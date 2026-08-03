"""CLI が、実データの形に耐えるか。

実データを初めて取得したとき、日足（944本）が手に入った。
そこに `--compare-all` をかけると、**日中モメンタムで例外が出て全体が落ちた**。
1セッション24時間に対して1本しかバーがないので、この戦略は成立しない。

戦略が成立しないこと自体は正しい。問題は、
**1つ成立しないだけで、他の6戦略の結果も見られなくなること。**

比較は、比較できるものだけで続けるべき。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.scripts.make_synthetic import make_synthetic_ohlcv  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "trading" / "run_backtest.py"


@pytest.fixture(scope="module")
def daily_csv(tmp_path_factory) -> Path:
    """日足のCSV。1時間足を日足にまとめて作る。"""
    df = make_synthetic_ohlcv(6_000, 11, "mixed")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    daily = (
        df.set_index("timestamp")
        .resample("1D")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )
    daily.index = daily.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    path = tmp_path_factory.mktemp("data") / "daily.csv"
    daily.to_csv(path, index_label="timestamp")
    return path


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=300,
    )


def test_compare_all_survives_a_strategy_that_cannot_run(daily_csv):
    """成立しない戦略が1つあっても、比較は最後まで進むこと。"""
    result = _run("--data", str(daily_csv), "--compare-all", "--cost", "gmo")

    assert result.returncode == 0, result.stderr[-2000:]
    assert "Traceback" not in result.stderr, result.stderr[-2000:]
    assert "このデータでは使えません" in result.stdout
    # 飛ばした戦略以外は、ちゃんと比較表に載っている
    assert "まとめ（買い持ちとの差の順）" in result.stdout
    assert "買い持ち" in result.stdout


def test_skipped_strategies_do_not_inflate_the_trial_count(daily_csv):
    """試行数は、実際に結果が出た戦略の数であること。

    落ちた戦略まで数えると、閾値が実際より厳しくなる。
    """
    result = _run("--data", str(daily_csv), "--compare-all", "--cost", "gmo")
    assert "試した戦略・設定の数 : 6" in result.stdout, result.stdout[-1500:]


def test_asking_for_an_impossible_strategy_fails_loudly(daily_csv):
    """1つだけ指定して、それが成立しないなら、失敗として終わること。

    黙って0件の結果を返すと、「試したが何も出なかった」と読めてしまう。
    """
    result = _run("--data", str(daily_csv), "--strategy", "intraday_momentum")
    assert result.returncode == 1
    assert "このデータでは使えません" in result.stdout
    assert "Traceback" not in result.stderr


def test_walk_forward_runs_alongside_compare_all(daily_csv):
    """--compare-all と --walk-forward の併用が無視されないこと。"""
    result = _run(
        "--data", str(daily_csv), "--compare-all", "--cost", "gmo", "--walk-forward", "4"
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "ウォークフォワード検証" in result.stdout
    assert "さらに検証します" in result.stdout


def test_rotation_null_runs_alongside_compare_all(daily_csv):
    """--null-runs も同じ扱いで、黙って無視されないこと。"""
    result = _run(
        "--data", str(daily_csv), "--compare-all", "--cost", "gmo", "--null-runs", "30"
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "ローテーション検定" in result.stdout
    assert "ずらした回数: 30 回" in result.stdout
