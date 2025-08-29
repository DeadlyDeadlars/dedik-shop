import httpx


class CryptoBot:
    def __init__(self, token: str):
        self._token = token
        self._base = "https://pay.crypt.bot/api"

    async def create_invoice(self, asset: str, amount: float, description: str, payload: dict | None = None):
        headers = {
            "Content-Type": "application/json",
            "Crypto-Pay-API-Token": self._token,
        }
        data = {
            "asset": asset,
            "amount": amount,
            "description": description,
            "payload": payload and __import__("json").dumps(payload),
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self._base}/createInvoice", headers=headers, json=data, timeout=20)
            r.raise_for_status()
            j = r.json()
            if not j.get("ok"):
                raise RuntimeError("CryptoBot API error")
            return j["result"]

    async def get_exchange_rates(self):
        headers = {
            "Crypto-Pay-API-Token": self._token,
        }
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self._base}/getExchangeRates", headers=headers, timeout=20)
            r.raise_for_status()
            j = r.json()
            if not j.get("ok"):
                raise RuntimeError("CryptoBot API error")
            return j["result"]

    async def rub_to_usdt(self, amount_rub: float) -> float:
        rates = await self.get_exchange_rates()
        # The API returns a list of {source, target, rate}
        rate = None
        for r in rates:
            if str(r.get("source")).upper() == "RUB" and str(r.get("target")).upper() == "USDT":
                rate = float(r.get("rate"))
                break
        if rate is None:
            # Fallback: try inverse path USDT->RUB
            for r in rates:
                if str(r.get("source")).upper() == "USDT" and str(r.get("target")).upper() == "RUB":
                    inv = float(r.get("rate"))
                    rate = 1.0 / inv if inv else None
                    break
        if rate is None:
            raise RuntimeError("RUB→USDT rate not available")
        return amount_rub * rate


