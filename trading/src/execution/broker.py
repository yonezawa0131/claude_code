"""取引所とのやりとり。

## 3つの実装

- `PaperBroker`  — 注文を出したことにして、状態をファイルに持つ。**既定**
- `BitbankBroker` — bitbank に発注する。**この環境から検証できていない**
- `GmoBroker`     — GMOコインに発注する。**この環境から検証できていない**

後者2つは正直に書いておく。この開発環境から取引所APIに到達できないため、
署名の組み立てや応答の解釈を**実物に対して確かめられていない**。
最小額で1回動かし、取引所の画面と突き合わせるまでは信用しないこと。

## 保有は必ず取引所から読む

`fetch_balances()` は、ローカルの記憶ではなく取引所の残高を返す。
手で1回売買しても、別のマシンから動かしても、プロセスが落ちても、
次の実行は正しい現在地から始まる。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from pathlib import Path
from typing import Protocol


class BrokerError(Exception):
    """取引所とのやりとりで起きた回復不能なエラー。"""


@dataclass(frozen=True)
class Order:
    """1件の注文。"""

    pair: str
    #: "buy" または "sell"
    side: str
    #: 数量（銘柄の単位）
    amount: float
    #: 指値価格。None なら成行
    price: float | None = None

    def __post_init__(self) -> None:
        if self.side not in ("buy", "sell"):
            raise ValueError(f"side は buy か sell です: {self.side}")
        if self.amount <= 0:
            raise ValueError("数量は正の値である必要があります")
        if self.price is not None and self.price <= 0:
            raise ValueError("指値価格は正の値である必要があります")

    @property
    def order_type(self) -> str:
        return "limit" if self.price is not None else "market"

    def notional(self, reference_price: float) -> float:
        """この注文の想定約定金額（円）。"""
        return self.amount * (self.price if self.price is not None else reference_price)


class Broker(Protocol):
    """取引所の最小インターフェース。"""

    name: str

    def fetch_balances(self) -> dict[str, float]:
        """通貨ごとの保有量を返す。**取引所が正**。"""
        ...

    def fetch_price(self, pair: str) -> float:
        """現在値を返す。"""
        ...

    def place_order(self, order: Order) -> dict:
        """注文を出す。"""
        ...


@dataclass
class PaperBroker:
    """発注したことにして、状態をファイルに持つ。

    **既定はこちら。** 本番は明示的に選ばないと動かない。

    ## 指値は、その値段に来るまで約定しない

    最初の実装は、指値を出した瞬間にその指値価格で約定させていた。
    現在値 9,989,404 円のときに 9,984,409 円の買い指値を出すと、
    **出した瞬間に 0.05% 得をする**計算になり、
    30万円の口座が1回の売買で 300,150 円になった。

    これは**この基盤がバックテスト側で見つけて直したのと同じ誤り**になる
    （`docs/02` の項目2、`backtest.MakerFill`）。片方で直して、片方で再現させた。

    指値が約定するのは「価格が自分のところまで来たとき」だけになる。
    だからここでは、指値注文を**板に置いたまま保持し**、
    次に価格を受け取ったときに届いていれば約定させる。届かなければ残る。

    この違いは無視できない。**約定しない指値がある**という事実こそ、
    この基盤が測って「1回きりの機会を狙う戦略では指値が成行より悪くなる」
    という結論を出した根拠になっている。

    ## 手数料も乗せる

    メイカーは受け取り（bitbank は −0.02%）、テイカーは支払い（0.12%）。
    ゼロにしておくと、成績が実際より良く出る。

    ## それでもこれは成績の見積もりには使えない

    板の厚みも、キューの順番も、部分約定も入っていない。
    ここで確かめるのは**配線が正しいか**だけになる。
    """

    state_path: Path
    name: str = "ペーパー（発注しません）"
    #: メイカー手数料（負なら受け取り）。bitbank の実料率
    fee_maker: float = -0.0002
    #: テイカー手数料
    fee_taker: float = 0.0012
    _prices: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.state_path = Path(self.state_path)
        if not self.state_path.exists():
            os.makedirs(self.state_path.parent, exist_ok=True)
            self._save({"balances": {"jpy": 0.0}, "open_orders": []})

    def _load(self) -> dict:
        with open(self.state_path, encoding="utf-8") as fh:
            state = json.load(fh)
        # 旧形式（残高だけ）からの読み替え
        if "balances" not in state:
            state = {"balances": state, "open_orders": []}
        state["balances"] = {k: float(v) for k, v in state["balances"].items()}
        state.setdefault("open_orders", [])
        return state

    def _save(self, state: dict) -> None:
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2, sort_keys=True)

    def set_prices(self, prices: dict[str, float]) -> None:
        self._prices = dict(prices)

    def deposit(self, currency: str, amount: float) -> None:
        """初期資金を置く。ペーパー用。"""
        state = self._load()
        state["balances"][currency] = state["balances"].get(currency, 0.0) + amount
        self._save(state)

    def fetch_balances(self) -> dict[str, float]:
        """**注文に取られていない**残高を返す。

        指値を出して板に置いている間、その資金は使えない。
        使える額として返すと、二重に使えることになる。
        """
        return dict(self._load()["balances"])

    def open_orders(self) -> list[dict]:
        return list(self._load()["open_orders"])

    def fetch_price(self, pair: str) -> float:
        if pair not in self._prices:
            raise BrokerError(f"価格が設定されていません: {pair}（set_prices を呼んでください）")
        return self._prices[pair]

    def _apply_fill(
        self, balances: dict, pair: str, side: str, amount: float, price: float, fee: float
    ) -> None:
        """約定を残高に反映する。予約済みの資金は差し引き済みとして扱う。"""
        base, quote = pair.split("_")
        gross = amount * price
        if side == "buy":
            # 予約時に quote を引いてあるので、ここでは受け取りだけ
            balances[base] = balances.get(base, 0.0) + amount
            balances[quote] = balances.get(quote, 0.0) - gross * fee
        else:
            balances[quote] = balances.get(quote, 0.0) + gross - gross * fee

    def place_order(self, order: Order) -> dict:
        state = self._load()
        balances = state["balances"]
        base, quote = order.pair.split("_")

        if order.price is None:
            # 成行は即時。テイカー手数料
            price = self.fetch_price(order.pair)
            need = order.amount * price
            if order.side == "buy":
                if balances.get(quote, 0.0) < need * (1 + self.fee_taker):
                    raise BrokerError(
                        f"{quote} が足りません"
                        f"（必要 {need:,.0f} / 保有 {balances.get(quote, 0.0):,.0f}）"
                    )
                balances[quote] = balances.get(quote, 0.0) - need
            else:
                if balances.get(base, 0.0) < order.amount - 1e-12:
                    raise BrokerError(
                        f"{base} が足りません"
                        f"（必要 {order.amount} / 保有 {balances.get(base, 0.0)}）"
                    )
                balances[base] = balances.get(base, 0.0) - order.amount
            self._apply_fill(balances, order.pair, order.side, order.amount, price, self.fee_taker)
            self._save(state)
            return {"paper": True, "status": "filled", "pair": order.pair,
                    "side": order.side, "amount": order.amount, "price": price,
                    "type": "market"}

        # 指値は板に置くだけ。資金を予約して、約定は価格が来るまで待つ
        need = order.amount * order.price
        if order.side == "buy":
            if balances.get(quote, 0.0) < need:
                raise BrokerError(
                    f"{quote} が足りません"
                    f"（必要 {need:,.0f} / 保有 {balances.get(quote, 0.0):,.0f}）"
                )
            balances[quote] = balances.get(quote, 0.0) - need
        else:
            if balances.get(base, 0.0) < order.amount - 1e-12:
                raise BrokerError(
                    f"{base} が足りません"
                    f"（必要 {order.amount} / 保有 {balances.get(base, 0.0)}）"
                )
            balances[base] = balances.get(base, 0.0) - order.amount

        state["open_orders"].append({
            "pair": order.pair, "side": order.side,
            "amount": order.amount, "price": order.price,
            # **いつ板に置いたかを持つ。** これがないと、
            # 注文を出す前に付いた安値で「約定した」と判定してしまう
            "placed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        self._save(state)
        return {"paper": True, "status": "resting", "pair": order.pair,
                "side": order.side, "amount": order.amount, "price": order.price,
                "type": "limit"}

    def settle(self, ranges: dict[str, tuple[float, float]]) -> list[dict]:
        """前回からの値動きが指値に届いていれば約定させる。

        **ここが「指値は必ず約定する」を否定している箇所になる。**

        受け取るのは (安値, 高値) の組であって、瞬間の価格ではない。
        板に置いた注文は、その間に**一度でも**指値に触れれば約定する。
        瞬間の価格だけで判定すると、実際には約定していたものを
        「約定しなかった」と扱うことになり、**今度は逆向きに嘘をつく**。

        バックテスト側の `backtest.MakerFill` が高値安値で判定しているのと
        同じ理屈になる。片方だけ瞬間値にすると、2つの結果が食い違う。
        """
        state = self._load()
        balances, resting = state["balances"], state["open_orders"]
        filled, still_open = [], []

        for o in resting:
            span = ranges.get(o["pair"])
            if span is None:
                still_open.append(o)
                continue
            low, high = float(span[0]), float(span[1])
            reached = low <= o["price"] if o["side"] == "buy" else high >= o["price"]
            if not reached:
                still_open.append({**o, "closest": low if o["side"] == "buy" else high})
                continue
            self._apply_fill(
                balances, o["pair"], o["side"], o["amount"], o["price"], self.fee_maker
            )
            filled.append({**o, "status": "filled", "fee": self.fee_maker})

        state["open_orders"] = still_open
        self._save(state)
        return filled

    def cancel_all(self) -> int:
        """板に置いた注文を全部取り消し、予約していた資金を戻す。

        入れ替えのたびに古い注文を消してから出し直す。
        残したまま新しい注文を出すと、資金が二重に取られる。
        """
        state = self._load()
        balances = state["balances"]
        for o in state["open_orders"]:
            base, quote = o["pair"].split("_")
            if o["side"] == "buy":
                balances[quote] = balances.get(quote, 0.0) + o["amount"] * o["price"]
            else:
                balances[base] = balances.get(base, 0.0) + o["amount"]
        count = len(state["open_orders"])
        state["open_orders"] = []
        self._save(state)
        return count


@dataclass
class BitbankBroker:
    """bitbank の private API を叩く。

    **この開発環境から検証できていない。**
    署名の組み立ても応答の解釈も、実物に対して確かめていない。
    最小額で1回動かし、取引所の画面と突き合わせるまで信用しないこと。

    API キーには**出金権限を付けないこと。** 取引権限だけで足りる。
    """

    api_key: str
    api_secret: str
    name: str = "bitbank（本番）"
    base_url: str = "https://api.bitbank.cc/v1"
    public_url: str = "https://public.bitbank.cc"
    order_path: str = "/user/spot/order"
    timeout: int = 15
    #: 実物に対する検証が済んでいないことを示す
    unverified: bool = True

    def _signed_get(self, path: str) -> dict:
        nonce = str(int(time.time() * 1000))
        message = nonce + path
        signature = hmac.new(
            self.api_secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        req = urllib.request.Request(
            self.base_url + path,
            headers={
                "ACCESS-KEY": self.api_key,
                "ACCESS-NONCE": nonce,
                "ACCESS-SIGNATURE": signature,
            },
        )
        return self._send(req)

    def _signed_post(self, path: str, body: dict) -> dict:
        nonce = str(int(time.time() * 1000))
        payload = json.dumps(body)
        message = nonce + payload
        signature = hmac.new(
            self.api_secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        req = urllib.request.Request(
            self.base_url + path,
            data=payload.encode(),
            headers={
                "Content-Type": "application/json",
                "ACCESS-KEY": self.api_key,
                "ACCESS-NONCE": nonce,
                "ACCESS-SIGNATURE": signature,
            },
            method="POST",
        )
        return self._send(req)

    def _send(self, req: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise BrokerError(f"HTTP {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BrokerError(f"取引所に到達できません: {exc}") from exc

        if payload.get("success") != 1:
            code = payload.get("data", {}).get("code", "unknown")
            raise BrokerError(f"取引所がエラーを返しました（code={code}）")
        return payload.get("data", {})

    def fetch_balances(self) -> dict[str, float]:
        data = self._signed_get("/user/assets")
        out = {}
        for asset in data.get("assets", []):
            amount = float(asset.get("free_amount", 0.0))
            if amount > 0:
                out[asset["asset"]] = amount
        return out

    def fetch_price(self, pair: str) -> float:
        req = urllib.request.Request(f"{self.public_url}/{pair}/ticker")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BrokerError(f"価格を取得できません: {exc}") from exc
        if payload.get("success") != 1:
            raise BrokerError(f"価格の応答が異常です: {payload}")
        return float(payload["data"]["last"])

    def order_body(self, order: Order) -> dict:
        """発注に使う本文を組み立てる。**送信はしない。**

        `place_order` はこれをそのまま送る。分けてあるのは、
        **送らずに中身を確かめられるようにする**ため。

        表示用に別途組み立て直すと、表示と実際の送信内容がずれる。
        ずれた表示で「確認した」と思い込むほうが、確認しないより危ない。
        """
        body = {
            "pair": order.pair,
            "amount": f"{order.amount:.8f}",
            "side": order.side,
            "type": order.order_type,
        }
        if order.price is not None:
            body["price"] = f"{order.price:.8f}"
            # 板に並べる注文だけを出す。約定してテイカーになるくらいなら出さない
            body["post_only"] = True
        return body

    def place_order(self, order: Order) -> dict:
        return self._signed_post(self.order_path, self.order_body(order))


#: GMOコインの銘柄名。**現物とレバレッジで別物になる。**
#:
#:   BTC      → 現物。買えば現物を持つ
#:   BTC_JPY  → **レバレッジ**。建玉であって現物ではない
#:
#: この違いは資金に直結する。レバレッジは建玉に1日0.04%（両建て両方）かかり、
#: 国内では2倍が上限で、**現物ではないので長期に持つと手数料が積み上がる**。
#:
#: 出回っているサンプルコードには `symbol='BTC_JPY'` で発注しているものがある。
#: そのまま真似すると、現物を買ったつもりで**レバレッジ建玉を持つ**ことになる。
#: だからこの基盤は、対応表にある現物銘柄しか受け付けない。
GMO_SPOT_SYMBOL = {
    "btc_jpy": "BTC",
    "eth_jpy": "ETH",
    "xrp_jpy": "XRP",
    "ltc_jpy": "LTC",
    "bcc_jpy": "BCH",
    "bch_jpy": "BCH",
}

#: レバレッジ側の銘柄名。**受け付けないために**持っている
GMO_LEVERAGE_SYMBOLS = frozenset(
    {"BTC_JPY", "ETH_JPY", "XRP_JPY", "LTC_JPY", "BCH_JPY"}
)


@dataclass
class GmoBroker:
    """GMOコインの API を叩く。**現物だけ。**

    **この開発環境から検証できていない。**
    署名の組み立ても応答の解釈も、実物に対して確かめていない。

    API キーには**出金権限を付けないこと。** 取引権限だけで足りる。

    ## bitbank との違いで、間違えると金が減るところ

    1. **銘柄名。** `BTC` が現物、`BTC_JPY` がレバレッジになる。
       取り違えると、現物を買ったつもりで建玉を持つ
    2. **署名するパスに `/private` を含めない。** URL は
       `https://api.coin.z.com/private/v1/account/assets` だが、
       署名する文字列は `/v1/account/assets` になる
    3. **成否は `status` で返る。** `status == 0` が成功で、
       HTTP 200 でも失敗していることがある

    ## 注文ルールは取引所から読む

    最小数量も刻み幅も、こちらの記憶ではなく `/public/v1/symbols` から取る。
    記憶で埋めると、取引所が変えた日から注文が黙って弾かれる。
    """

    api_key: str
    api_secret: str
    name: str = "GMOコイン（本番・現物）"
    private_url: str = "https://api.coin.z.com/private"
    public_url: str = "https://api.coin.z.com/public"
    order_path: str = "/v1/order"
    timeout: int = 15
    #: 実物に対する検証が済んでいないことを示す
    unverified: bool = True
    _rules: dict = field(default_factory=dict)

    # --- 銘柄 -------------------------------------------------------------

    def symbol(self, pair: str) -> str:
        """`btc_jpy` を GMO の**現物**銘柄に直す。

        GMO の銘柄名をそのまま渡されたら拒否する。**黙って通さない。**

        ## 大文字と小文字の区別が、ここでは意味を持つ

        この基盤の内部表記は小文字の `btc_jpy`。GMO のレバレッジ銘柄は
        大文字の `BTC_JPY`。**綴りは同じで、指すものが違う。**

        だから照合は大文字のまま、完全一致でやる。`upper()` してから
        照合すると、内部表記の `btc_jpy` まで巻き込んで全部拒否することになる
        （実際に一度そう書いて、全銘柄が通らなくなった）。
        """
        if pair in GMO_LEVERAGE_SYMBOLS:
            raise BrokerError(
                f"{pair} は GMOコインでは**レバレッジ**銘柄です。"
                "この基盤が扱うのは現物だけです"
                "（現物は BTC のように _JPY が付きません）。"
                f"現物を指すなら小文字で {pair.lower()} と書いてください"
            )
        try:
            return GMO_SPOT_SYMBOL[pair.lower()]
        except KeyError:
            raise BrokerError(
                f"GMOコインの現物銘柄に対応表がありません: {pair}"
                f"（対応: {', '.join(sorted(GMO_SPOT_SYMBOL))}）"
            ) from None

    # --- 通信 -------------------------------------------------------------

    def _open(self, req: urllib.request.Request):
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise BrokerError(f"HTTP {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BrokerError(f"取引所に到達できません: {exc}") from exc

        # **HTTP 200 でも失敗していることがある。** status を見ないと見逃す
        if payload.get("status") != 0:
            messages = payload.get("messages") or []
            detail = "; ".join(
                f"{m.get('message_code', '?')}: {m.get('message_string', '')}"
                for m in messages
            ) or "詳細不明"
            raise BrokerError(f"取引所がエラーを返しました（{detail}）")
        return payload.get("data")

    def _public_get(self, path: str):
        return self._open(urllib.request.Request(self.public_url + path))

    def sign(self, method: str, path: str, body: str = "") -> tuple[str, str]:
        """署名と、それに使った時刻を返す。

        署名する文字列は `時刻(ミリ秒) + メソッド + パス + 本文`。
        **パスに `/private` は含めない。** URL には含めるので混同しやすい。
        GET のクエリ文字列も含めない。
        """
        timestamp = str(int(time.time() * 1000))
        text = timestamp + method + path + body
        signature = hmac.new(
            self.api_secret.encode(), text.encode(), hashlib.sha256
        ).hexdigest()
        return timestamp, signature

    def _signed(self, method: str, path: str, body: dict | None = None):
        payload = json.dumps(body) if body is not None else ""
        timestamp, signature = self.sign(method, path, payload)
        headers = {
            "API-KEY": self.api_key,
            "API-TIMESTAMP": timestamp,
            "API-SIGN": signature,
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = payload.encode()
        return self._open(urllib.request.Request(
            self.private_url + path, data=data, headers=headers, method=method
        ))

    # --- 読む -------------------------------------------------------------

    def exchange_status(self) -> str:
        """取引所が開いているか。`OPEN` / `PREOPEN` / `MAINTENANCE`。

        GMOコインには定期メンテナンスがある。その最中の失敗は
        **配線の問題ではない。** 切り分けられないと原因を探し回ることになる。
        """
        return str(self._public_get("/v1/status").get("status", "UNKNOWN"))

    def trading_rules(self, pair: str) -> dict:
        """取引所が公開している注文のルールを読む（最小数量・刻み幅）。"""
        if not self._rules:
            self._rules = {row["symbol"]: row for row in self._public_get("/v1/symbols")}
        symbol = self.symbol(pair)
        if symbol not in self._rules:
            raise BrokerError(f"{symbol} の取引ルールが取得できませんでした")
        return self._rules[symbol]

    def fetch_price(self, pair: str) -> float:
        data = self._public_get(f"/v1/ticker?symbol={self.symbol(pair)}")
        if not data:
            raise BrokerError(f"価格の応答が空です: {pair}")
        return float(data[0]["last"])

    def fetch_balances(self) -> dict[str, float]:
        """**注文に取られていない**残高を返す。

        GMO は `amount`（保有量）と `available`（注文に使える量）を返す。
        `amount` を使うと、板に置いた注文の分まで使えることにしてしまう。
        """
        out: dict[str, float] = {}
        for asset in self._signed("GET", "/v1/account/assets") or []:
            amount = float(asset.get("available", 0.0))
            if amount > 0:
                out[str(asset["symbol"]).lower()] = amount
        return out

    # --- 書く -------------------------------------------------------------

    def conform(self, order: Order) -> Order:
        """取引所の刻み幅に合わせる。合わないと注文が弾かれる。

        数量は**切り捨てる**（意図より多く出さない）。
        価格は買いなら切り下げ、売りなら切り上げる。
        どちらも**板に並ぶ側に寄る**方向になり、意図せずテイカーにならない。
        """
        rules = self.trading_rules(order.pair)
        size = Decimal(str(order.amount)).quantize(
            Decimal(str(rules["sizeStep"])), rounding=ROUND_DOWN
        )
        minimum = Decimal(str(rules["minOrderSize"]))
        if size < minimum:
            raise BrokerError(
                f"{order.pair} の数量 {order.amount} は最小注文数量 {minimum} を下回ります"
            )
        price = order.price
        if price is not None:
            rounding = ROUND_DOWN if order.side == "buy" else ROUND_UP
            price = float(
                Decimal(str(price)).quantize(
                    Decimal(str(rules["tickSize"])), rounding=rounding
                )
            )
        return Order(order.pair, order.side, float(size), price)

    def order_body(self, order: Order) -> dict:
        """発注に使う本文を組み立てる。**送信はしない。**

        `place_order` はこれをそのまま送る。表示用に組み立て直すと、
        表示と実際の送信内容がずれる。
        """
        body = {
            "symbol": self.symbol(order.pair),
            "side": "BUY" if order.side == "buy" else "SELL",
            "executionType": "LIMIT" if order.price is not None else "MARKET",
            "size": str(order.amount),
        }
        if order.price is not None:
            body["price"] = str(int(order.price)) if float(order.price).is_integer() \
                else str(order.price)
        return body

    def place_order(self, order: Order) -> dict:
        conformed = self.conform(order)
        order_id = self._signed("POST", self.order_path, self.order_body(conformed))
        return {
            "orderId": order_id,
            "symbol": self.symbol(conformed.pair),
            "side": conformed.side,
            "amount": conformed.amount,
            "price": conformed.price,
        }
