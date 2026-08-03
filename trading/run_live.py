#!/usr/bin/env python
"""執行本体。目標の保有に近づけるための注文を出す。

## 動き方

    1. 取引所から**現在の保有を読む**（記憶に頼らない）
    2. 戦略から目標の保有を求める
    3. 差分を注文にする
    4. 関門を通す
    5. 通れば出す。通らなければ止めて理由を出す
    6. すべて記録する

毎回1から現在地を読み直すので、前回落ちていても、手で売買していても、
別のマシンから動かしても、同じ判断になる。

## 既定はペーパー

本番は `--live` を明示し、さらに関門をすべて通ったときだけ動く。
関門には「事前登録した検定に合格しているか」が含まれる。

**優位性のない戦略を自動化すると、損失は確実に、正確に、休みなく実現する。**
この基盤が実データで測った5戦略は、元本30万円で平均11.5万円を失う成績だった。
自動化していれば、その11.5万円は取りこぼしなく失われていた。

## 使い方

    # 配線の確認（発注しない）
    python trading/run_live.py --strategy equal_weight_btc --paper-capital 300000

    # 定期実行（cron から。週次リバランスなら週1回で足りる）
    0 0 * * 1 cd ~/claude_code && .venv-trading/bin/python trading/run_live.py ...

    # 本番（関門を全部通った場合のみ動く）
    BITBANK_API_KEY=... BITBANK_API_SECRET=... \
        python trading/run_live.py --strategy ... --live
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.src.execution.broker import (  # noqa: E402
    BitbankBroker,
    BrokerError,
    PaperBroker,
)
from trading.src.execution.guards import (  # noqa: E402
    GuardContext,
    Limits,
    ValidationRecord,
    check,
    describe,
)
from trading.src.execution.journal import Journal  # noqa: E402
from trading.src.execution.reconcile import (  # noqa: E402
    TargetPortfolio,
    build_orders,
    current_weights,
    exposure_jpy,
)

#: 目標を決める関数。戦略ごとにここへ足す。
#: **どれも、検証を通るまで本番では動かない。**
def _equal_weight_btc(_prices: dict[str, float]) -> TargetPortfolio:
    """BTCを全額持つ。買い持ちそのもの。

    この基盤が実データで測った範囲では、**これが最も成績の良かった方針**になる
    （年17.9%、ただし最大下落 −50.2%）。
    比較の基準線として、また配線の確認用として置いてある。
    """
    return TargetPortfolio(weights={"btc_jpy": 1.0})


def _half_btc(_prices: dict[str, float]) -> TargetPortfolio:
    """BTCを半分、残りは現金。下落耐性を半分にする。"""
    return TargetPortfolio(weights={"btc_jpy": 0.5})


TARGETS = {
    "equal_weight_btc": _equal_weight_btc,
    "half_btc": _half_btc,
}


def main() -> int:
    p = argparse.ArgumentParser(description="目標の保有に近づける")
    p.add_argument("--strategy", required=True, choices=sorted(TARGETS),
                   help="目標を決める方針")
    p.add_argument("--live", action="store_true",
                   help="本番で発注する（関門をすべて通った場合のみ動きます）")
    p.add_argument("--pairs", default="btc_jpy",
                   help="価格を取る銘柄（カンマ区切り）")
    p.add_argument("--state", type=Path, default=Path("trading/data/paper_state.json"),
                   help="ペーパー用の保有状態ファイル")
    p.add_argument("--paper-capital", type=float, default=0.0,
                   help="ペーパーの初期資金。状態ファイルが空のときだけ入れる")
    p.add_argument("--journal", type=Path, default=Path("trading/data/journal.jsonl"),
                   help="記録の出力先")
    p.add_argument("--validation", type=Path, default=Path("trading/data/validation.json"),
                   help="事前登録した検定の合格記録")
    p.add_argument("--initial-equity", type=float, default=0.0,
                   help="運用開始時の資産（円）。損失の上限判定に使う")
    p.add_argument("--max-per-run", type=float, default=50_000.0)
    p.add_argument("--max-per-order", type=float, default=20_000.0)
    p.add_argument("--max-exposure", type=float, default=100_000.0)
    p.add_argument("--market", action="store_true",
                   help="指値ではなく成行で出す（往復コストが約9倍になります）")
    args = p.parse_args()

    journal = Journal(args.journal)
    pairs = [s.strip() for s in args.pairs.split(",") if s.strip()]
    mode = "本番" if args.live else "ペーパー"

    print("=" * 70)
    print(f"執行  {mode}  戦略: {args.strategy}")
    print("=" * 70)

    # --- 取引所につなぐ --------------------------------------------------
    if args.live:
        key = os.environ.get("BITBANK_API_KEY")
        secret = os.environ.get("BITBANK_API_SECRET")
        if not key or not secret:
            print("エラー: BITBANK_API_KEY と BITBANK_API_SECRET を環境変数で渡してください",
                  file=sys.stderr)
            return 1
        broker = BitbankBroker(api_key=key, api_secret=secret)
        print(f"接続  : {broker.name}")
        if broker.unverified:
            print("  ※ この発注経路は実物に対して検証されていません。")
            print("     最小額で1回動かし、取引所の画面と突き合わせてください。")
    else:
        broker = PaperBroker(state_path=args.state)
        if args.paper_capital > 0 and not broker.fetch_balances().get("jpy"):
            broker.deposit("jpy", args.paper_capital)
            print(f"ペーパーに {args.paper_capital:,.0f} 円を置きました")
        print(f"接続  : {broker.name}")

    # --- 1. 現在地を読む（記憶に頼らない）--------------------------------
    try:
        prices = {pair: broker.fetch_price(pair) for pair in pairs}
    except BrokerError as exc:
        # ペーパーは価格を持たないので、公開APIから取ってくる
        if args.live:
            print(f"エラー: 価格を取得できません。{exc}", file=sys.stderr)
            return 1
        from trading.src.execution.broker import BitbankBroker as _Pub
        pub = _Pub(api_key="", api_secret="")
        try:
            prices = {pair: pub.fetch_price(pair) for pair in pairs}
        except BrokerError as exc2:
            print(f"エラー: 価格を取得できません。{exc2}", file=sys.stderr)
            return 1
        broker.set_prices(prices)

    balances = broker.fetch_balances()
    weights, equity = current_weights(balances, prices)
    exposure = exposure_jpy(balances, prices)

    print()
    print(f"現在の総資産: {equity:,.0f} 円")
    for pair, w in sorted(weights.items()):
        print(f"  {pair:<12} {w * 100:6.2f} %  ({balances.get(pair.split('_')[0], 0):.8f})")
    print(f"  {'現金':<12} {balances.get('jpy', 0.0) / equity * 100 if equity else 0:6.2f} %")

    journal.write("state", mode=mode, equity=equity, balances=balances, prices=prices)

    # --- 2〜3. 目標と差分 -------------------------------------------------
    target = TARGETS[args.strategy](prices)
    orders, _ = build_orders(
        target, balances, prices,
        limit_offset=None if args.market else 0.0005,
    )

    print()
    print("目標:")
    for pair, w in sorted(target.weights.items()):
        print(f"  {pair:<12} {w * 100:6.2f} %")

    print()
    if not orders:
        print("差分はありません。何もしません。")
        journal.write("no_action", strategy=args.strategy)
        return 0

    print(f"出す注文（{len(orders)} 件）:")
    for o in orders:
        kind = "指値" if o.price else "成行"
        print(f"  {o.side:<5} {o.pair:<12} {o.amount:.8f}  "
              f"{kind} {o.price if o.price else prices[o.pair]:,.0f}  "
              f"≒ {o.notional(prices[o.pair]):,.0f} 円")

    # --- 4. 関門 ----------------------------------------------------------
    validation = None
    if args.validation.exists():
        try:
            validation = ValidationRecord.load(args.validation)
        except (KeyError, ValueError) as exc:
            print(f"\n検証記録を読めません: {exc}", file=sys.stderr)

    limits = Limits(
        max_notional_per_run=args.max_per_run,
        max_notional_per_order=args.max_per_order,
        max_total_exposure=args.max_exposure,
    )
    violations = check(GuardContext(
        strategy=args.strategy, orders=orders, prices=prices,
        equity=equity, initial_equity=args.initial_equity or equity,
        exposure=exposure, limits=limits, validation=validation,
    ))

    print()
    print("-" * 70)
    print(describe(violations))
    print("-" * 70)
    journal.write("guards", strategy=args.strategy,
                  violations=[str(v) for v in violations],
                  orders=[o.__dict__ for o in orders])

    # --- 5. 執行 ----------------------------------------------------------
    if not args.live:
        print()
        print("ペーパーなので、そのまま反映します（発注はしていません）。")
        for o in orders:
            try:
                broker.place_order(o)
                journal.write("paper_fill", **o.__dict__)
            except BrokerError as exc:
                print(f"  スキップ: {o.pair} {o.side} — {exc}")
                journal.write("paper_reject", reason=str(exc), **o.__dict__)
        after = broker.fetch_balances()
        _, new_equity = current_weights(after, prices)
        print(f"\n反映後の総資産: {new_equity:,.0f} 円")
        return 0

    if violations:
        print()
        print("**本番では実行しません。** 上の理由を解消してください。")
        return 2

    print()
    print("関門を通過しました。発注します。")
    placed, failed = 0, 0
    for o in orders:
        try:
            response = broker.place_order(o)
            journal.write("order_placed", response=response, **o.__dict__)
            print(f"  出しました: {o.side} {o.pair} {o.amount:.8f}")
            placed += 1
        except BrokerError as exc:
            journal.write("order_failed", reason=str(exc), **o.__dict__)
            print(f"  失敗: {o.side} {o.pair} — {exc}", file=sys.stderr)
            failed += 1

    print()
    print(f"発注 {placed} 件 / 失敗 {failed} 件。記録: {args.journal}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
