"""取引所とのやりとり。

## 2つの実装

- `PaperBroker`  — 注文を出したことにして、状態をファイルに持つ。**既定**
- `BitbankBroker` — 実際に発注する。**この環境から検証できていない**

後者は正直に書いておく。この開発環境から取引所APIに到達できないため、
署名の組み立てや応答の解釈を**実物に対して確かめられていない**。
最小額で1回動かし、取引所の画面と突き合わせるまでは信用しないこと。

## 保有は必ず取引所から読む

`fetch_balances()` は、ローカルの記憶ではなく取引所の残高を返す。
手で1回売買しても、別のマシンから動かしても、プロセスが落ちても、
次の実行は正しい現在地から始まる。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
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
        })
        self._save(state)
        return {"paper": True, "status": "resting", "pair": order.pair,
                "side": order.side, "amount": order.amount, "price": order.price,
                "type": "limit"}

    def settle(self, prices: dict[str, float]) -> list[dict]:
        """価格が指値に届いていれば約定させる。届いていなければ残す。

        **ここが「指値は必ず約定する」を否定している箇所になる。**
        """
        state = self._load()
        balances, resting = state["balances"], state["open_orders"]
        filled, still_open = [], []

        for o in resting:
            price = prices.get(o["pair"])
            if price is None:
                still_open.append(o)
                continue
            reached = price <= o["price"] if o["side"] == "buy" else price >= o["price"]
            if not reached:
                still_open.append(o)
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

    def place_order(self, order: Order) -> dict:
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
        return self._signed_post("/user/spot/order", body)
