#!/usr/bin/env python
"""バックテストを実行して結果を表示する。

使い方の例:

    # 合成データでエンジンの挙動を見る（ネットワーク不要）
    python trading/scripts/make_synthetic.py --bars 4000 --regime mixed --out trading/data/synthetic.csv
    python trading/run_backtest.py --data trading/data/synthetic.csv --strategy ema_atr

    # 実データで検証する（先に手元で fetch_ohlcv.py を実行してCSVを用意）
    python trading/run_backtest.py --data trading/data/btc_jpy_1hour.csv \
        --strategy ema_atr --cost gmo --capital 300000 --walk-forward 6

    # 「1日いくら」が元本に対して何%なのかを見る
    python trading/run_backtest.py --show-required-return
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.src.backtest import BacktestConfig, run_backtest
from trading.src.costs import PRESETS, OrderType, breakeven_move
from trading.src.metrics import evaluate
from trading.src.strategy import STRATEGIES
from trading.src.validate import check_causality, required_return_table, walk_forward


def load_ohlcv(path: Path) -> pd.DataFrame:
    """CSVを読み込んでバックテスト用のDataFrameにする。"""
    if not path.exists():
        raise SystemExit(
            f"データが見つかりません: {path}\n"
            "先に scripts/make_synthetic.py（合成データ）か "
            "scripts/fetch_ohlcv.py（実データ・要ネットワーク）で作成してください。"
        )
    df = pd.read_csv(path)
    if "timestamp" not in df.columns:
        raise SystemExit("CSVに timestamp 列がありません")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def build_strategy(name: str, allow_short: bool):
    if name not in STRATEGIES:
        raise SystemExit(f"未知の戦略: {name}（利用可能: {', '.join(STRATEGIES)}）")
    cls = STRATEGIES[name]
    kwargs = {}
    if "allow_short" in getattr(cls, "__dataclass_fields__", {}):
        kwargs["allow_short"] = allow_short
    return cls(**kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description="バックテストの実行")
    parser.add_argument("--data", type=Path, help="OHLCVのCSVファイル")
    parser.add_argument(
        "--strategy", default="ema_atr", help=f"戦略名（{', '.join(STRATEGIES)}）"
    )
    parser.add_argument(
        "--cost", default="gmo", help=f"コストモデル（{', '.join(PRESETS)}）"
    )
    parser.add_argument("--capital", type=float, default=300_000.0, help="初期資金（円）")
    parser.add_argument(
        "--fraction", type=float, default=1.0, help="1トレードに投じる資金の割合"
    )
    parser.add_argument(
        "--order-type", default="taker", choices=["taker", "maker"], help="執行方法"
    )
    parser.add_argument("--allow-short", action="store_true", help="ショートを許可する")
    parser.add_argument(
        "--leverage", type=float, default=1.0, help="レバレッジ（国内個人は2.0が上限）"
    )
    parser.add_argument(
        "--walk-forward", type=int, default=0, help="期間分割数（0なら実施しない）"
    )
    parser.add_argument(
        "--compare-all", action="store_true", help="全戦略を同条件で比較する"
    )
    parser.add_argument(
        "--show-required-return",
        action="store_true",
        help="「1日いくら」を元本に対する率に翻訳した表を出す",
    )
    args = parser.parse_args()

    if args.show_required_return:
        print(required_return_table())
        return 0

    if args.data is None:
        parser.error("--data を指定してください（または --show-required-return）")

    df = load_ohlcv(args.data)
    cost = PRESETS.get(args.cost)
    if cost is None:
        raise SystemExit(f"未知のコストモデル: {args.cost}")

    order_type = OrderType(args.order_type)
    config = BacktestConfig(
        initial_capital=args.capital,
        position_fraction=args.fraction,
        order_type=order_type,
        allow_short=args.allow_short,
        leverage=args.leverage,
    )

    print("=" * 68)
    print(f"データ       : {args.data}  ({len(df):,} バー)")
    print(f"期間         : {df.index[0]:%Y-%m-%d} 〜 {df.index[-1]:%Y-%m-%d}")
    print(f"コスト       : {cost.name}")
    print(f"  往復コスト : {cost.round_trip_rate(order_type) * 100:.3f} %")
    print(f"  損益分岐   : 1回の取引で {breakeven_move(cost, order_type) * 100:.3f} % 動く必要がある")
    if cost.unverified:
        print(f"  ※ 未確認の数字を含みます: {cost.note}")
    print("=" * 68)
    print()

    names = list(STRATEGIES) if args.compare_all else [args.strategy]
    reports = []
    for name in names:
        strategy = build_strategy(name, args.allow_short)

        violations = check_causality(strategy, df, cuts=4)
        if violations:
            print(f"[{name}] 先読みが検出されました。結果は無効です:")
            for v in violations[:3]:
                print(f"  {v}")
            print()
            continue

        result = run_backtest(df, strategy, cost, config)
        report = evaluate(result)
        reports.append((name, report))
        print(report.summary())
        print()
        print("-" * 68)
        print()

    if args.walk_forward and not args.compare_all:
        strategy = build_strategy(args.strategy, args.allow_short)
        wf = walk_forward(df, strategy, cost, config, n_windows=args.walk_forward)
        print(wf.summary())
        print()

    if args.compare_all and reports:
        print("まとめ（買い持ちとの差の順）")
        print()
        header = f"{'戦略':<22}{'総リターン':>12}{'買い持ち差':>12}{'取引':>7}{'最大DD':>9}"
        print(header)
        print("-" * len(header))
        for name, rep in sorted(reports, key=lambda x: -x[1].excess_over_buy_hold):
            print(
                f"{rep.strategy_name:<22}"
                f"{rep.total_return * 100:>11.2f}%"
                f"{rep.excess_over_buy_hold * 100:>11.2f}%"
                f"{rep.trade_count:>7}"
                f"{rep.max_drawdown * 100:>8.1f}%"
            )
        print()
        print("買い持ち差がマイナスの戦略は、ただ持っているより成績が悪いということです。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
