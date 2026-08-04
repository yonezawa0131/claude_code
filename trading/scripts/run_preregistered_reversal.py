#!/usr/bin/env python
"""事前登録した検定その3：銘柄横断の**反転**。

## この仮説がどこから来たか（正直に書く）

検定その2（モメンタム）を 2024-01-01〜2026-08-01 のデータで測ったとき、
**逆向きの兆候**が出た。

    上位 − 下位 = -0.742 %/期（133期）
    中央値 -0.673 %、最大の1期を除くと -1.041 %（外れ値では説明できない）
    無作為割当の対照で、観測値は乱数分布の**下位4.7%**
    前半 -0.012 % / 後半 -1.461 %（どちらも負）

つまり「直近上がった銘柄が、次の週に下がる」。文献が報告する向きとは反対になる。

**これは事後に見つけた仮説である。** だから、それを見つけたデータでは検証できない。
このスクリプトは 2024-01-01 以降のデータを渡されたら**実行を拒否する**。

## なぜ t 検定を主判定にしないか

検定その2 では、2つの検定が食い違った。

    t 検定       t = -1.07（有意でない）
    無作為割当   観測値は乱数分布の下位4.7%

t 検定は各期が独立同分布だと仮定するが、実際には市場全体の動きが
全期に共通で乗っている。無作為割当ではその共通部分が上位・下位の両方に入って
**相殺される**ので、こちらのほうが精密な検定になる。

観測された期間ごとの標準偏差は 8.00%、無作為割当の分布の標準偏差は 0.402%。
**2倍近く違う。** t 検定はこのデータには不適切だった。

だからこの検定では**無作為割当を主判定**にする。
これは結果を見てから基準を緩めたのではなく、
**検定その2 が残した、検定の妥当性についての独立な証拠**にもとづく変更になる。

## 事前登録した内容（2026年8月3日、2021〜2023年のデータを見る前に確定）

仮説:
    銘柄横断の**反転**。過去7日のリターンが低い銘柄が、次の7日で高い銘柄を上回る。

パラメータ（検定その2 と完全に同じ。ここを変えたら別の検定になる）:
    lookback = 7日 / holding = 7日 / n_groups = 5 / min_universe = 15

判定基準（**4つすべて**）:
    A. 上位 − 下位 が**負**であること（＝下位群が上位群を上回る）
    B. 無作為割当の対照で、観測値が乱数分布の**下位5%**に入ること
    C. 前半と後半で符号が一致すること
    D. 平均が少数の期に支配されていないこと
       （最大の1期を除いても符号が変わらない）

## 通っても、日本では取れない可能性が高い

反転を取るには上位群を**空売り**する必要がある。国内はレバレッジ手数料が
1日0.04%（週0.28%）。回転率0.79でテイカーなら週0.38%。
**合計0.66%に対して、観測された粗利は週0.742%。ほとんど残らない。**

現物ロングのみ（下位群を買う）なら空売りの費用は要らないが、
市場ベータを丸ごと負う。検定その2 の期間では市場自体が -16.8%/年だった。

**この検定に通ることは、儲かることを意味しない。**
意味するのは「順位づけに情報がある」ことだけになる。

使い方:
    # 仮説を見つけたのとは別の期間のデータを取る
    python trading/scripts/fetch_universe.py \
        --start 2021-01-01 --end 2023-12-31 --out-dir trading/data/universe_2021

    python trading/scripts/run_preregistered_reversal.py --dir trading/data/universe_2021
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.src.cross_section import (  # noqa: E402
    build_panel,
    cross_sectional_test,
    random_group_null,
)

# --- 事前登録した設定。検定その2 と同一 -------------------------------------
LOOKBACK = 7
HOLDING = 7
N_GROUPS = 5
MIN_UNIVERSE = 15
NULL_RUNS = 500
NULL_PERCENTILE = 5.0

#: 仮説を見つけた期間。**ここと重なるデータでは検証できない**
DISCOVERY_START = pd.Timestamp("2024-01-01", tz="UTC")

PASS, FAIL = "合格", "不合格"


def _load_panel(directory: Path) -> pd.DataFrame:
    files = sorted(directory.glob("*.csv"))
    if not files:
        raise SystemExit(f"CSVが見つかりません: {directory}")
    frames = {}
    for path in files:
        df = pd.read_csv(path)
        if "timestamp" not in df.columns:
            continue
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
        frames[path.stem] = df.set_index("timestamp").sort_index()
    if len(frames) < MIN_UNIVERSE:
        raise SystemExit(
            f"{len(frames)} 銘柄しかありません。最低 {MIN_UNIVERSE} 銘柄が要ります。\n"
            "  古い期間ほど上場銘柄が少なくなります。"
        )
    return build_panel(frames)


def main() -> int:
    p = argparse.ArgumentParser(
        description="事前登録した銘柄横断反転の検定（パラメータは変更できません）"
    )
    p.add_argument("--dir", type=Path, required=True, help="銘柄ごとのCSVが入ったディレクトリ")
    args = p.parse_args()

    panel = _load_panel(args.dir)

    # **仮説を見つけたデータでは検証できない。** ここは譲れない
    if panel.index.max() >= DISCOVERY_START:
        raise SystemExit(
            f"このデータは {panel.index.max():%Y-%m-%d} まで含んでいます。\n"
            f"この仮説は {DISCOVERY_START:%Y-%m-%d} 以降のデータを見て思いついたものなので、\n"
            "**そこと重なる期間では検証になりません。**\n"
            f"  {DISCOVERY_START:%Y-%m-%d} より前で終わるデータを用意してください:\n"
            "  python trading/scripts/fetch_universe.py \\\n"
            "      --start 2021-01-01 --end 2023-12-31 --out-dir trading/data/universe_2021"
        )

    ppy = 365.0 / HOLDING
    print("=" * 72)
    print("事前登録した検定その3：銘柄横断の反転")
    print("=" * 72)
    print(f"銘柄数   : {panel.shape[1]}")
    print(f"期間     : {panel.index[0]:%Y-%m-%d} 〜 {panel.index[-1]:%Y-%m-%d}"
          f"（{len(panel)} 日）")
    print(f"設定     : ルックバック {LOOKBACK}日 / 保有 {HOLDING}日 / {N_GROUPS}分位")
    print("")
    print("この仮説は 2024-01〜2026-08 のデータで見つけたもので、")
    print("**いま測っているのはそれとは別の期間**になります。")
    print("=" * 72)
    print()

    result = cross_sectional_test(
        panel, lookback=LOOKBACK, holding=HOLDING,
        n_groups=N_GROUPS, min_universe=MIN_UNIVERSE,
    )
    print(result.summary(periods_per_year=ppy))
    print()
    print(result.robustness())
    print()

    n_periods = len(result.spread.dropna())
    if n_periods < 30:
        print(f"→ 期間が {n_periods} 期しかありません。**判定不能。**")
        return 2

    print("-" * 72)
    print()
    print(f"銘柄を無作為に分け直す対照を {NULL_RUNS} 回まわします")
    print()
    null = random_group_null(
        panel, lookback=LOOKBACK, holding=HOLDING, n_groups=N_GROUPS,
        min_universe=MIN_UNIVERSE, n_runs=NULL_RUNS,
    )
    print(null.summary())
    print()
    print("-" * 72)
    print()

    first, second = result.split_halves()
    for label, part in (("前半", first), ("後半", second)):
        print(f"  {label}（{part.index[0]:%Y-%m-%d}〜{part.index[-1]:%Y-%m-%d}）: "
              f"上位−下位 {part.mean() * 100:+.3f} %/期（{len(part)} 期）")
    print()

    s = result.spread.dropna()
    without = s.drop(s.abs().idxmax())

    verdicts = [
        ("A. 上位 − 下位 が負", PASS if s.mean() < 0 else FAIL,
         f"{s.mean() * 100:+.3f} %/期"),
        ("B. 無作為割当の下位5%", PASS if null.percentile <= NULL_PERCENTILE else FAIL,
         f"下位 {null.percentile:.1f} %"),
        ("C. 前半と後半で符号が一致", PASS if first.mean() * second.mean() > 0 else FAIL,
         f"前半 {first.mean() * 100:+.3f} % / 後半 {second.mean() * 100:+.3f} %"),
        ("D. 1期に支配されていない", PASS if s.mean() * without.mean() > 0 else FAIL,
         f"最大の1期を除くと {without.mean() * 100:+.3f} %"),
    ]

    print("=" * 72)
    print("事前登録した基準による判定")
    print("=" * 72)
    for name, verdict, note in verdicts:
        print(f"  {'○' if verdict == PASS else '×'} {name:<26} {verdict:<6} {note}")
    print()

    if any(v == FAIL for _, v, _ in verdicts):
        print("→ **別の期間では再現しませんでした。**")
        print()
        print("  2024〜2026年に見えた反転は、その期間に固有のものだったことになります。")
        print("  **同じデータで見つけた仮説が、別のデータで消える。**")
        print("  これは事後の発見に最もよく起きる形です。")
        return 1

    print("→ **別の期間でも再現しました。**")
    print()
    print("  ただし、これは「順位づけに情報がある」ことしか意味しません。")
    print("  日本で取れるかは別問題です:")
    print("    - 反転を取るには上位群の空売りが要る。レバレッジ手数料は週0.28%")
    print("    - 回転率0.79でテイカーなら週0.38%。合計0.66%")
    print("    - 観測された粗利が週0.742%なら、**残るのは0.08%**")
    print("    - 現物ロングのみ（下位群を買う）なら空売り費用は不要だが、")
    print("      市場ベータを丸ごと負う")
    print()
    print("  次は run_backtest.py 側で、コストを入れて実装可能性を測ること。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
