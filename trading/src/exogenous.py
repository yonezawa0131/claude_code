"""価格以外の判断材料（マクロ・ニュース・シーズナル）を扱うための枠組み。

## なぜ専用の枠組みが要るのか

価格以外の情報をバックテストに入れると、`validate.check_causality()` では
捕まえられない種類の先読みが混入する。検査器は戦略コードの因果性しか見ないが、
この種の先読みは**入力データそのもの**に埋まっているためである。

典型例:

- 「この期間のFRBはタカ派だった」— 事後に確定した評価。当時は分からない
- 「この日に地政学リスクが顕在化した」— 顕在化した後にしか分類できない
- 改定される統計（GDP、雇用統計）の**改定後の値**を使う
- 指標の公表時刻ではなく**対象期間**の日付で結合する
  （7月のCPIは8月中旬に公表される。7月のバーに結合したら1ヶ月先読みしている）

そこでこのモジュールでは、外部データに必ず2つの時刻を持たせる。

- `refers_to`: その値が「いつについての」情報か
- `known_at` : その値が「いつ観測可能になったか」

バックテストで使ってよいのは `known_at` を過ぎたものだけ。
この区別を型で強制することで、事故を構造的に防ぐ。

## サンプル数について

もう一つの問題は、外部要因ほど**独立した観測回数が少ない**こと。
2年ぶんの1時間足は17,520本あるが、その間にFOMCは16回しかない。
16回の観測に対して条件を増やせば、何かが効いて見えるのは当たり前で、
それは発見ではなく当てはめである。

`effective_sample_size()` はこれを事前に突きつけるためにある。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ExogenousSeries:
    """外部データの系列。観測可能になった時刻を必ず持つ。

    Parameters
    ----------
    name:
        識別名
    frame:
        列に ``refers_to`` ``known_at`` ``value`` を持つ DataFrame。
        ``known_at`` はその値が公表・観測可能になった時刻（UTC）
    """

    name: str
    frame: pd.DataFrame

    REQUIRED = ("refers_to", "known_at", "value")

    def __post_init__(self) -> None:
        missing = [c for c in self.REQUIRED if c not in self.frame.columns]
        if missing:
            raise ValueError(f"{self.name}: 列が足りません {missing}")

        known = pd.to_datetime(self.frame["known_at"], utc=True)
        refers = pd.to_datetime(self.frame["refers_to"], utc=True)

        # 対象期間より前に観測できる情報は存在しない
        if (known < refers).any():
            bad = int((known < refers).sum())
            raise ValueError(
                f"{self.name}: known_at が refers_to より前の行が {bad} 件あります。"
                "公表前の値を使うことになり、先読みになります"
            )

    def align_to(self, index: pd.DatetimeIndex) -> pd.Series:
        """バーの index に、その時点で**既に観測可能だった**値を割り当てる。

        merge_asof を known_at 基準で使うことで、
        「まだ公表されていない値」が過去のバーに漏れることを防ぐ。
        """
        if not isinstance(index, pd.DatetimeIndex):
            raise ValueError("index は DatetimeIndex である必要があります")

        left = pd.DataFrame({"ts": index}).sort_values("ts")
        right = (
            self.frame.assign(known_at=pd.to_datetime(self.frame["known_at"], utc=True))
            .sort_values("known_at")[["known_at", "value"]]
        )
        merged = pd.merge_asof(
            left, right, left_on="ts", right_on="known_at", direction="backward"
        )
        return pd.Series(
            merged["value"].to_numpy(), index=index, name=self.name
        )


def effective_sample_size(
    index: pd.DatetimeIndex, events_per_year: float
) -> tuple[int, float]:
    """ある頻度の外部要因について、この期間に何回観測できるかを返す。

    戻り値は (バー数, 想定される外部イベント回数)。

    バー数がいくら多くても、外部要因の観測回数はそれとは無関係に決まる。
    FOMCで条件分岐する戦略の実質的なサンプル数はFOMCの回数であって、
    バーの本数ではない。
    """
    if len(index) < 2:
        return len(index), 0.0
    span_days = (index[-1] - index[0]).total_seconds() / 86400.0
    return len(index), events_per_year * span_days / 365.0


#: よく持ち出される外部要因と、その年間発生回数
KNOWN_FREQUENCIES: dict[str, float] = {
    "FOMC（米連邦公開市場委員会）": 8.0,
    "日銀 金融政策決定会合": 8.0,
    "米CPI公表": 12.0,
    "米雇用統計": 12.0,
    "四半期（決算期末）": 4.0,
    "夏季（バカンス期）": 1.0,
    "曜日（各曜日）": 52.0,
    "月内の特定日": 12.0,
}


def sample_size_report(index: pd.DatetimeIndex) -> str:
    """判断材料ごとの有効サンプル数を並べた表を作る。

    「この材料を条件に入れてよいか」を、感覚ではなく回数で判断するための表。
    目安として、条件分岐に使うなら最低でも数十回、
    パラメータを調整するなら数百回の観測がほしい。
    """
    bars, _ = effective_sample_size(index, 0)
    span_days = (index[-1] - index[0]).total_seconds() / 86400.0
    lines = [
        f"データ期間: {index[0]:%Y-%m-%d} 〜 {index[-1]:%Y-%m-%d}"
        f"（{span_days:.0f}日 / {bars:,}バー）",
        "",
        f"{'判断材料':<28}{'観測回数':>10}   判定",
        "-" * 62,
        f"{'価格そのもの':<28}{bars:>10,}   十分",
    ]
    for label, freq in KNOWN_FREQUENCIES.items():
        _, count = effective_sample_size(index, freq)
        if count >= 200:
            verdict = "十分"
        elif count >= 30:
            verdict = "検証はできるが結論は弱い"
        else:
            verdict = "**検証不能**（偶然と区別できない）"
        lines.append(f"{label:<28}{count:>10.0f}   {verdict}")
    lines += [
        "",
        "観測回数が30を下回る材料を条件に加えると、",
        "「効いているように見えるもの」は高い確率で偶然です。",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 価格だけから作れる、時間に関する特徴量
#
# 外部データを持ち込まなくても、時間帯・曜日は index から決まる。
# これらは観測回数が多いので、検証に耐える。
# ---------------------------------------------------------------------------


def session_of(index: pd.DatetimeIndex, tz: str = "Asia/Tokyo") -> pd.Series:
    """時間帯を「アジア／欧州／米国」に分類する。

    暗号資産は24時間動くが、板の厚みと参加者は時間帯で変わる。
    「海外勢が休んでいる時間は動きが鈍い」という直感は、
    季節ではなく**時間帯**で見れば観測回数が桁違いに多く、検証できる。
    """
    local = index.tz_convert(tz)
    hour = local.hour
    labels = np.where(
        (hour >= 8) & (hour < 16),
        "asia",
        np.where((hour >= 16) & (hour < 22), "europe", "us"),
    )
    return pd.Series(labels, index=index, name="session")


@dataclass
class SessionFilter:
    """既存の戦略に、取引してよい時間帯・曜日の制限をかけるラッパー。

    「セッションによって値動きの質が違う」という仮説を、
    外部データなしで検証できる形にしたもの。

    使い方::

        base = EmaCrossATR()
        filtered = SessionFilter(base, allowed_sessions=("us",))

    元の戦略のシグナルのうち、許可された時間帯以外をノーポジにする。
    これにより「時間帯を絞ると成績が上がるか」を1パラメータで検証できる。
    パラメータが少ないほど、当てはめすぎの危険が小さい。
    """

    base: object
    #: 許可する時間帯。None なら制限しない
    allowed_sessions: tuple[str, ...] | None = None
    #: 許可する曜日（0=月曜）。None なら制限しない
    allowed_weekdays: tuple[int, ...] | None = None
    tz: str = "Asia/Tokyo"

    @property
    def name(self) -> str:
        parts = [getattr(self.base, "name", type(self.base).__name__)]
        if self.allowed_sessions:
            parts.append("/".join(self.allowed_sessions))
        if self.allowed_weekdays:
            parts.append("曜日" + ",".join(str(d) for d in self.allowed_weekdays))
        return " + ".join(parts)

    def warmup(self) -> int:
        return self.base.warmup()  # type: ignore[attr-defined]

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        sig = self.base.generate(df).copy()  # type: ignore[attr-defined]

        allowed = pd.Series(True, index=df.index)
        if self.allowed_sessions is not None:
            allowed &= session_of(df.index, self.tz).isin(self.allowed_sessions)
        if self.allowed_weekdays is not None:
            local = df.index.tz_convert(self.tz)
            allowed &= pd.Series(local.weekday, index=df.index).isin(
                self.allowed_weekdays
            )

        sig.loc[~allowed, "direction"] = 0.0
        sig.loc[~allowed, ["stop_loss", "take_profit"]] = np.nan
        return sig


@dataclass
class BlackoutFilter:
    """指定した時刻の前後で取引を止めるラッパー。

    FOMCやCPIの公表前後は、方向は読めないがボラティリティは跳ねる。
    **方向を当てにいくのではなく、当てられない時間を避ける**という使い方なら、
    外部要因を1パラメータで扱える。

    「イベントで儲ける」ではなく「イベントを避ける」ほうが、
    必要な予測力がゼロで済むぶん検証に耐えやすい。

    events はイベント発生時刻（UTC）の DatetimeIndex。
    公表スケジュールは事前に決まっているので、これは後知恵にならない。
    """

    base: object
    events: pd.DatetimeIndex
    before: pd.Timedelta = pd.Timedelta("2h")
    after: pd.Timedelta = pd.Timedelta("2h")

    @property
    def name(self) -> str:
        base_name = getattr(self.base, "name", type(self.base).__name__)
        return f"{base_name} + イベント回避"

    def warmup(self) -> int:
        return self.base.warmup()  # type: ignore[attr-defined]

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        sig = self.base.generate(df).copy()  # type: ignore[attr-defined]
        blocked = pd.Series(False, index=df.index)
        for event in self.events:
            blocked |= (df.index >= event - self.before) & (df.index <= event + self.after)
        sig.loc[blocked, "direction"] = 0.0
        sig.loc[blocked, ["stop_loss", "take_profit"]] = np.nan
        return sig
