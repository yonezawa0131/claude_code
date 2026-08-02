#!/usr/bin/env python
"""
仮想通貨取引所（bitbank / GMOコイン）からOHLCV（ローソク足）データを取得し、
CSVファイルとして保存するスクリプト。

対応取引所:
    - bitbank   : https://public.bitbank.cc/{pair}/candlestick/{type}/{yyyy または yyyymmdd}
                  レスポンス形式:
                  {"success":1,"data":{"candlestick":[{"type":"1hour",
                   "ohlcv":[[open,high,low,close,volume,timestamp_ms], ...]}]}}
    - GMOコイン : https://api.coin.z.com/public/v1/klines?symbol=BTC_JPY&interval=1hour&date=2026
                  レスポンス形式:
                  {"status":0,"data":[{"openTime":"...","open":"...","high":"...",
                   "low":"...","close":"...","volume":"..."}, ...]}

取得単位の仕様:
    日足以下（1day, 1week, 1month, 1hour, 4hour, 8hour, 12hour など）の粒度は「年単位」(yyyy)、
    分足（1min, 5min, 15min, 30min など "min" を含むinterval）は「日単位」(yyyymmdd) で
    リクエストする。指定した --start / --end の期間をカバーするのに必要な年/日を
    自動的に列挙し、複数リクエストに分割して取得・結合する。

使い方:
    python scripts/fetch_ohlcv.py \
        --exchange bitbank --pair btc_jpy --interval 1hour \
        --start 2024-01-01 --end 2026-08-01 --out data/btc_jpy_1hour.csv

注意事項:
    - レート制限に配慮し、リクエストごとに必ず1秒以上のスリープを挟む。
    - 失敗したリクエストは指数バックオフで最大3回まで再試行する。
    - urllib.request の標準の挙動に従い、環境変数 HTTPS_PROXY / HTTP_PROXY を尊重する。
    - このスクリプトはユーザー自身のPCから実行することを想定している
      （このエージェントの実行環境からは取引所APIに到達できない）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

import pandas as pd

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# 出力CSVの列（厳密にこの順序・名前で出力する）
CSV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

# リクエスト間の最小スリープ秒数（レート制限対策。必ず1秒以上空ける）
MIN_SLEEP_SECONDS = 1.2

# 失敗時の最大リトライ回数
MAX_RETRIES = 3

# 指数バックオフの基準秒数（2秒, 4秒, 8秒 ... と増えていく）
BACKOFF_BASE_SECONDS = 2.0

# HTTPリクエストのタイムアウト秒数
REQUEST_TIMEOUT_SECONDS = 15

# interval文字列 -> 想定バー間隔（欠損バー検出・pandas.date_rangeのfreqに使用）
# 1monthのみ月初アンカー("MS")による近似（月は日数が可変のため）
INTERVAL_TO_FREQ: dict[str, str] = {
    "1min": "1min",
    "5min": "5min",
    "10min": "10min",
    "15min": "15min",
    "30min": "30min",
    "1hour": "1h",
    "4hour": "4h",
    "8hour": "8h",
    "12hour": "12h",
    "1day": "1D",
    "1week": "1W",
    "1month": "1MS",
}


class FetchError(Exception):
    """データ取得処理における回復不能なエラー"""


def _is_minute_interval(interval: str) -> bool:
    """分足（"min"を含むinterval）かどうかを判定する。分足は日単位(yyyymmdd)で取得する仕様。"""
    return "min" in interval


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _http_get(url: str) -> bytes:
    """
    指定URLにGETリクエストを送り、レスポンスボディ(bytes)を返す。

    - urllib.request の標準opener（環境変数 HTTPS_PROXY / HTTP_PROXY を自動的に
      尊重する ProxyHandler を含む）をそのまま利用する。
    - 失敗した場合は指数バックオフで最大 MAX_RETRIES 回まで再試行する。
    - 成否にかかわらず、リクエストのたびに MIN_SLEEP_SECONDS 秒以上スリープしてから戻る
      （＝次のリクエストまでの間隔を必ず1秒以上空ける）。
    """
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fetch_ohlcv/1.0"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                body = resp.read()
            return body
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                backoff = BACKOFF_BASE_SECONDS**attempt
                print(
                    f"  [警告] リクエスト失敗 (試行 {attempt}/{MAX_RETRIES}): {exc} "
                    f"-> {backoff:.1f}秒後に再試行します",
                    file=sys.stderr,
                )
                time.sleep(backoff)
        finally:
            # レート制限対策: 成功・失敗にかかわらず必ず間隔を空ける
            time.sleep(MIN_SLEEP_SECONDS)

    raise FetchError(f"リクエストが{MAX_RETRIES}回失敗しました: {url} (最後のエラー: {last_error})")


# ---------------------------------------------------------------------------
# 取引所ごとの取得処理
# ---------------------------------------------------------------------------


def _fetch_bitbank_period(pair: str, interval: str, period: str) -> pd.DataFrame:
    """bitbankから1期間分（1年 or 1日）のOHLCVを取得する"""
    url = f"https://public.bitbank.cc/{pair}/candlestick/{interval}/{period}"
    print(f"  取得中: {url}")
    body = _http_get(url)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise FetchError(f"bitbankのレスポンスがJSONとして解析できません: {url}") from exc

    if payload.get("success") != 1:
        code = payload.get("data", {}).get("code", "unknown")
        raise FetchError(f"bitbank APIがエラーを返しました (code={code}): {url}")

    candlesticks = payload.get("data", {}).get("candlestick", [])
    if not candlesticks:
        return pd.DataFrame(columns=CSV_COLUMNS)

    rows = []
    for entry in candlesticks:
        for o, h, l, c, v, ts_ms in entry.get("ohlcv", []):
            timestamp = dt.datetime.fromtimestamp(int(ts_ms) / 1000, tz=dt.timezone.utc)
            rows.append((timestamp, float(o), float(h), float(l), float(c), float(v)))

    return pd.DataFrame(rows, columns=CSV_COLUMNS)


def _fetch_gmo_period(pair: str, interval: str, period: str) -> pd.DataFrame:
    """GMOコインから1期間分（1年 or 1日）のOHLCVを取得する"""
    symbol = pair.upper()
    url = f"https://api.coin.z.com/public/v1/klines?symbol={symbol}&interval={interval}&date={period}"
    print(f"  取得中: {url}")
    body = _http_get(url)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise FetchError(f"GMOコインのレスポンスがJSONとして解析できません: {url}") from exc

    if payload.get("status") != 0:
        messages = payload.get("messages", [])
        raise FetchError(f"GMOコイン APIがエラーを返しました (status={payload.get('status')}): {messages}")

    data = payload.get("data", [])
    if not data:
        return pd.DataFrame(columns=CSV_COLUMNS)

    rows = []
    for entry in data:
        timestamp = dt.datetime.fromtimestamp(int(entry["openTime"]) / 1000, tz=dt.timezone.utc)
        rows.append(
            (
                timestamp,
                float(entry["open"]),
                float(entry["high"]),
                float(entry["low"]),
                float(entry["close"]),
                float(entry["volume"]),
            )
        )

    return pd.DataFrame(rows, columns=CSV_COLUMNS)


FETCHERS = {
    "bitbank": _fetch_bitbank_period,
    "gmo": _fetch_gmo_period,
}


# ---------------------------------------------------------------------------
# 期間分割・取得の統括
# ---------------------------------------------------------------------------


def _build_periods(interval: str, start: dt.date, end: dt.date) -> list[str]:
    """
    開始日・終了日をカバーするのに必要な取得単位（年 "yyyy" または日 "yyyymmdd"）の
    リストを作る。分足は日単位、それ以外は年単位。
    """
    if _is_minute_interval(interval):
        periods = []
        current = start
        while current <= end:
            periods.append(current.strftime("%Y%m%d"))
            current += dt.timedelta(days=1)
        return periods

    return [str(y) for y in range(start.year, end.year + 1)]


def fetch_ohlcv(exchange: str, pair: str, interval: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """指定された取引所・通貨ペア・足種・期間のOHLCVを、必要な回数に分割して取得し結合する"""
    periods = _build_periods(interval, start, end)
    fetch_fn = FETCHERS[exchange]

    print(f"{exchange} から {pair} / {interval} を取得します（{len(periods)}回のリクエストに分割）")

    frames = []
    for i, period in enumerate(periods, start=1):
        print(f"[{i}/{len(periods)}] period={period}")
        try:
            df = fetch_fn(pair, interval, period)
        except FetchError as exc:
            raise FetchError(f"period={period} の取得に失敗しました: {exc}") from exc
        if not df.empty:
            frames.append(df)

    if not frames:
        raise FetchError("取得できたデータが0件でした。exchange/pair/interval/期間の指定を確認してください。")

    return pd.concat(frames, ignore_index=True)


def _postprocess(df: pd.DataFrame, start: dt.date, end: dt.date) -> pd.DataFrame:
    """指定期間でフィルタし、重複除去・timestamp昇順ソートを行う"""
    start_dt = dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc)
    end_dt = dt.datetime.combine(end, dt.time.min, tzinfo=dt.timezone.utc) + dt.timedelta(days=1)

    df = df[(df["timestamp"] >= start_dt) & (df["timestamp"] < end_dt)]
    df = df.drop_duplicates(subset="timestamp")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 検証
# ---------------------------------------------------------------------------


def _validate(df: pd.DataFrame, interval: str) -> None:
    """取得結果を検証し、行数・期間・欠損バー数・異常行数を標準出力に出す"""
    n = len(df)
    print("\n=== 検証結果 ===")
    print(f"行数: {n}")

    if n == 0:
        print("データが0件のため、これ以上の検証はスキップします")
        print("================\n")
        return

    ts_min = df["timestamp"].min()
    ts_max = df["timestamp"].max()
    print(f"期間: {ts_min.isoformat()} 〜 {ts_max.isoformat()}")

    freq = INTERVAL_TO_FREQ.get(interval)
    if freq is None:
        print(f"欠損バー検出: interval={interval} は未対応のためスキップします")
    else:
        expected_index = pd.date_range(start=ts_min, end=ts_max, freq=freq, tz="UTC")
        expected_count = len(expected_index)
        missing = max(expected_count - n, 0)
        print(f"想定バー数: {expected_count}  実バー数: {n}  欠損バー数: {missing}")
        if interval == "1month":
            print("  (注: 1monthは月ごとの日数が異なるため、月初アンカーによる近似値)")

    invalid_hl = int((df["high"] < df["low"]).sum())
    invalid_close = int(((df["close"] > df["high"]) | (df["close"] < df["low"])).sum())
    invalid_open = int(((df["open"] > df["high"]) | (df["open"] < df["low"])).sum())
    print(
        f"異常行: high<low = {invalid_hl}件, closeが[low,high]範囲外 = {invalid_close}件, "
        f"openが[low,high]範囲外 = {invalid_open}件"
    )
    print("================\n")


def _save_csv(df: pd.DataFrame, out_path: str) -> None:
    """timestampをUTCのISO8601文字列に変換し、指定列のみでCSVを保存する"""
    out_df = df.copy()
    out_df["timestamp"] = out_df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    out_df.to_csv(out_path, index=False, columns=CSV_COLUMNS)
    print(f"保存しました: {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"日付は YYYY-MM-DD 形式で指定してください: {value}") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="bitbank / GMOコインからOHLCVデータを取得してCSVに保存する")
    parser.add_argument("--exchange", required=True, choices=["bitbank", "gmo"], help="取引所名")
    parser.add_argument("--pair", required=True, help="通貨ペア（例: btc_jpy）")
    parser.add_argument("--interval", required=True, help="足種（例: 1min, 1hour, 1day）")
    parser.add_argument("--start", required=True, type=_parse_date, help="取得開始日 YYYY-MM-DD")
    parser.add_argument("--end", required=True, type=_parse_date, help="取得終了日 YYYY-MM-DD（この日を含む）")
    parser.add_argument("--out", required=True, help="出力CSVファイルパス")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.start > args.end:
        print("エラー: --start は --end と同じか、それより前の日付を指定してください", file=sys.stderr)
        sys.exit(1)

    try:
        df = fetch_ohlcv(args.exchange, args.pair, args.interval, args.start, args.end)
        df = _postprocess(df, args.start, args.end)
        _validate(df, args.interval)
        _save_csv(df, args.out)
    except FetchError as exc:
        print(f"エラー: データ取得に失敗しました。{exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # 予期しないエラーも分かりやすい日本語で報告する
        print(f"エラー: 予期しない問題が発生しました。{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
