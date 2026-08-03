"""データ取得スクリプトの検証。

このスクリプトは開発環境から実行できない（取引所APIに到達できない）。
**動作確認できないコードほど、動くところまでは検証しておく必要がある。**

実際、初版は 1hour を年単位でリクエストする想定で書かれていて、
ユーザーの環境で 404 になった。そして 404 を3回再試行していた。

ここで検証するのは、ネットワークを使わない部分。
  - 日付の指定形式を、想定ではなく実際の応答で決めているか
  - 待っても直らない失敗を、再試行していないか
"""

from __future__ import annotations

import datetime as dt
import sys
import urllib.error
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.scripts import fetch_ohlcv as fo  # noqa: E402

START = dt.date(2024, 1, 1)
END = dt.date(2024, 3, 1)


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    """テストでレート制限待ちをしない。"""
    monkeypatch.setattr(fo.time, "sleep", lambda *_: None)


def _frame(n: int = 3) -> pd.DataFrame:
    ts = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 1.0,
        }
    )


# ---------------------------------------------------------------------------
# 期間の組み立て
# ---------------------------------------------------------------------------


def test_yearly_periods_cover_every_year_touched():
    assert fo._build_periods("year", dt.date(2024, 6, 1), dt.date(2026, 2, 1)) == [
        "2024",
        "2025",
        "2026",
    ]


def test_daily_periods_include_both_ends():
    periods = fo._build_periods("day", dt.date(2024, 1, 30), dt.date(2024, 2, 2))
    assert periods == ["20240130", "20240131", "20240201", "20240202"]


def test_period_string_matches_the_granularity():
    day = dt.date(2024, 7, 5)
    assert fo._period_string(day, "year") == "2024"
    assert fo._period_string(day, "day") == "20240705"


# ---------------------------------------------------------------------------
# 日付形式は、想定ではなく応答で決める
# ---------------------------------------------------------------------------


def test_falls_back_to_daily_when_the_assumed_format_404s(monkeypatch, capsys):
    """**この基盤が実際に踏んだ不具合。**

    1hour を年単位と想定していたが、404 が返った。
    想定を書き換えるだけでは、また別の足種で同じことが起きる。
    実際に叩いて確かめ、外れていたら切り替える。
    """
    calls = []

    def fake(pair, interval, period):
        calls.append(period)
        if len(period) == 4:  # 年単位は受け付けない取引所
            raise fo.HttpStatusError(404, "url")
        return _frame()

    monkeypatch.setitem(fo.FETCHERS, "bitbank", fake)
    monkeypatch.setattr(fo, "YEARLY_INTERVALS", frozenset({"1hour"}))  # わざと外した想定

    granularity, df = fo._probe_granularity("bitbank", "btc_jpy", "1hour", START)

    assert granularity == "day"
    assert calls == ["2024", "20240101"]
    assert not df.empty
    assert "この形式を使います" in capsys.readouterr().out


def test_falls_back_when_the_response_is_empty():
    """404 だけでなく、空の応答も「その形式では取れない」と扱う。"""

    def fake(pair, interval, period):
        return pd.DataFrame(columns=fo.CSV_COLUMNS) if len(period) == 4 else _frame()

    original = fo.FETCHERS["bitbank"]
    fo.FETCHERS["bitbank"] = fake
    try:
        granularity, _ = fo._probe_granularity("bitbank", "btc_jpy", "1day", START)
    finally:
        fo.FETCHERS["bitbank"] = original
    assert granularity == "day"


def test_keeps_the_assumed_format_when_it_works(monkeypatch):
    """当たっているときに、余計な切り替えをしないこと。"""
    calls = []

    def fake(pair, interval, period):
        calls.append(period)
        return _frame()

    monkeypatch.setitem(fo.FETCHERS, "bitbank", fake)
    granularity, _ = fo._probe_granularity("bitbank", "btc_jpy", "1day", START)
    assert granularity == "year"
    assert calls == ["2024"], "1回で決まるはずが余計に叩いています"


