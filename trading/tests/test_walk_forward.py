"""ウォークフォワード検証そのものの検証。

これは実データで採否を決める最終判定器になる。
その判定器が**優位性の消滅を捉えられるか**は、
判定させる前に確かめておかないといけない。

陽性対照と同じ論理で、答えの分かっているデータを2種類使う。
  - 優位性が最後まで一定のデータ → 警告を出してはいけない
  - 優位性が後半にかけて消えるデータ → 必ず捉えないといけない

2つ目は実際に起きること。公表された異常収益は縮小する傾向がある。
そして厄介なことに、**全期間で1回バックテストすると気づけない。**
前半の利益が後半の損失を覆い隠して、平均すればプラスに見える。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trading.scripts.make_synthetic import make_synthetic_ohlcv  # noqa: E402
from trading.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from trading.src.costs import GMO_EXCHANGE, OrderType  # noqa: E402
from trading.src.metrics import evaluate  # noqa: E402
from trading.src.strategy import IntradayMomentum  # noqa: E402
from trading.src.validate import DECAY_Z_THRESHOLD, walk_forward  # noqa: E402

SEED = 3
# 6分割して各期間が30回の取引を超えるだけの本数が要る。
# これを下回ると、期間ごとの成績がノイズに埋もれて傾向が読めない
BARS = 20_000
WINDOWS = 6

CONFIG = BacktestConfig(
    initial_capital=300_000.0,
    position_fraction=1.0,
    order_type=OrderType.TAKER,
)
STRATEGY = IntradayMomentum(stop_atr=None)


def _frame(bars: int = BARS, seed: int = SEED, **kw) -> pd.DataFrame:
    df = make_synthetic_ohlcv(bars, seed, "intraday", session_bars=24, **kw)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    return df.set_index("timestamp")


def _walk(**kw):
    return walk_forward(_frame(**kw), STRATEGY, GMO_EXCHANGE, CONFIG, n_windows=WINDOWS)


STABLE = dict(beta=1.0)
DECAYING = dict(beta=1.0, beta_end=0.0)


def _has(warnings: list[str], fragment: str) -> bool:
    return any(fragment in w for w in warnings)


# ---------------------------------------------------------------------------
# 消えていく優位性を捉えられるか
# ---------------------------------------------------------------------------


def test_a_decaying_edge_still_looks_profitable_over_the_full_sample():
    """全期間で1回測ると、死んだ優位性がプラスに見える。

    ウォークフォワードが必要な理由そのもの。
    ここがマイナスになるならデータの作りが強すぎて、検証になっていない。
    """
    report = evaluate(run_backtest(_frame(**DECAYING), STRATEGY, GMO_EXCHANGE, CONFIG))
    assert report.total_return > 0, "全期間でマイナスなら、そもそも隠れていない"


def test_counting_winning_windows_would_have_passed_the_dead_edge():
    """**勝った期間の数だけでは、死んだ優位性を弾けない。**

    このテストは「良い性質」ではなく、**道具の欠陥を固定する**ためにある。
    数は順番を捨てるので、前半の貯金で過半数が残ってしまう。
    decay_z を足した理由がこれ。
    """
    result = _walk(**DECAYING)
    positive = int((result.returns > 0).sum())
    assert positive > len(result.returns) / 2, (
        "勝ち期間の数が過半数を割っています。"
        "このデータでは数え上げだけでも弾けてしまい、検証になりません"
    )
    # 数では通ってしまうが、順番を見る統計量は捉える
    assert result.decay_z < DECAY_Z_THRESHOLD


def test_decaying_edge_raises_the_decay_warning():
    warnings = _walk(**DECAYING).warnings()
    assert _has(warnings, "後半の成績が前半より落ちています"), warnings


def test_decaying_edge_reports_that_the_latest_window_is_negative():
    """直近が負なのに全体が正、という形を名指しする。

    「過去の相場で測っている」ことに気づける唯一の手がかりになる。
    """
    result = _walk(**DECAYING)
    assert result.returns[-1] < 0 < result.returns.mean()
    assert _has(result.warnings(), "最新の期間はマイナス"), result.warnings()


# ---------------------------------------------------------------------------
# 消えていない優位性を、消えたと言わないか
# ---------------------------------------------------------------------------


def test_stable_edge_is_not_flagged_as_decaying():
    """常に警告を出す検査は、警告を出さない検査と同じくらい役に立たない。"""
    result = _walk(**STABLE)
    assert result.decay_z > DECAY_Z_THRESHOLD, (
        f"一定の優位性を減衰と誤判定しています（{result.decay_z:+.2f}）"
    )
    assert not _has(result.warnings(), "後半の成績が前半より落ちています")
    assert not _has(result.warnings(), "最新の期間はマイナス")


def test_stable_edge_wins_every_window():
    result = _walk(**STABLE)
    assert (result.returns > 0).all(), result.returns


def test_the_two_cases_are_separated_by_the_statistic():
    """安定と消滅で、標準化スコアが閾値をまたいで分かれる。

    10シードで測った範囲は 安定 [-0.95, +1.43] / 消滅 [-1.75, -1.09]。
    **境目に余裕はほとんどない。** この1つの数字で採否を決めないこと。
    """
    stable, decaying = _walk(**STABLE).decay_z, _walk(**DECAYING).decay_z
    assert decaying < DECAY_Z_THRESHOLD < stable
    assert stable - decaying > 1.0


# ---------------------------------------------------------------------------
# 読めないときに読めないと言うか
# ---------------------------------------------------------------------------


def test_thin_windows_are_flagged_rather_than_read():
    """期間あたりの取引が少なすぎるときは、傾向を読ませない。

    最初にこれを測ったとき、8000本を6分割して各期間28回になり、
    安定と消滅の区別がつかなかった。**足りないことに気づける必要がある。**
    """
    result = _walk(bars=4_000, **DECAYING)
    assert _has(result.warnings(), "ノイズに埋もれ"), result.warnings()


def test_decay_is_undefined_with_too_few_windows():
    """2〜3分割では前半後半に分けられない。数字をでっち上げない。"""
    result = walk_forward(_frame(bars=6_000), STRATEGY, GMO_EXCHANGE, CONFIG, n_windows=3)
    assert np.isnan(result.decay)
    assert np.isnan(result.decay_z)


def test_summary_mentions_the_ordering_caveat():
    """レポートを読んだ人が、数え上げの限界に気づけること。"""
    assert "順番を捨てます" in _walk(**STABLE).summary()
