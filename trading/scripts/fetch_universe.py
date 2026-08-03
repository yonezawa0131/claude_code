#!/usr/bin/env python
"""銘柄横断の検定用に、取引所の全JPY建て銘柄の日足を取得する。

## 銘柄リストを書き下さない理由

上場銘柄は増えるし、消える。ここに一覧を書けば、書いた時点から古くなる。
そして**存在しない銘柄名で404を出すより、取引所に聞くほうが速くて正しい。**

このスクリプトは `https://public.bitbank.cc/tickers` から
現在取引されている銘柄を取得し、JPY建てのものを対象にする。

## 生存バイアスについて

**現在の上場銘柄しか取れない。** 途中で上場廃止になった銘柄は入らない。
消えるのはたいてい値下がりした銘柄なので、この方法で集めたデータは
**成績が上振れする**。結果を読むときに必ず割り引くこと。

このバイアスは、上位群と下位群の差（spread）を見る場合はいくらか緩和される
（消えた銘柄は下位群に入っていたはずなので、spread は控えめに出る）。
それでも消えるわけではない。

使い方:
    python trading/scripts/fetch_universe.py \
        --start 2024-01-01 --end 2026-08-01 --out-dir trading/data/universe
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.scripts.fetch_ohlcv import (  # noqa: E402
    CSV_COLUMNS,
    FetchError,
    HttpStatusError,
    _http_get,
    _postprocess,
    _save_csv,
    fetch_ohlcv,
)

TICKERS_URL = "https://public.bitbank.cc/tickers"


def discover_pairs(quote: str = "jpy") -> list[str]:
    """取引所から、いま取引できる銘柄の一覧を取得する。"""
    payload = json.loads(_http_get(TICKERS_URL))
    if payload.get("success") != 1:
        raise FetchError(f"銘柄一覧を取得できませんでした: {payload}")
    pairs = [t["pair"] for t in payload.get("data", []) if t.get("pair", "").endswith(f"_{quote}")]
    return sorted(set(pairs))


def _parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    p = argparse.ArgumentParser(description="全JPY建て銘柄の日足を取得する")
    p.add_argument("--start", required=True, type=_parse_date, help="取得開始日 YYYY-MM-DD")
    p.add_argument("--end", required=True, type=_parse_date, help="取得終了日 YYYY-MM-DD")
    p.add_argument("--out-dir", required=True, help="出力ディレクトリ")
    p.add_argument("--interval", default="1day", help="足種（既定 1day）")
    p.add_argument("--min-bars", type=int, default=200,
                   help="この本数に満たない銘柄は保存しない（上場が新しすぎる）")
    args = p.parse_args()

    try:
        pairs = discover_pairs()
    except (FetchError, HttpStatusError) as exc:
        print(f"エラー: 銘柄一覧を取得できませんでした。{exc}", file=sys.stderr)
        print("  --diagnose で疎通を確認してください:", file=sys.stderr)
        print("  python trading/scripts/fetch_ohlcv.py --exchange bitbank "
              "--pair btc_jpy --diagnose", file=sys.stderr)
        return 1

    print(f"取引できるJPY建て銘柄: {len(pairs)} 種類")
    print(f"  {', '.join(pairs)}")
    print()
    print(f"{args.interval} を {args.start} 〜 {args.end} で取得します。")
    print("=" * 70)

    os.makedirs(args.out_dir, exist_ok=True)
    saved, skipped, failed = [], [], []

    for i, pair in enumerate(pairs, start=1):
        print(f"\n[{i}/{len(pairs)}] {pair}")
        try:
            df = fetch_ohlcv("bitbank", pair, args.interval, args.start, args.end)
            df = _postprocess(df, args.start, args.end)
        except (FetchError, HttpStatusError) as exc:
            print(f"  取得できませんでした: {exc}")
            failed.append(pair)
            continue

        if len(df) < args.min_bars:
            print(f"  {len(df)} 本しかないため保存しません（上場が新しすぎます）")
            skipped.append(pair)
            continue

        _save_csv(df, os.path.join(args.out_dir, f"{pair}.csv"))
        saved.append(pair)

    print()
    print("=" * 70)
    print(f"保存 {len(saved)} 銘柄 / 本数不足 {len(skipped)} / 失敗 {len(failed)}")
    if skipped:
        print(f"  本数不足: {', '.join(skipped)}")
    if failed:
        print(f"  失敗    : {', '.join(failed)}")
    print()
    print("※ ここに集まるのは**いま上場している銘柄だけ**です。")
    print("  途中で上場廃止になった銘柄は入らないので、成績は上振れします。")

    if len(saved) < 10:
        print()
        print("エラー: 10銘柄未満では横断検定になりません。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
