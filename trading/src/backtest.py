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
from .growth import AdaptiveSizing


REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


class Side(Enum):
    FLAT = 0
    LONG = 1
    SHORT = -1


@dataclass(frozen=True)
class MakerFill:
    """指値注文が約定したかどうかを、バーの高値安値から判定する。

    ## なぜ要るか

    指値のコストは成行の9分の1（GMOコインの実料率で往復0.020% 対 0.180%）。
    しかしそれは**約定した場合の話**で、指値は必ずしも約定しない。
    「並べたら必ず約定する」前提で計算した優位性は、実在しない。

    ## 判定の仕方

    始値から offset だけ不利でない側に指値を置く。
    買いなら始値の下、売りなら始値の上。
    そのバーの値動きが**指値を抜けた**ときだけ約定とする。

        買い: low  < 始値 × (1 - offset) なら約定
        売り: high > 始値 × (1 + offset) なら約定

    「抜けた」を条件にするのは、指値と同値までしか来なかった場合、
    板に先に並んでいた注文が優先されて自分まで回ってこない可能性が高いため。
    OHLCVからは板の順番が分からないので、**約定しなかった側に倒す**。

    ## 逆選択はモデル化しない。勝手に出てくる

    指値が約定するのは「価格が自分に向かってきたとき」＝
    買い指値なら下げているとき。約定した直後に不利な方向へ動きやすい。

    これは**別途モデル化する必要がない**。
    正直に置いて正直に約定判定すれば、そのバーの値動きから自動的に出てくる。
    やるべきなのは、それを打ち消さないことだけ。

    ## offset は「約定するか」だけを決める。値段は良くしない

    指値を深く置けば実際には約定価格も良くなるが、**ここでは加算しない**。
    スプレッドを払わずに済む分は `CostModel.cost_rate(MAKER)` が
    すでに織り込んでいるので、ここで値段も良くすると**二重計上**になる。

    最初の実装はこれを間違えていて、EMAクロス戦略の成績が
    成行 +6,843% に対して指値 +16,471% という、
    片道2bpの値段改善を1,470往復ぶん積み上げただけの数字を出していた。

    そのため、この模型では**深い offset は単に不利**になる（約定率だけ下がる）。
    実際には「深く置くほど、約定しにくいが値段は良い」というトレードオフがある。
    そこは表現できていない。**保守側のずれ**として受け入れている。

    ## この模型が捉えていないもの

    - 板の厚み。自分の注文量が板を動かす影響は入っていない
    - バー内の時間順序。安値がバーの前半に来たか後半かは分からない
    - 部分約定。全量約定するか、しないかの二択にしてある
    - 深く置いたときの値段改善（上記のとおり、意図的に入れていない）
    """

    #: 始値から何割離して置くか（0.0002 = 2bp）。
    #: 0にすると始値ちょうどに置くことになり、
    #: 始値は常に [安値, 高値] の内側なので判定が退化する
    offset: float = 0.0002

    #: 約定しなかったとき、そのバーの終値で成行に切り替えるか。
    #: False なら見送る（次のバーで置き直す動きになる）
    chase_at_close: bool = False

    def __post_init__(self) -> None:
        if self.offset <= 0:
            raise ValueError(
                "offset は正の値である必要があります。"
                "0にすると始値ちょうどに置くことになり、"
                "始値は必ず高値安値の内側にあるため常に約定してしまいます"
            )
        if self.offset > 0.05:
            raise ValueError("offset が大きすぎます（5%超）")

    def fills(self, side: Side, open_price: float, high: float, low: float) -> bool:
        """そのバーで指値が約定したか。

        side は「自分が出す注文の向き」。買い注文なら Side.LONG、
        売り注文なら Side.SHORT（ロングの決済も売り注文なので SHORT）。
        """
        if side is Side.LONG:
            return bool(low < open_price * (1.0 - self.offset))
        if side is Side.SHORT:
            return bool(high > open_price * (1.0 + self.offset))
        return False


