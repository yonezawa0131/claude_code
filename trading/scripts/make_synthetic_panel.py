#!/usr/bin/env python
"""銘柄横断の検定用に、複数銘柄の合成価格を作る。

単一銘柄の合成データ（make_synthetic.py）と役割が違う。
ここで作りたいのは**銘柄間の関係**であり、3つの成分に分けて生成する。

    リターン = ベータ × 市場 + テーマ + ノイズ

- **市場**: 全銘柄に共通する動き。強気相場・弱気相場を作る
- **ベータ**: 銘柄ごとの市場への感応度。ばらつきを持たせられる
- **テーマ**: 銘柄ごとに数週間続く固有の動き。**これが横断モメンタムの正体**

この3つを別々に操作できることが要点になる。とくに次の対照が要る。

    テーマなし × ベータのばらつきあり × 強気相場

この設定では、**上昇率上位の銘柄は単にベータの高い銘柄**でしかない。
上位群は市場に勝つが、それは予測力ではない。
検定器がこれを「優位性あり」と言ったら、その検定器は使えない。

使い方:
    # 横断モメンタムあり（陽性対照）
    python trading/scripts/make_synthetic_panel.py --assets 30 --days 600 --seed 1 \
        --theme 0.010 --out-dir trading/data/panel_positive

    # ベータのばらつきだけ（罠の対照）
    python trading/scripts/make_synthetic_panel.py --assets 30 --days 600 --seed 1 \
        --theme 0.0 --beta-spread 0.5 --market-drift 0.004 --out-dir trading/data/panel_beta
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

import numpy as np
import pandas as pd

CSV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
ANCHOR = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)

#: テーマの持続。0.97 なら半減期おおよそ23日。
#: 数週間続くので、1週間で順位づけして1週間持つ検定に噛み合う
THEME_PERSISTENCE = 0.97


def make_panel(
    n_assets: int,
    n_days: int,
    seed: int,
    theme_scale: float = 0.010,
    beta_spread: float = 0.0,
    market_drift: float = 0.0,
    market_vol: float = 0.030,
    idio_vol: float = 0.030,
    reversal: float = 0.0,
    reversal_period: int = 7,
) -> dict[str, pd.DataFrame]:
    """銘柄ごとの日足 OHLCV を作って返す。

    Parameters
    ----------
    theme_scale:
        テーマ成分の大きさ。**0にすると横断モメンタムが消える**
    beta_spread:
        ベータのばらつき。0なら全銘柄が同じ感応度
    market_drift:
        市場の日次ドリフト。正にすると強気相場になる
    reversal:
        **横断の反転**の強さ。前の期間に上がった銘柄ほど、次の期間で下がる。

        テーマの符号を反転させても反転相場にはならない。テーマは対称な
        ゆらぎなので、符号を変えても「持続する固有の動き」のままになり、
        順位づけはやはりモメンタムを拾う。

        反転を作るには、**前の期間のリターンそのものを次の期間から引く**必要がある。
    reversal_period:
        何日ぶんのリターンを、次の何日から引くか
    """
    if n_assets < 4:
        raise ValueError("銘柄数は4以上にしてください")
    rng = np.random.default_rng(seed)

    market = market_drift + market_vol * rng.standard_normal(n_days)
    betas = 1.0 + beta_spread * rng.standard_normal(n_assets)

    # テーマ: 銘柄ごとに、数週間かけてゆっくり変わる固有の傾き
    theme = np.zeros((n_days, n_assets))
    shock = rng.standard_normal((n_days, n_assets))
    keep = THEME_PERSISTENCE
    fresh = np.sqrt(1.0 - keep**2)
    for t in range(1, n_days):
        theme[t] = keep * theme[t - 1] + fresh * shock[t]

    idio = idio_vol * rng.standard_normal((n_days, n_assets))
    returns = market[:, None] * betas[None, :] + theme_scale * theme + idio

    if reversal != 0.0:
        # 前の期間の固有リターンを、次の期間から引く。
        # 市場成分は引かない（引くと市場そのものが反転してしまう）
        own = theme_scale * theme + idio
        for start in range(reversal_period, n_days - reversal_period + 1, reversal_period):
            prev = own[start - reversal_period : start].sum(axis=0)
            returns[start : start + reversal_period] -= reversal * prev / reversal_period

    log_prices = np.log(100_000.0) + np.cumsum(returns, axis=0)
    closes = np.exp(log_prices)

    timestamps = [ANCHOR + dt.timedelta(days=i) for i in range(n_days)]
    stamps = [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in timestamps]

    frames: dict[str, pd.DataFrame] = {}
    for j in range(n_assets):
        c = closes[:, j]
        o = np.empty(n_days)
        o[0] = 100_000.0
        o[1:] = c[:-1]
        wick = np.abs(rng.standard_normal(n_days)) * 0.004 * c
        frames[f"COIN{j:02d}"] = pd.DataFrame(
            {
                "timestamp": stamps,
                "open": np.round(o, 2),
                "high": np.round(np.maximum(o, c) + wick, 2),
                "low": np.round(np.minimum(o, c) - wick, 2),
                "close": np.round(c, 2),
                "volume": np.round(rng.lognormal(0, 0.5, n_days), 4),
            }
        )
    return frames


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="銘柄横断の検定用の合成パネルを作る")
    p.add_argument("--assets", type=int, required=True, help="銘柄数")
    p.add_argument("--days", type=int, required=True, help="日数")
    p.add_argument("--seed", type=int, required=True, help="乱数シード")
    p.add_argument("--theme", type=float, default=0.010,
                   help="テーマ成分の大きさ（0で横断モメンタムなし）")
    p.add_argument("--beta-spread", type=float, default=0.0, help="ベータのばらつき")
    p.add_argument("--market-drift", type=float, default=0.0, help="市場の日次ドリフト")
    p.add_argument("--reversal", type=float, default=0.0,
                   help="横断の反転の強さ（前期間に上がった銘柄が次期間に下がる）")
    p.add_argument("--out-dir", type=str, required=True, help="出力ディレクトリ")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        frames = make_panel(
            args.assets, args.days, args.seed,
            theme_scale=args.theme,
            beta_spread=args.beta_spread,
            market_drift=args.market_drift,
            reversal=args.reversal,
        )
    except ValueError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)
    for name, df in frames.items():
        df.to_csv(os.path.join(args.out_dir, f"{name}.csv"), index=False, columns=CSV_COLUMNS)
    print(f"保存しました: {args.out_dir} に {len(frames)} 銘柄 × {args.days} 日")
    print(f"  テーマ {args.theme} / ベータのばらつき {args.beta_spread} / "
          f"市場ドリフト {args.market_drift}")


if __name__ == "__main__":
    main()
