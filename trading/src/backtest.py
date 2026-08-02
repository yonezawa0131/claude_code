"""イベント駆動のバックテストエンジン。

設計方針は「エンジンが嘘をつかないこと」に全振りしてある。
バックテストが実運用より良く見える原因はだいたい決まっていて、
このエンジンはそれぞれに対策を持っている。

1. 先読み（look-ahead）
   バー t の情報で判断し、同じバー t の終値で約定させると、
   未来を知って取引したことになる。
   → このエンジンは **バー t のシグナルを、バー t+1 の始値で約定させる**。
      さらに validate.check_causality() で、戦略が本当に因果的かを
      機械的に検査できるようにしてある。

2. コストの過小評価
   → 全約定に手数料・スプレッド・滑りを乗せる。costs.py 参照。

3. 建値と決済の同一バー内順序の楽観視
   1本のバーの中で損切りと利確の両方に触れた場合、
   どちらが先に起きたかは日足・時間足のデータからは分からない。
   → **常に損切りが先に起きたものとして扱う**（保守側）。

4. 買い持ちとの比較忘れ
   ビットコインを持っているだけの成績を下回る戦略は、
   手間とリスクを増やして価値を減らしている。
   → metrics.py が必ず買い持ちベンチマークを並べる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import numpy as np
import pandas as pd

from .costs import CostModel, OrderType


REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


class Side(Enum):
    FLAT = 0
    LONG = 1
    SHORT = -1


@dataclass(frozen=True)
class BacktestConfig:
    """バックテストの実行条件。"""

    #: 初期資金（円）
    initial_capital: float = 500_000.0

    #: 1トレードで投じる資金の割合。1.0 で全額
    position_fraction: float = 1.0

    #: 執行方法。既定は保守側の TAKER
    order_type: OrderType = OrderType.TAKER

    #: ショートを許可するか。
    #: 国内では現物で売り建てできず、証拠金取引（個人は2倍まで）が必要。
    #: 既定は False にしてある
    allow_short: bool = False

    #: レバレッジ。国内の個人は2倍が上限
    leverage: float = 1.0

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("初期資金は正の値である必要があります")
        if not 0 < self.position_fraction <= 1:
            raise ValueError("position_fraction は 0 より大きく 1 以下です")
        if self.leverage < 1:
            raise ValueError("レバレッジは1以上です")
        if self.leverage > 2:
            raise ValueError(
                "国内の個人向け暗号資産証拠金取引は2倍が上限です"
                "（2020年5月施行の内閣府令）"
            )


@dataclass
class Trade:
    """約定して決済まで終わった1往復の記録。"""

    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: Side
    entry_price: float
    exit_price: float
    size: float
    #: 手数料・スプレッド・滑りの合計（円）
    cost: float
    #: コスト差引後の損益（円）
    pnl: float
    #: 決済理由
    reason: str

    @property
    def bars_held(self) -> int:
        return 0  # 補助。集計側で必要になったら埋める


class Strategy(Protocol):
    """戦略のインターフェース。

    generate() は **因果的（causal）** でなければならない。
    つまり、i 番目の行の出力は df の 0..i 行目だけから決まること。
    未来の行を1行でも参照したら、それは先読みであり、
    バックテストの結果は意味を失う。

    この性質は validate.check_causality() で機械的に検査できる。
    新しい戦略を書いたら必ず通すこと。
    """

    name: str

    def warmup(self) -> int:
        """指標の計算に必要な最低バー数。この本数までは取引しない。"""
        ...

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """バーごとの目標ポジションを返す。

        戻り値は df と同じ index を持ち、次の列を含むこと:
          - direction: +1(ロング) / -1(ショート) / 0(ノーポジ)
          - stop_loss: 損切り価格。不要なら NaN
          - take_profit: 利確価格。不要なら NaN
        """
        ...


@dataclass
class BacktestResult:
    """バックテストの生の出力。評価は metrics.py が行う。"""

    equity: pd.Series
    trades: list[Trade]
    config: BacktestConfig
    cost_model: CostModel
    strategy_name: str
    price: pd.Series
    #: 執行できなかった理由などの警告
    warnings: list[str] = field(default_factory=list)


def _validate_frame(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"必要な列がありません: {missing}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("index は DatetimeIndex である必要があります")
    if not df.index.is_monotonic_increasing:
        raise ValueError("index が時刻の昇順になっていません")
    if df.index.has_duplicates:
        raise ValueError("index に重複した時刻があります")

    bad_hl = (df["high"] < df["low"]).sum()
    if bad_hl:
        raise ValueError(f"high < low の行が {bad_hl} 件あります")
    outside = (
        (df["close"] > df["high"])
        | (df["close"] < df["low"])
        | (df["open"] > df["high"])
        | (df["open"] < df["low"])
    ).sum()
    if outside:
        raise ValueError(f"始値/終値が高値安値の外側にある行が {outside} 件あります")


def _fill_price(raw_price: float, side: Side, cost: CostModel, order_type: OrderType) -> float:
    """コストを織り込んだ約定価格。

    買うときは高く、売るときは安く約定する側に倒す。
    """
    rate = cost.cost_rate(order_type)
    if side is Side.LONG:
        return raw_price * (1 + rate)
    if side is Side.SHORT:
        return raw_price * (1 - rate)
    return raw_price


def run_backtest(
    df: pd.DataFrame,
    strategy: Strategy,
    cost: CostModel,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """バックテストを実行する。

    df は index が DatetimeIndex、列に open/high/low/close/volume を持つこと。
    """
    config = config or BacktestConfig()
    _validate_frame(df)

    signals = strategy.generate(df)
    for col in ("direction", "stop_loss", "take_profit"):
        if col not in signals.columns:
            raise ValueError(f"戦略の出力に {col} 列がありません")
    if not signals.index.equals(df.index):
        raise ValueError("戦略の出力の index が入力と一致しません")

    warmup = max(strategy.warmup(), 1)
    warnings: list[str] = []

    if config.allow_short and (signals["direction"] < 0).any():
        warnings.append(
            "ショートを含む戦略です。国内では現物で売り建てできず、"
            "証拠金取引口座（個人はレバレッジ2倍まで）が必要になります。"
        )
    if not config.allow_short and (signals["direction"] < 0).any():
        warnings.append(
            "戦略がショートを指示していますが allow_short=False のため"
            "ノーポジとして扱いました。"
        )

    opens = df["open"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    directions = signals["direction"].to_numpy(dtype=float)
    stops = signals["stop_loss"].to_numpy(dtype=float)
    targets = signals["take_profit"].to_numpy(dtype=float)
    index = df.index

    cash = config.initial_capital
    side = Side.FLAT
    size = 0.0
    entry_price = 0.0
    entry_time: pd.Timestamp | None = None
    entry_cost = 0.0
    active_stop = np.nan
    active_target = np.nan

    equity = np.empty(len(df), dtype=float)
    equity[:] = np.nan
    trades: list[Trade] = []

    def mark_to_market(price: float) -> float:
        if side is Side.FLAT:
            return cash
        if side is Side.LONG:
            return cash + size * price
        # ショートは建値と現在値の差で評価する
        return cash + size * (2 * entry_price - price)

    def close_position(exit_raw: float, when: pd.Timestamp, reason: str) -> None:
        nonlocal cash, side, size, entry_price, entry_time, entry_cost
        nonlocal active_stop, active_target

        if side is Side.FLAT:
            return

        # 決済は建てたのと逆側なので、コストの向きも逆になる
        exit_side = Side.SHORT if side is Side.LONG else Side.LONG
        exit_price = _fill_price(exit_raw, exit_side, cost, config.order_type)
        exit_cost = abs(exit_raw - exit_price) * size

        if side is Side.LONG:
            proceeds = size * exit_price
            pnl = proceeds - size * entry_price
            cash += proceeds
        else:
            pnl = size * (entry_price - exit_price)
            cash += size * entry_price + pnl

        trades.append(
            Trade(
                entry_time=entry_time,  # type: ignore[arg-type]
                exit_time=when,
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                size=size,
                cost=entry_cost + exit_cost,
                pnl=pnl,
                reason=reason,
            )
        )
        side = Side.FLAT
        size = 0.0
        entry_price = 0.0
        entry_time = None
        entry_cost = 0.0
        active_stop = np.nan
        active_target = np.nan

    def open_position(new_side: Side, raw_price: float, when: pd.Timestamp,
                      stop: float, target: float) -> None:
        nonlocal cash, side, size, entry_price, entry_time, entry_cost
        nonlocal active_stop, active_target

        notional = cash * config.position_fraction * config.leverage
        if notional <= 0 or raw_price <= 0:
            return
        fill = _fill_price(raw_price, new_side, cost, config.order_type)
        qty = notional / fill
        entry_cost = abs(fill - raw_price) * qty

        if new_side is Side.LONG:
            cash -= qty * fill
        else:
            # ショートは証拠金を拘束する扱い。建値ぶんを一旦差し引いて
            # 決済時に戻す（mark_to_market と整合させるための簡略化）
            cash -= qty * fill

        side = new_side
        size = qty
        entry_price = fill
        entry_time = when
        active_stop = stop
        active_target = target

    for i in range(len(df)):
        if i < warmup:
            equity[i] = cash
            continue

        bar_time = index[i]

        # --- 1. 保有中なら、まずこのバーの中で損切り/利確に触れたか判定する
        if side is not Side.FLAT:
            hit_stop = False
            hit_target = False
            if not np.isnan(active_stop):
                hit_stop = (
                    lows[i] <= active_stop if side is Side.LONG else highs[i] >= active_stop
                )
            if not np.isnan(active_target):
                hit_target = (
                    highs[i] >= active_target if side is Side.LONG else lows[i] <= active_target
                )

            # 同一バーで両方に触れた場合は、損切りが先に起きたとみなす（保守側）
            if hit_stop:
                close_position(float(active_stop), bar_time, "stop_loss")
            elif hit_target:
                close_position(float(active_target), bar_time, "take_profit")

        # --- 2. 1本前のバーで出たシグナルを、このバーの始値で執行する
        desired_raw = directions[i - 1]
        desired = Side.FLAT
        if desired_raw > 0:
            desired = Side.LONG
        elif desired_raw < 0 and config.allow_short:
            desired = Side.SHORT

        if desired is not side:
            if side is not Side.FLAT:
                close_position(opens[i], bar_time, "signal")
            if desired is not Side.FLAT:
                open_position(
                    desired,
                    opens[i],
                    bar_time,
                    float(stops[i - 1]),
                    float(targets[i - 1]),
                )
        elif side is not Side.FLAT:
            # 同じ向きを維持する場合でも、損切り水準は更新する（トレーリング）
            new_stop = float(stops[i - 1])
            if not np.isnan(new_stop):
                if np.isnan(active_stop):
                    active_stop = new_stop
                elif side is Side.LONG:
                    active_stop = max(active_stop, new_stop)
                else:
                    active_stop = min(active_stop, new_stop)
            new_target = float(targets[i - 1])
            if not np.isnan(new_target):
                active_target = new_target

        equity[i] = mark_to_market(closes[i])

    # 最終バーで持ち越していたら手仕舞う
    if side is not Side.FLAT:
        close_position(closes[-1], index[-1], "end_of_data")
        equity[-1] = cash

    equity_series = pd.Series(equity, index=index, name="equity").ffill()

    if cost.unverified:
        warnings.append(
            f"コストモデル「{cost.name}」には未確認の数字が含まれます: {cost.note}"
        )

    return BacktestResult(
        equity=equity_series,
        trades=trades,
        config=config,
        cost_model=cost,
        strategy_name=getattr(strategy, "name", type(strategy).__name__),
        price=df["close"],
        warnings=warnings,
    )
