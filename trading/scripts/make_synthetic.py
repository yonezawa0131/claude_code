#!/usr/bin/env python
"""
バックテストエンジンの自己検証用に、合成OHLCV（ローソク足）データを生成するスクリプト。
ネットワークには一切アクセスしない。

各バーは「始値→終値」を対数価格空間のブラウニアン・ブリッジで結ぶ経路を乱数で生成し、
その経路上の最大値/最小値からhigh/lowを作る。始値・終値は経路の端点として必ず
含まれる（かつ最終的にopen/closeとの比較で明示的にクランプする）ため、
    high >= max(open, close)
    low  <= min(open, close)
が常に保証される。

--regime で以下の相場特性を切り替えられる:
    trend  : 明確な上昇トレンド（強いドリフトを持つ幾何ブラウン運動）
    range  : 平均回帰するレンジ相場（オルンシュタイン=ウーレンベック過程）
    mixed  : トレンド区間とレンジ区間が交互に現れる
    random : ドリフトなしの幾何ブラウン運動（優位性のない戦略が優位性を
             持てないはずの対照群。ここで利益が出るならエンジンのバグ）
    intraday : ランダムウォークに「日中モメンタム」だけを埋め込んだ**陽性対照**。
             セッション最終バーのリターンが、そのセッション初バーのリターンの
             beta 倍だけ押し上げられる。それ以外の性質は random と同じ
             （トレンドもレンジもない）。
             検出器が「何も見つけない」とき、それがデータにパターンが無いからか
             コードが壊れているからかを区別するために要る。

陰性対照（random）だけでは足りない。何も検出しないコードは、
陰性対照を必ず通ってしまう。**存在するパターンを検出できることを先に示す。**

出力CSVの列・形式は fetch_ohlcv.py と完全に同じ:
    timestamp,open,high,low,close,volume
    （timestampはUTCのISO8601文字列、例: 2026-08-01T00:00:00Z）

使い方:
    python scripts/make_synthetic.py --bars 5000 --seed 42 --out data/synthetic.csv --regime mixed
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from typing import Callable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# 出力CSVの列（厳密にこの順序・名前で出力する。fetch_ohlcv.pyと同一形式）
CSV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

# BTC/JPYらしい初期価格水準（円）。1000万円程度からスタートする
INITIAL_PRICE = 10_000_000.0

# タイムスタンプのアンカー（再現性のため固定日時から1時間足で生成する）
ANCHOR_START = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
BAR_TIMEDELTA = dt.timedelta(hours=1)

# 1本のバー内の値動き経路を何分割して生成するか（ブラウニアン・ブリッジのステップ数）
INTRABAR_STEPS = 20

# 陽性対照（intradayレジーム）の既定値。
# 1セッション24本＝1時間足で1日。ANCHOR_STARTがUTC 00:00なので、
# セッションの区切りは IntradayMomentum の既定設定と一致する
DEFAULT_SESSION_BARS = 24
# 初バーのリターンが最終バーに乗る倍率。0にすると random と同じ性質になる
DEFAULT_INTRADAY_BETA = 1.0


# ---------------------------------------------------------------------------
# レジームごとの終値系列生成
# ---------------------------------------------------------------------------


def _generate_trend_path(
    rng: np.random.Generator,
    bars: int,
    start_price: float,
    mu: float = 0.0006,
    sigma: float = 0.004,
    direction: float = 1.0,
) -> np.ndarray:
    """
    明確なドリフトを持つ幾何ブラウン運動で終値の系列を生成する（対数リターンの累積）。
    direction<0を渡すと下降トレンドにできる（mixedレジームで区間の向きを変えるために使用）。
    戻り値は各バー終値の配列（長さbars）。
    """
    log_returns = direction * mu + sigma * rng.standard_normal(bars)
    log_prices = np.log(start_price) + np.cumsum(log_returns)
    return np.exp(log_prices)


def _generate_range_path(
    rng: np.random.Generator,
    bars: int,
    start_price: float,
    theta: float = 0.03,
    sigma: float = 0.005,
) -> np.ndarray:
    """
    オルンシュタイン=ウーレンベック過程で、start_priceを中心に平均回帰する
    対数価格の系列を生成する。戻り値は各バー終値の配列（長さbars）。
    """
    log_center = np.log(start_price)
    log_prices = np.empty(bars)
    prev = log_center
    noise = rng.standard_normal(bars)
    for i in range(bars):
        prev = prev + theta * (log_center - prev) + sigma * noise[i]
        log_prices[i] = prev
    return np.exp(log_prices)


def _generate_random_path(
    rng: np.random.Generator,
    bars: int,
    start_price: float,
    sigma: float = 0.006,
) -> np.ndarray:
    """
    ドリフトなし（mu=0）の幾何ブラウン運動、つまり純粋なランダムウォークで終値を生成する。
    優位性のない戦略が優位性を持てないはずの対照群データ。
    """
    log_returns = sigma * rng.standard_normal(bars)
    log_prices = np.log(start_price) + np.cumsum(log_returns)
    return np.exp(log_prices)


def _generate_intraday_momentum_path(
    rng: np.random.Generator,
    bars: int,
    start_price: float,
    sigma: float = 0.006,
    session_bars: int = DEFAULT_SESSION_BARS,
    beta: float = DEFAULT_INTRADAY_BETA,
    beta_end: float | None = None,
) -> np.ndarray:
    """陽性対照。ランダムウォークに、日中モメンタムだけを埋め込む。

    各セッションの**最終バー**の対数リターンに、
    そのセッションの**初バー**の対数リターンの beta 倍を加える。

        r[last] = beta * r[first] + noise

    加える量の期待値は0なので、系列全体としてのドリフトは生まれない。
    つまり買い持ちでは取れず、**セッション内の位置を見て初めて取れる**利益になる。

    セッションの区切りは ANCHOR_START（UTC 00:00）に揃えてあるので、
    IntradayMomentum(session_hours=24, session_start_hour=0) の区切りと一致する。

    埋め込んだ効果の大きさは事前に計算できる。ロングだけを取る場合、
    初バーが上げた（確率1/2）ときの最終バーの期待リターンは

        beta * sigma * sqrt(2/pi)

    beta=1.0, sigma=0.006 なら約 +0.48%。往復コスト0.18%を引いても残る水準で、
    「検出できて当然」の強さにしてある。**弱い信号を検出できるかは別の問題**で、
    それは強さを下げたデータで測ること。

    ## 優位性が消えていく相場

    beta_end を指定すると、beta から beta_end まで**セッションごとに線形で変化**する。
    beta=1.0, beta_end=0.0 なら「効いていた優位性が、期間の後半にかけて
    裁定されて消えていく」データになる。

    これは実際に起きることであり（発見・公表された異常収益は縮小する傾向がある）、
    **全期間で1回バックテストすると気づけない**という点で厄介でもある。
    前半の利益が後半の損失を覆い隠して、平均すればプラスに見えてしまう。
    ウォークフォワード検証がこれを捉えられるかを測るために使う。
    """
    if session_bars < 2:
        raise ValueError("--session-bars は2以上である必要があります")

    log_returns = sigma * rng.standard_normal(bars)
    starts = list(range(0, bars, session_bars))
    finish = beta if beta_end is None else beta_end

    for n, start in enumerate(starts):
        last = start + session_bars - 1
        if last >= bars:
            break  # 端数のセッションには埋め込まない
        # セッションごとに beta -> beta_end へ線形に変化させる
        progress = n / (len(starts) - 1) if len(starts) > 1 else 0.0
        strength = beta + (finish - beta) * progress
        log_returns[last] += strength * log_returns[start]

    log_prices = np.log(start_price) + np.cumsum(log_returns)
    return np.exp(log_prices)


def _generate_mixed_path(
    rng: np.random.Generator,
    bars: int,
    start_price: float,
    chunk_size: int = 250,
) -> np.ndarray:
    """
    トレンド区間とレンジ区間を交互に繋げて終値の系列を生成する。
    トレンド区間は前の値から連続するように接続し、方向（上昇/下降）を区間ごとに切り替える。
    """
    closes = np.empty(bars)
    current_price = start_price
    pos = 0
    chunk_idx = 0
    trend_direction = 1.0
    while pos < bars:
        n = min(chunk_size, bars - pos)
        if chunk_idx % 2 == 0:
            segment = _generate_trend_path(rng, n, current_price, direction=trend_direction)
            trend_direction *= -1.0  # 次のトレンド区間は逆方向にして変化をつける
        else:
            segment = _generate_range_path(rng, n, current_price)
        closes[pos : pos + n] = segment
        current_price = segment[-1]
        pos += n
        chunk_idx += 1
    return closes


def _intraday_entry(
    rng: np.random.Generator, bars: int, price: float, **options
) -> np.ndarray:
    return _generate_intraday_momentum_path(
        rng,
        bars,
        price,
        session_bars=int(options.get("session_bars", DEFAULT_SESSION_BARS)),
        beta=float(options.get("beta", DEFAULT_INTRADAY_BETA)),
        beta_end=(
            None if options.get("beta_end") is None else float(options["beta_end"])
        ),
    )


REGIME_GENERATORS: dict[str, Callable[..., np.ndarray]] = {
    "trend": lambda rng, bars, price, **_: _generate_trend_path(rng, bars, price),
    "range": lambda rng, bars, price, **_: _generate_range_path(rng, bars, price),
    "mixed": lambda rng, bars, price, **_: _generate_mixed_path(rng, bars, price),
    "random": lambda rng, bars, price, **_: _generate_random_path(rng, bars, price),
    "intraday": _intraday_entry,
}


# ---------------------------------------------------------------------------
# バー内経路（high/lowの生成）
# ---------------------------------------------------------------------------


def _brownian_bridge_high_low(
    rng: np.random.Generator,
    open_price: float,
    close_price: float,
    path_sigma: float,
    steps: int = INTRABAR_STEPS,
) -> tuple[float, float]:
    """
    始値から終値まで対数価格空間でブラウニアン・ブリッジの経路を作り、
    その経路のmax/minからhigh/lowを求める。
    始値・終値は経路の端点として厳密に含まれ、さらに念のためopen/closeとの
    比較で明示的にクランプするため、
        high >= max(open, close), low <= min(open, close)
    が常に保証される。
    """
    a = np.log(open_price)
    b = np.log(close_price)
    t = np.linspace(0.0, 1.0, steps + 1)

    # 標準ブラウン運動 W（W[0] = 0）
    dw = rng.standard_normal(steps) / np.sqrt(steps)
    w = np.concatenate(([0.0], np.cumsum(dw)))

    # ブリッジ: B(t) = a + t*(b-a) + sigma*(W(t) - t*W(1))  -> B(0)=a, B(1)=b が厳密に成立
    bridge = a + t * (b - a) + path_sigma * (w - t * w[-1])
    prices = np.exp(bridge)

    high = float(max(prices.max(), open_price, close_price))
    low = float(min(prices.min(), open_price, close_price))
    return high, low


# ---------------------------------------------------------------------------
# 合成データ生成本体
# ---------------------------------------------------------------------------


def make_synthetic_ohlcv(bars: int, seed: int, regime: str, **options) -> pd.DataFrame:
    """指定されたレジーム・シードに従って合成OHLCVデータフレームを作る。

    options はレジームごとの追加パラメータ（intraday の session_bars / beta）。
    知らないキーは無視される。
    """
    if bars <= 0:
        raise ValueError("--bars は1以上の整数を指定してください")
    if regime not in REGIME_GENERATORS:
        raise ValueError(f"未対応のregimeです: {regime}（有効な値: {sorted(REGIME_GENERATORS)}）")

    rng = np.random.default_rng(seed)

    # バーごとの終値系列を生成
    closes = REGIME_GENERATORS[regime](rng, bars, INITIAL_PRICE, **options)

    # 始値は「1本前の終値」。最初のバーの始値は初期価格とする
    opens = np.empty(bars)
    opens[0] = INITIAL_PRICE
    opens[1:] = closes[:-1]

    # バー内のゆらぎ幅（ブリッジのsigma）。バーの実現リターンが大きいほど、
    # バー内のヒゲも大きくなるようにする
    bar_log_return = np.abs(np.log(closes / opens))
    path_sigma = 0.003 + 0.6 * bar_log_return

    highs = np.empty(bars)
    lows = np.empty(bars)
    for i in range(bars):
        h, l = _brownian_bridge_high_low(rng, opens[i], closes[i], path_sigma[i])
        highs[i] = h
        lows[i] = l

    # 出来高: リターンが大きいバーほど出来高も増える傾向を持たせた対数正規ノイズ
    base_volume = 3.0
    volume_noise = rng.lognormal(mean=0.0, sigma=0.5, size=bars)
    volumes = base_volume * (1.0 + 5.0 * bar_log_return) * volume_noise

    # 円単位（整数）に丸める。丸めによってhigh/lowの不等式が崩れないよう、
    # 丸め後にもう一度open/closeとのmax/minでクランプし直す
    opens_r = np.round(opens, 0)
    closes_r = np.round(closes, 0)
    highs_r = np.maximum(np.round(highs, 0), np.maximum(opens_r, closes_r))
    lows_r = np.minimum(np.round(lows, 0), np.minimum(opens_r, closes_r))

    timestamps = [ANCHOR_START + i * BAR_TIMEDELTA for i in range(bars)]
    timestamp_strs = [ts.strftime("%Y-%m-%dT%H:%M:%SZ") for ts in timestamps]

    df = pd.DataFrame(
        {
            "timestamp": timestamp_strs,
            "open": opens_r,
            "high": highs_r,
            "low": lows_r,
            "close": closes_r,
            "volume": np.round(volumes, 4),
        }
    )
    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="バックテストエンジン自己検証用の合成OHLCVデータを生成する")
    parser.add_argument("--bars", type=int, required=True, help="生成するバー数")
    parser.add_argument("--seed", type=int, required=True, help="乱数シード（同じ値なら完全に再現できる）")
    parser.add_argument("--out", type=str, required=True, help="出力CSVファイルパス")
    parser.add_argument(
        "--regime",
        type=str,
        required=True,
        choices=sorted(REGIME_GENERATORS.keys()),
        help="価格系列の性質（trend/range/mixed/random/intraday）",
    )
    parser.add_argument(
        "--session-bars",
        type=int,
        default=DEFAULT_SESSION_BARS,
        help=f"intradayレジーム: 1セッションのバー数（既定 {DEFAULT_SESSION_BARS}）",
    )
    parser.add_argument(
        "--intraday-beta",
        type=float,
        default=DEFAULT_INTRADAY_BETA,
        help=(
            "intradayレジーム: 初バーのリターンが最終バーに乗る倍率"
            f"（既定 {DEFAULT_INTRADAY_BETA}、0でパターンなし）"
        ),
    )
    parser.add_argument(
        "--intraday-beta-end",
        type=float,
        default=None,
        help=(
            "intradayレジーム: 期間の最後での倍率。"
            "指定すると beta からここまで線形に変化する"
            "（0を指定すれば「優位性が裁定されて消えていく」データになる）"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    try:
        df = make_synthetic_ohlcv(
            args.bars,
            args.seed,
            args.regime,
            session_bars=args.session_bars,
            beta=args.intraday_beta,
            beta_end=args.intraday_beta_end,
        )
    except ValueError as exc:
        print(f"エラー: パラメータが不正です。{exc}", file=sys.stderr)
        sys.exit(1)

    try:
        out_dir = os.path.dirname(args.out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        df.to_csv(args.out, index=False, columns=CSV_COLUMNS)
    except OSError as exc:
        print(f"エラー: 出力ファイルの書き込みに失敗しました。{exc}", file=sys.stderr)
        sys.exit(1)

    invalid_hl = int((df["high"] < df["low"]).sum())
    invalid_close = int(((df["close"] > df["high"]) | (df["close"] < df["low"])).sum())
    invalid_open = int(((df["open"] > df["high"]) | (df["open"] < df["low"])).sum())

    print(f"保存しました: {args.out}")
    print(f"regime={args.regime}  bars={len(df)}  seed={args.seed}")
    print(
        f"整合性チェック: high<low = {invalid_hl}件, closeが[low,high]範囲外 = {invalid_close}件, "
        f"openが[low,high]範囲外 = {invalid_open}件"
    )


if __name__ == "__main__":
    main()
