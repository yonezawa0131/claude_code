"""adops CLI: ブランディング動画広告のプランニング/トラッキング/レポーティング。

使い方:
    python3 -m adops plan campaigns/<campaign_id>     # (1) 媒体プラン+シミュレーション生成
    python3 -m adops status [campaigns/<campaign_id>] # 進捗: 全案件横断 or 1案件詳細
    python3 -m adops report campaigns/<campaign_id>   # (5) report.md 生成
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from adops import io


def cmd_plan(args: argparse.Namespace) -> int:
    from adops.planner import build_plan

    campaign_dir = Path(args.campaign_dir)
    order = io.load_order(campaign_dir)
    benchmarks = io.load_benchmarks(args.benchmarks)
    plan = build_plan(order, benchmarks)
    path = io.save_plan(plan, campaign_dir)

    print(f"✔ プランを生成しました: {path}")
    print(f"\n■ 戦略方針\n{plan['strategy_summary']}\n")
    print("■ 媒体配分")
    for a in plan["allocations"]:
        print(f"  - {a['media_name']}: {io.fmt_yen(a['budget'])} ({io.fmt_pct(a['share'])})")
        print(f"      最適化: {a['optimization']}")
    total = plan["simulation"]["total"]
    print("\n■ シミュレーション（合計）")
    print(f"  imp: {io.fmt_num(total['impressions'])} / 視聴: {io.fmt_num(total['views'])}"
          f" / 完全視聴: {io.fmt_num(total['completed_views'])}")
    print(f"  推定リーチ: {io.fmt_num(total['reach'])} / CPM: {io.fmt_yen(total['cpm'])}"
          f" / CPV: {io.fmt_yen(total['cpv'])}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from adops.tracker import campaign_status, format_campaign_detail, format_status_table, portfolio_status

    if args.campaign_dir:
        status = campaign_status(Path(args.campaign_dir))
        print(format_campaign_detail(status))
    else:
        statuses = portfolio_status()
        if not statuses:
            print("plan.yaml を持つ案件がありません。まず `python3 -m adops plan` を実行してください。")
            return 1
        print(format_status_table(statuses))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from adops.reporter import write_report

    path = write_report(Path(args.campaign_dir))
    print(f"✔ レポートを生成しました: {path}")
    print("  考察・NEXT ACTION は自動生成の素案です。report-writer エージェントで肉付けしてください。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adops", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="order.yaml から媒体プラン+シミュレーションを生成")
    p_plan.add_argument("campaign_dir", help="案件ディレクトリ（campaigns/<campaign_id>）")
    p_plan.add_argument("--benchmarks", default=io.DEFAULT_BENCHMARKS, help="媒体マスタYAMLのパス")
    p_plan.set_defaults(func=cmd_plan)

    p_status = sub.add_parser("status", help="実績 vs シミュレーションの進捗確認")
    p_status.add_argument("campaign_dir", nargs="?", help="省略時は全案件横断ビュー")
    p_status.set_defaults(func=cmd_status)

    p_report = sub.add_parser("report", help="終了後レポート（report.md）を生成")
    p_report.add_argument("campaign_dir", help="案件ディレクトリ（campaigns/<campaign_id>）")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (io.SchemaError, FileNotFoundError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
