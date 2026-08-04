#!/usr/bin/env python
"""事前登録した検定その2：銘柄横断モメンタム。

## なぜこれが「別の仮説」なのか

これまで実データで測って全滅したのは、すべて
**1つの資産の価格履歴から、その資産の将来を当てる**という形だった。
そして実際、その情報源には何もなかった。自己相関はどの時間軸でもゼロ、
日中モメンタムは検出力100%で否定された。

ここで使う情報源は違う。**他の銘柄の値動き**を使う。

## 事前登録した内容（2026年8月3日、横断データを1行も見る前に確定）

仮説:
    Guo, Sang, Tu & Wang (2024, Journal of Economic Dynamics and Control) ほか。
    暗号資産の将来リターンは、他の暗号資産の過去リターンで予測できる。
    機構は「共通ショック＋限定的注意による情報伝播の遅れ」。
    複数の研究が、モメンタムは1〜4週間で優勢、1か月超で反転すると報告している。

パラメータ（すべて文献由来。このデータからは選ばない）:
    lookback  = 7日    順位づけに使う過去の期間
    holding   = 7日    保有期間。文献が報告する「1〜4週間」の下端
    n_groups  = 5      五分位。上位20%と下位20%
    skip      = 0      間を空けない（余計なパラメータを増やさない）
    min_universe = 15  この銘柄数を下回る時点は使わない

判定基準:

    【第一関門：信号があるか】コストも執行も考えない。純粋な予測力。
      A. 上位 − 下位 の平均が正で、t > 2
      B. 無作為割当の対照で上位5%に入る
      C. 前半と後半で符号が一致する

    【第二関門：日本で実装できるか】第一関門を通った場合のみ評価する。
      D. bitbank のテイカー手数料（片道0.12%）を引いても正
      E. 現物ロングのみ（上位群 − 市場）でも、コスト控除後に正

    A〜C が1つでも欠ければ、そこで終わり。D・E は見ない。
    **信号がないものの実装を検討するのは、順序が逆になる。**

使い方:
    python trading/scripts/fetch_universe.py \
        --start 2024-01-01 --end 2026-08-01 --out-dir trading/data/universe
    python trading/scripts/run_preregistered_cross.py --dir trading/data/universe
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

# --- 事前登録した設定。ここを変えたら、それは別の検定 ----------------------
LOOKBACK = 7
HOLDING = 7
N_GROUPS = 5
MIN_UNIVERSE = 15
NULL_RUNS = 300
NULL_PERCENTILE = 95.0

#: bitbank の実料率（2026年8月時点の公開情報）
TAKER_PER_SIDE = 0.0012
MAKER_PER_SIDE = -0.0002

PASS, FAIL, UNKNOWN = "合格", "不合格", "判定不能"


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
            f"{len(frames)} 銘柄しかありません。"
            f"この検定には最低 {MIN_UNIVERSE} 銘柄が要ります"
        )
    return build_panel(frames)


def _t(series: pd.Series) -> float:
    s = series.dropna()
    if len(s) < 3 or s.std(ddof=1) == 0:
        return float("nan")
    return float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s))))


def main() -> int:
    p = argparse.ArgumentParser(
        description="事前登録した銘柄横断モメンタムの検定（パラメータは変更できません）"
    )
    p.add_argument("--dir", type=Path, required=True, help="銘柄ごとのCSVが入ったディレクトリ")
    args = p.parse_args()

    panel = _load_panel(args.dir)
    ppy = 365.0 / HOLDING

    print("=" * 72)
    print("事前登録した検定その2：銘柄横断モメンタム")
    print("=" * 72)
    print(f"銘柄数   : {panel.shape[1]}")
    print(f"期間     : {panel.index[0]:%Y-%m-%d} 〜 {panel.index[-1]:%Y-%m-%d}"
          f"（{len(panel)} 日）")
    print(f"設定     : ルックバック {LOOKBACK}日 / 保有 {HOLDING}日 / {N_GROUPS}分位")
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
        print("  データを増やしてください。")
        return 2

    # 検出力: この標本で、どれだけの効果なら検出できたか
    sd = result.spread.std(ddof=1)
    detectable = 1.96 * sd / np.sqrt(n_periods)
    print(f"  検出力: この {n_periods} 期で検出できる最小の効果は "
          f"{detectable * 100:.3f} %/期（年率 {detectable * ppy * 100:.1f} %）")
    print()
    print("-" * 72)
    print()

    verdicts: list[tuple[str, str, str]] = []

    # --- A. 信号の有無 ---------------------------------------------------
    t_spread = _t(result.spread)
    verdicts.append((
        "A. 上位 − 下位 が正で t>2",
        PASS if (result.spread.mean() > 0 and t_spread > 2.0) else FAIL,
        f"平均 {result.spread.mean() * 100:+.3f} %/期、t = {t_spread:+.2f}",
    ))

    # --- B. 無作為割当の対照 ---------------------------------------------
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
    verdicts.append((
        "B. 無作為割当で再現しない",
        PASS if null.percentile >= NULL_PERCENTILE else FAIL,
        f"上位 {100 - null.percentile:.1f} %",
    ))
    if null.percentile <= 100 - NULL_PERCENTILE:
        print("  ※ 逆向きに外れています。順位づけには情報があるが、")
        print("     **文献が報告する向きとは反対**（上位が下位に負ける）。")
        print("     これは事前登録した仮説ではないので、ここでは合格にしません。")
        print("     追う場合は新しい検定として、別のデータで測り直すこと。")
        print()

    # --- C. 前半と後半で符号が一致 ---------------------------------------
    # **同じ検定の結果を分けるだけにする。** パネルを切って測り直すと、
    # 週の区切りがずれて全期間とは別の週を測ることになる
    first, second = result.split_halves()
    signs = [first.mean(), second.mean()]
    for label, part in (("前半", first), ("後半", second)):
        print(f"  {label}（{part.index[0]:%Y-%m-%d}〜{part.index[-1]:%Y-%m-%d}）: "
              f"上位−下位 {part.mean() * 100:+.3f} %/期（{len(part)} 期）")
    combined = pd.concat([first, second]).mean()
    print(f"  合わせると {combined * 100:+.3f} %/期  "
          f"（全期間 {result.spread.mean() * 100:+.3f} %/期）")
    print()
    consistent = all(np.isfinite(s) for s in signs) and signs[0] * signs[1] > 0
    verdicts.append((
        "C. 前半と後半で符号が一致",
        PASS if consistent else FAIL,
        f"前半 {signs[0] * 100:+.3f} % / 後半 {signs[1] * 100:+.3f} %",
    ))

    gate1 = [v for _, v, _ in verdicts if v == FAIL]

    # --- D, E. 実装（第一関門を通った場合のみ）----------------------------
    if not gate1:
        taker = cross_sectional_test(
            panel, lookback=LOOKBACK, holding=HOLDING, n_groups=N_GROUPS,
            min_universe=MIN_UNIVERSE, cost_per_side=TAKER_PER_SIDE,
        )
        verdicts.append((
            "D. テイカー手数料を引いても正",
            PASS if taker.spread.mean() > 0 else FAIL,
            f"{taker.spread.mean() * 100:+.3f} %/期"
            f"（年率 {taker.spread.mean() * ppy * 100:+.1f} %）",
        ))
        verdicts.append((
            "E. 現物ロングのみでも正",
            PASS if taker.excess.mean() > 0 else FAIL,
            f"上位−市場 {taker.excess.mean() * 100:+.3f} %/期"
            f"（年率 {taker.excess.mean() * ppy * 100:+.1f} %）",
        ))

    # --- 判定 -------------------------------------------------------------
    print("=" * 72)
    print("事前登録した基準による判定")
    print("=" * 72)
    for name, verdict, note in verdicts:
        mark = {PASS: "○", FAIL: "×", UNKNOWN: "？"}[verdict]
        print(f"  {mark} {name:<26} {verdict:<6} {note}")
    print()

    if gate1:
        print("→ **第一関門で不合格。信号がありません。**")
        print()
        print("  実装（コスト・執行）は評価しません。")
        print("  信号がないものの実装を検討するのは、順序が逆になります。")
        print()
        print("  ルックバックや保有期間を変えたくなりますが、それは新しい検定です。")
        print("  試行数を数え直してください。")
        return 1

    if any(v == FAIL for _, v, _ in verdicts):
        print("→ **信号はあるが、日本の条件では取り切れません。**")
        print()
        print("  第一関門（A〜C）を通ったのは意味があります。")
        print("  週次リバランスは約定機会が168時間あるので、指値（メイカー）が使えます。")
        print(f"  bitbank のメイカーは {MAKER_PER_SIDE * 100:+.2f}%（受け取り）です。")
        print("  次に確かめるべきは、指値でどこまで約定するかになります。")
        return 3

    print("→ **すべての基準を満たしました。**")
    print()
    print("  ただしこれは「この期間で、偶然では説明しにくい」というだけです。")
    print("  次に確かめること:")
    print("    - 生存バイアス。いま上場している銘柄しか見ていません")
    print("    - 流動性。薄い銘柄は板が動くので、想定どおりに約定しません")
    print("    - ショートの費用。国内はレバレッジ手数料が1日0.04%（年約14.6%）")
    print("    - 最小額で実際に動かしたときに、想定どおりの約定になるか")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
