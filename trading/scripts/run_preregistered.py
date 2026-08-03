#!/usr/bin/env python
"""事前登録した検定を、そのまま実行する。

## なぜ調整できないスクリプトが要るのか

1時間足のデータで日中モメンタムを試して外れたとき、
「セッションの区切りを変えてみよう」と考えるのは自然な反応になる。
区切り4通り × 測る本数2 × 持つ本数2 × 閾値3 = 48通り試せば、何か当たる。

そして 48通り試したときに優位性ゼロでも到達する年率シャープは、
この基盤で実測して **2.61** だった（docs/05）。
当たったものが 2.61 を超えていなければ、それは試した数の産物でしかない。

だから**データを見る前に条件を固定する**。
このスクリプトには戦略もパラメータも渡せない。
結果を見てから条件を変える余地を、構造的になくしてある。

条件を変えたくなったら、それは新しい検定なので、
試行数を数え直して `run_backtest.py` で明示的に実行すること。

## 事前登録した内容（2026年8月3日、1時間足のデータを見る前に確定）

仮説:
    Shen, Urquhart & Wang (2022, Financial Review) が報告した
    ビットコインの日中モメンタム。セッション冒頭の値動きが終盤を予測する。

パラメータ（すべて事前に決め打ち。データからは選ばない）:
    session_hours      = 24     1日1セッション
    session_start_hour = 0      UTC 0時区切り
    entry_bars         = 1      冒頭1本で方向を測る
    exit_bars          = 1      終盤1本を持つ
    threshold          = 0.0    閾値なし
    stop_atr           = 2.0    既定の損切り
    allow_short        = False  現物を想定

条件（成行・GMOコイン取引所・元本30万円・全額）。

判定基準（**5つすべてを満たしたときだけ「優位性あり」とする**）:
    1. 先読みがないこと
    2. コスト控除後のリターンが買い持ちを上回ること
    3. 年率シャープが、試行数を考慮した閾値を上回ること
    4. ローテーション検定で上位5%に入ること
    5. ウォークフォワードで、過半の期間が買い持ちを上回り、
       かつ減衰していないこと

    5については、各期間の取引が30回に満たない場合は
    「判定不能」とする。**不合格ではなく、判定不能。**

試行数の数え方:
    実データ（BTC/JPY）に対してこれまでに評価した戦略の総数を使う。
    日足で6件、1時間足の比較で7件。合わせて13。
    この検定だけを見れば事前登録の1件だが、**同じデータを何度も見た事実は消えない**ので、
    厳しい側で数える。

使い方:
    python trading/scripts/run_preregistered.py --data trading/data/btc_jpy_1hour.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from trading.src.costs import GMO_EXCHANGE, OrderType  # noqa: E402
from trading.src.metrics import evaluate, multiple_testing_report  # noqa: E402
from trading.src.strategy import IntradayMomentum  # noqa: E402
from trading.src.validate import (  # noqa: E402
    DECAY_Z_THRESHOLD,
    MIN_TRADES_PER_WINDOW,
    check_causality,
    rotation_null,
    walk_forward,
)

# --- 事前登録した設定。ここを変えたら、それは別の検定 ----------------------

STRATEGY = IntradayMomentum(
    session_hours=24,
    session_start_hour=0,
    entry_bars=1,
    exit_bars=1,
    threshold=0.0,
    allow_short=False,
    atr_period=14,
    stop_atr=2.0,
)
CONFIG = BacktestConfig(
    initial_capital=300_000.0,
    position_fraction=1.0,
    order_type=OrderType.TAKER,
)
COST = GMO_EXCHANGE
N_TRIALS = 13
NULL_RUNS = 200
WALK_FORWARD_WINDOWS = 6
ROTATION_PERCENTILE = 95.0

PASS, FAIL, UNKNOWN = "合格", "不合格", "判定不能"


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"データが見つかりません: {path}")
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def _require_hourly(df: pd.DataFrame) -> None:
    hours = pd.Series(df.index).diff().median().total_seconds() / 3600.0
    if not 0.9 <= hours <= 1.1:
        raise SystemExit(
            f"この検定は1時間足を前提にしています（このデータは約{hours:.1f}時間足）。\n"
            "日足ではセッション内に1本しかないため、この戦略は成立しません。"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="事前登録した日中モメンタムの検定を実行する（パラメータは変更できません）"
    )
    parser.add_argument("--data", type=Path, required=True, help="1時間足のOHLCV CSV")
    args = parser.parse_args()

    df = _load(args.data)
    _require_hourly(df)

    print("=" * 70)
    print("事前登録した検定：ビットコインの日中モメンタム")
    print("=" * 70)
    print(f"データ   : {args.data}  ({len(df):,} バー)")
    print(f"期間     : {df.index[0]:%Y-%m-%d} 〜 {df.index[-1]:%Y-%m-%d}")
    print(f"戦略     : {STRATEGY.name}"
          f"（区切り{STRATEGY.session_start_hour}時 / 測る{STRATEGY.entry_bars}本 "
          f"/ 持つ{STRATEGY.exit_bars}本）")
    print(f"執行     : 成行・{COST.name}")
    print(f"試行数   : {N_TRIALS}（実データに対する評価の累計）")
    print("=" * 70)
    print()

    verdicts: list[tuple[str, str, str]] = []

    # --- 1. 先読み -------------------------------------------------------
    violations = check_causality(STRATEGY, df, cuts=5)
    verdicts.append(
        ("1. 先読みがない", PASS if not violations else FAIL,
         "なし" if not violations else str(violations[0]))
    )

    report = evaluate(run_backtest(df, STRATEGY, COST, CONFIG))
    print(report.summary())
    print()
    print("-" * 70)
    print()

    # --- 2. 買い持ちを上回る ---------------------------------------------
    beat = report.excess_over_buy_hold > 0
    verdicts.append(
        ("2. 買い持ちを上回る", PASS if beat else FAIL,
         f"{report.total_return * 100:+.2f}% vs 買い持ち {report.buy_hold_return * 100:+.2f}%")
    )

    # --- 3. 試行数を考慮したシャープ --------------------------------------
    print(multiple_testing_report(report, n_trials=N_TRIALS))
    print()
    print("-" * 70)
    print()
    from trading.src.growth import expected_max_sharpe

    threshold = expected_max_sharpe(
        N_TRIALS, max(report.n_observations, 2), report.periods_per_year
    )
    verdicts.append(
        ("3. 偶然の水準を超える", PASS if report.sharpe > threshold else FAIL,
         f"シャープ {report.sharpe:.2f} / 閾値 {threshold:.2f}")
    )

    # --- 4. ローテーション検定 -------------------------------------------
    print(f"同じ売買パターンを、でたらめな時点に {NULL_RUNS} 回置き直します")
    print()
    null = rotation_null(df, STRATEGY, COST, CONFIG, n_runs=NULL_RUNS)
    print(null.summary())
    print()
    print("-" * 70)
    print()
    verdicts.append(
        ("4. タイミングに意味がある",
         PASS if null.return_percentile >= ROTATION_PERCENTILE else FAIL,
         f"上位 {100 - null.return_percentile:.1f}%"
         f"（ずらすと中央値 {np.median(null.null_returns) * 100:+.2f}%）")
    )

    # --- 5. 期間を分けても通用する ----------------------------------------
    wf = walk_forward(df, STRATEGY, COST, CONFIG, n_windows=WALK_FORWARD_WINDOWS)
    print(wf.summary())
    print()
    print("-" * 70)
    print()

    thin = [r.trade_count for _, _, r in wf.windows if r.trade_count < MIN_TRADES_PER_WINDOW]
    beat_windows = sum(1 for _, _, r in wf.windows if r.excess_over_buy_hold > 0)
    if thin:
        wf_verdict, wf_note = UNKNOWN, (
            f"取引が {MIN_TRADES_PER_WINDOW} 回未満の期間が {len(thin)} 個"
            "（この分割では読めません）"
        )
    else:
        majority = beat_windows > len(wf.windows) / 2
        not_decaying = np.isnan(wf.decay_z) or wf.decay_z > DECAY_Z_THRESHOLD
        wf_verdict = PASS if (majority and not_decaying) else FAIL
        wf_note = (
            f"買い持ちに勝った期間 {beat_windows}/{len(wf.windows)}、"
            f"減衰スコア {wf.decay_z:+.2f}"
        )
    verdicts.append(("5. 期間を分けても通用する", wf_verdict, wf_note))

    # --- 判定 -------------------------------------------------------------
    print("=" * 70)
    print("事前登録した基準による判定")
    print("=" * 70)
    for name, verdict, note in verdicts:
        mark = {PASS: "○", FAIL: "×", UNKNOWN: "？"}[verdict]
        print(f"  {mark} {name:<26} {verdict:<6} {note}")
    print()

    failed = [v for _, v, _ in verdicts if v == FAIL]
    unknown = [v for _, v, _ in verdicts if v == UNKNOWN]

    if failed:
        print("→ **優位性は示されませんでした。**")
        print()
        print("  条件を変えて試したくなりますが、それは新しい検定になります。")
        print("  試すこと自体は構いません。ただし試行数を数え直してください。")
        print("  48通り試せば、優位性がゼロでも年率シャープ2.61が出ます（docs/05）。")
        print()
        print("  **見つからないと分かることも、資金を入れる前に得られる答えです。**")
        return 1

    if unknown:
        print("→ **判定できませんでした。** データが足りません。")
        print("  期間を増やすか、分割数を減らして測り直してください。")
        return 2

    print("→ **5つすべてを満たしました。**")
    print()
    print("  ただしこれは「過去のこの期間で、偶然では説明しにくい」というだけです。")
    print("  将来も続くことの根拠にはなりません。")
    print()
    print("  次に確かめること:")
    print("    - 指値で執行した場合（--order-type maker）。")
    print("      1セッション1回きりの戦略は、取り逃しが手数料の節約より高くつきます（docs/02）")
    print("    - 別の期間・別の取引所のデータでも同じ形になるか")
    print("    - 最小額で実際に動かしたときに、想定どおりの約定になるか")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