def test_both_formats_failing_explains_what_to_check(monkeypatch):
    def fake(pair, interval, period):
        raise fo.HttpStatusError(404, "url")

    monkeypatch.setitem(fo.FETCHERS, "bitbank", fake)
    with pytest.raises(fo.FetchError, match="年単位でも日単位でも"):
        fo._probe_granularity("bitbank", "btc_jpy", "1hour", START)


def test_the_probe_result_is_reused_not_refetched(monkeypatch):
    """形式の確認で取れたデータを捨てない。無駄な1回を増やさない。"""
    calls = []

    def fake(pair, interval, period):
        calls.append(period)
        return _frame()

    monkeypatch.setitem(fo.FETCHERS, "bitbank", fake)
    fo.fetch_ohlcv("bitbank", "btc_jpy", "1day", dt.date(2024, 1, 1), dt.date(2026, 1, 1))
    assert calls == ["2024", "2025", "2026"], calls


# ---------------------------------------------------------------------------
# 待っても直らない失敗を再試行しない
# ---------------------------------------------------------------------------


def _raise_status(code: int):
    def opener(*_args, **_kwargs):
        raise urllib.error.HTTPError("url", code, "msg", {}, None)

    return opener


def test_404_is_not_retried(monkeypatch):
    """**404 は待っても直らない。**

    初版はすべての失敗を3回再試行していたので、
    URLが間違っているだけで6秒待たされ、原因も分かりにくかった。
    """
    attempts = []

    def opener(*args, **kwargs):
        attempts.append(1)
        raise urllib.error.HTTPError("url", 404, "Not Found", {}, None)

    monkeypatch.setattr(fo.urllib.request, "urlopen", opener)
    with pytest.raises(fo.HttpStatusError) as excinfo:
        fo._http_get("https://example.invalid/x")
    assert excinfo.value.status == 404
    assert len(attempts) == 1, f"404 を {len(attempts)} 回試行しています"


def test_rate_limit_and_server_errors_are_retried(monkeypatch):
    """429 と 5xx は時間をおけば直りうるので、再試行する。"""
    for code in (429, 503):
        attempts = []

        def opener(*args, _code=code, **kwargs):
            attempts.append(1)
            raise urllib.error.HTTPError("url", _code, "msg", {}, None)

        monkeypatch.setattr(fo.urllib.request, "urlopen", opener)
        with pytest.raises(fo.FetchError):
            fo._http_get("https://example.invalid/x")
        assert len(attempts) == fo.MAX_RETRIES, f"{code}: {len(attempts)} 回"


def test_network_errors_are_retried(monkeypatch):
    attempts = []

    def opener(*args, **kwargs):
        attempts.append(1)
        raise urllib.error.URLError("unreachable")

    monkeypatch.setattr(fo.urllib.request, "urlopen", opener)
    with pytest.raises(fo.FetchError):
        fo._http_get("https://example.invalid/x")
    assert len(attempts) == fo.MAX_RETRIES


# ---------------------------------------------------------------------------
# 途中で失敗しても、取れた分を捨てない
# ---------------------------------------------------------------------------


def test_partial_results_are_saved_when_the_fetch_breaks(monkeypatch, tmp_path):
    """900回のリクエストが800回目で落ちても、そこまでを残す。"""
    partial = tmp_path / "out.csv.partial"

    def fake(pair, interval, period):
        if period == "2026":
            raise fo.FetchError("落ちた")
        return _frame()

    monkeypatch.setitem(fo.FETCHERS, "bitbank", fake)
    with pytest.raises(fo.FetchError):
        fo.fetch_ohlcv(
            "bitbank",
            "btc_jpy",
            "1day",
            dt.date(2024, 1, 1),
            dt.date(2026, 1, 1),
            partial_out=str(partial),
        )

    assert partial.exists(), "取れた分が保存されていません"
    saved = pd.read_csv(partial)
    assert len(saved) > 0
    assert list(saved.columns) == fo.CSV_COLUMNS
