import hashlib
import hmac
import json
from aiohttp import web
from aiogram import Bot
from .models import Orders


def verify_signature(secret: str | None, body: bytes, signature_header: str | None) -> bool:
    if not secret:
        return False
    if not signature_header:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return signature_header == digest


def create_app(bot: Bot, orders: Orders, admin_ids: list[int], secret: str | None):
    app = web.Application()

    async def handle(request: web.Request):
        raw = await request.read()
        if not verify_signature(secret, raw, request.headers.get("X-Signature")):
            return web.json_response({"ok": False}, status=401)
        try:
            payload = json.loads(raw.decode())
        except Exception:
            return web.json_response({"ok": False}, status=400)

        event_type = payload.get("update_type") or payload.get("type") or payload.get("event")
        if event_type != "invoice_paid":
            return web.json_response({"ok": True})

        invoice_id = payload.get("invoice_id") or (payload.get("payload") or {}).get("invoice_id")
        if not invoice_id:
            return web.json_response({"ok": True})

        order = await orders.with_user_by_invoice(int(invoice_id))
        if order:
            await orders.set_status(order["id"], "paid")
            text_admin = f"✅ Оплачен заказ #{order['id']}\n{order['location']} • {order['specs']} • {order['price']} RUB\nВыдайте товар."
            for admin_id in admin_ids:
                try:
                    await bot.send_message(admin_id, text_admin)
                except Exception:
                    pass
            if order.get("telegram_id"):
                try:
                    await bot.send_message(int(order["telegram_id"]), "✅ Оплата подтверждена. Ждите выдачи от администратора.")
                except Exception:
                    pass
        return web.json_response({"ok": True})

    app.add_routes([web.post("/cryptobot-webhook", handle)])
    return app