@dataclass(frozen=True)
class BacktestConfig:
    """バックテストの実行条件。"""

    #: 初期資金（円）
    initial_capital: float = 500_000.0

    #: 1トレードで投じる資金の割合。1.0 で全額。
    #: risk_per_trade を指定した場合はそちらが優先される
    position_fraction: float = 1.0

    #: 1トレードで許容する損失を、資金に対する率で指定する（例: 0.01 = 1%）。
    #: 損切り価格までの距離からポジションサイズを逆算するため、
    #: ボラティリティが高いときは自動的に小さく建てることになる。
    #:
    #: Barber & Odean 系の研究が示すとおり、個人の損失の大半は
    #: 銘柄選択の失敗ではなく、コストと過大なポジションから来る。
    #: ケリー基準の数理では、賭け金を最適値の c 倍にすると
    #: 長期成長率は概ね c(2-c) 倍になり、2倍賭けると成長率はゼロになる。
    #: 半分に抑えれば最大成長率の約75%を保ちながら変動を大きく減らせる。
    #: None なら position_fraction による固定割合になる
    risk_per_trade: float | None = None

    #: 執行方法。既定は保守側の TAKER
    order_type: OrderType = OrderType.TAKER

    #: 指値の約定判定。order_type=MAKER のときだけ効く。
    #: **None のままだと「並べたら必ず約定する」前提**になり、
    #: MAKER の結果は上振れする。指値で運用するつもりなら必ず指定すること。
    #:
    #: なお損切りは常に成行として扱う（指値では逆行時に約定しないため）。
    #: 利確は指値なので order_type に従う
    maker_fill: MakerFill | None = None

    #: ショートを許可するか。
    #: 国内では現物で売り建てできず、証拠金取引（個人は2倍まで）が必要。
    #: 既定は False にしてある
    allow_short: bool = False

    #: レバレッジ。国内の個人は2倍が上限
    leverage: float = 1.0

    #: 成績に応じてポジションサイズを変える設定。
    #: 指定すると risk_per_trade より優先される。
    #: 資産が最高値を更新している間だけ拡大し、ドローダウン中は必ず縮小する
    adaptive_sizing: AdaptiveSizing | None = None

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("初期資金は正の値である必要があります")
        if not 0 < self.position_fraction <= 1:
            raise ValueError("position_fraction は 0 より大きく 1 以下です")
        if self.risk_per_trade is not None and not 0 < self.risk_per_trade <= 0.5:
            raise ValueError(
                "risk_per_trade は 0 より大きく 0.5 以下です。"
                "1トレードで資金の50%超を危険に晒す設定は認めていません"
            )
        if self.leverage < 1:
            raise ValueError("レバレッジは1以上です")
        if self.leverage > 2:
            raise ValueError(
                "国内の個人向け暗号資産証拠金取引は2倍が上限です"
                "（2020年5月施行の内閣府令）"
            )
        if self.maker_fill is not None and self.order_type is not OrderType.MAKER:
            raise ValueError(
                "maker_fill は order_type=MAKER のときだけ意味を持ちます。"
                "成行で約定判定をしても、判定するものがありません"
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
    peak_equity = config.initial_capital
    highs_made = 0
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

    def close_position(
        exit_raw: float,
        when: pd.Timestamp,
        reason: str,
        order_type: OrderType | None = None,
    ) -> None:
        nonlocal cash, side, size, entry_price, entry_time, entry_cost
        nonlocal active_stop, active_target

        if side is Side.FLAT:
            return

        order_type = config.order_type if order_type is None else order_type
        # 決済は建てたのと逆側なので、コストの向きも逆になる
        exit_side = Side.SHORT if side is Side.LONG else Side.LONG
        exit_price = _fill_price(exit_raw, exit_side, cost, order_type)
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
                      stop: float, target: float,
                      order_type: OrderType | None = None) -> None:
        nonlocal cash, side, size, entry_price, entry_time, entry_cost
        nonlocal active_stop, active_target

        order_type = config.order_type if order_type is None else order_type
        fill = _fill_price(raw_price, new_side, cost, order_type)

        risk_fraction = config.risk_per_trade
        if config.adaptive_sizing is not None:
            risk_fraction = config.adaptive_sizing.risk_for(cash, peak_equity, highs_made)

        if risk_fraction is not None and not np.isnan(stop):
            # 損切りまでの距離からサイズを逆算する。
            # 損切りが遠い（＝ボラティリティが高い）ときは自動的に小さく建つ
            stop_distance = abs(fill - stop)
            if stop_distance <= 0:
                return
            risk_amount = cash * risk_fraction
            notional = risk_amount * fill / stop_distance
            # レバレッジ上限は超えられない
            notional = min(notional, cash * config.leverage)
        else:
            notional = cash * config.position_fraction * config.leverage

        if notional <= 0 or raw_price <= 0:
            return
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

    unfilled_entries = 0
    unfilled_exits = 0

    def resolve_fill(order_side: Side, i: int) -> tuple[float, OrderType] | None:
        """このバーで、その向きの注文がいくらで約定するかを返す。

        指値の約定判定を入れている場合だけ、約定しないことがある。
        戻り値が None なら、この注文は成立しなかった。
        """
        if config.order_type is not OrderType.MAKER or config.maker_fill is None:
            return opens[i], config.order_type

        if config.maker_fill.fills(order_side, opens[i], highs[i], lows[i]):
            # 約定した。値段は始値を基準にしたまま、コストだけ MAKER のものを使う。
            # 指値ぶんの値段改善を足すと cost_rate との二重計上になる
            return opens[i], OrderType.MAKER
        if config.maker_fill.chase_at_close:
            # 約定しなかったので終値で成行に切り替える。手数料は成行のもの
            return closes[i], OrderType.TAKER
        return None

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
                # **損切りは常に成行。** 逆行しているときに指値では約定しない
                close_position(
                    float(active_stop), bar_time, "stop_loss", OrderType.TAKER
                )
            elif hit_target:
                # 利確はもともと板に置く指値なので、執行方法はそのまま
                close_position(float(active_target), bar_time, "take_profit")

        # --- 2. 1本前のバーで出たシグナルを、このバーの始値で執行する
        desired_raw = directions[i - 1]
        desired = Side.FLAT
        if desired_raw > 0:
            desired = Side.LONG
        elif desired_raw < 0 and config.allow_short:
            desired = Side.SHORT

        if desired is not side:
            still_holding = False
            if side is not Side.FLAT:
                # 決済は建玉と逆向きの注文になる
                exit_order = Side.SHORT if side is Side.LONG else Side.LONG
                filled = resolve_fill(exit_order, i)
                if filled is None:
                    # 指値が約定しなかった。**降りたくても降りられない。**
                    # 次のバーで置き直すことになる（ポジションは残る）
                    unfilled_exits += 1
                    still_holding = True
                else:
                    close_position(filled[0], bar_time, "signal", filled[1])

            if desired is not Side.FLAT and not still_holding:
                filled = resolve_fill(desired, i)
                if filled is None:
                    # 指値が約定しなかった。この機会は取れない
                    unfilled_entries += 1
                else:
                    open_position(
                        desired,
                        filled[0],
                        bar_time,
                        float(stops[i - 1]),
                        float(targets[i - 1]),
                        filled[1],
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
        if equity[i] > peak_equity:
            peak_equity = equity[i]
            highs_made += 1

    # 最終バーで持ち越していたら手仕舞う。
    # データが尽きて強制的に閉じるので、成行として扱う
    if side is not Side.FLAT:
        close_position(closes[-1], index[-1], "end_of_data", OrderType.TAKER)
        equity[-1] = cash

    equity_series = pd.Series(equity, index=index, name="equity").ffill()

    if cost.unverified:
        warnings.append(
            f"コストモデル「{cost.name}」には未確認の数字が含まれます: {cost.note}"
        )

    if config.order_type is OrderType.MAKER and config.maker_fill is None:
        warnings.append(
            "指値（MAKER）で計算していますが、約定判定を入れていません。"
            "「並べたら必ず約定する」前提なので、この結果は上振れしています。"
            "BacktestConfig(maker_fill=MakerFill()) を指定してください。"
        )
    if unfilled_entries or unfilled_exits:
        attempted = len(trades) + unfilled_entries
        rate = unfilled_entries / attempted if attempted else 0.0
        warnings.append(
            f"指値が約定しなかった回数: 新規 {unfilled_entries} 回"
            f"（試みた {attempted} 回の {rate * 100:.1f}%）、決済 {unfilled_exits} 回。"
            "決済の未約定は、降りたい場面で降りられなかったことを意味します。"
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
