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

    価格は外から与える（`set_prices`）。バックテストではなく、
    「配線が正しいか」を確かめるためのものになる。
    約定は指値でも即時・全量成立として扱うので、
    **成績の見積もりには使えない**。それはバックテスト側の仕事になる。
    """

    state_path: Path
    name: str = "ペーパー（発注しません）"
    _prices: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.state_path = Path(self.state_path)
        if not self.state_path.exists():
            os.makedirs(self.state_path.parent, exist_ok=True)
            self._save({"jpy": 0.0})

    def _load(self) -> dict[str, float]:
        with open(self.state_path, encoding="utf-8") as fh:
            return {k: float(v) for k, v in json.load(fh).items()}

    def _save(self, balances: dict[str, float]) -> None:
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump(balances, fh, ensure_ascii=False, indent=2, sort_keys=True)

    def set_prices(self, prices: dict[str, float]) -> None:
        self._prices = dict(prices)

    def deposit(self, currency: str, amount: float) -> None:
        """初期資金を置く。ペーパー用。"""
        balances = self._load()
        balances[currency] = balances.get(currency, 0.0) + amount
        self._save(balances)

    def fetch_balances(self) -> dict[str, float]:
        return self._load()

    def fetch_price(self, pair: str) -> float:
        if pair not in self._prices:
            raise BrokerError(f"価格が設定されていません: {pair}（set_prices を呼んでください）")
        return self._prices[pair]

    def place_order(self, order: Order) -> dict:
        base = order.pair.split("_")[0]
        quote = order.pair.split("_")[1]
        price = order.price if order.price is not None else self.fetch_price(order.pair)
        cost = order.amount * price

        balances = self._load()
        if order.side == "buy":
            if balances.get(quote, 0.0) < cost:
                raise BrokerError(
                    f"{quote} が足りません（必要 {cost:,.0f} / 保有 {balances.get(quote, 0.0):,.0f}）"
                )
            balances[quote] = balances.get(quote, 0.0) - cost
            balances[base] = balances.get(base, 0.0) + order.amount
        else:
            if balances.get(base, 0.0) < order.amount - 1e-12:
                raise BrokerError(
                    f"{base} が足りません（必要 {order.amount} / 保有 {balances.get(base, 0.0)}）"
                )
            balances[base] = balances.get(base, 0.0) - order.amount
            balances[quote] = balances.get(quote, 0.0) + cost
        self._save(balances)

        return {
            "paper": True,
            "pair": order.pair,
            "side": order.side,
            "amount": order.amount,
            "price": price,
            "type": order.order_type,
        }


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
