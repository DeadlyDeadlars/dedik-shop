from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def build_main_menu() -> types.ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="🛒 Каталог")
    kb.button(text="📦 Мои заказы")
    kb.button(text="💳 Оплатить заказ")
    kb.button(text="🆘 Поддержка")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def setup_handlers(router: Router, services):
    db = services["db"]
    tariffs = services["tariffs"]
    users = services["users"]
    orders = services["orders"]
    cryptobot = services["cryptobot"]
    rub_usdt_rate: float = services.get("rub_usdt_rate", 0)
    admin_ids = services["admin_ids"]

    @router.message(F.text == "/start")
    async def start_cmd(msg: types.Message):
        await db.ensure_schema()
        await msg.answer("Главное меню", reply_markup=build_main_menu())

    @router.message(F.text == "🛒 Каталог")
    async def catalog(msg: types.Message):
        locs = await tariffs.list_locations()
        kb = InlineKeyboardBuilder()
        for loc in locs:
            kb.button(text=loc, callback_data=f"loc:{loc}")
        kb.adjust(1)
        await msg.answer("Выберите страну:", reply_markup=kb.as_markup())

    @router.callback_query(F.data.startswith("loc:"))
    async def list_tariffs(cb: types.CallbackQuery):
        loc = cb.data.split(":", 1)[1]
        ts = await tariffs.list_by_location(loc)
        if not ts:
            return await cb.message.edit_text(f"Тарифы для {loc} не найдены.")
        lines = []
        kb = InlineKeyboardBuilder()
        for t in ts:
            lines.append(f"{t['specs']}\nЦена: {t['price']} RUB")
            kb.button(text=f"Купить за {t['price']}", callback_data=f"buy:{t['id']}")
        kb.button(text="↩️ Назад", callback_data="back:catalog")
        kb.adjust(1)
        await cb.message.edit_text(
            f"Тарифы — {loc}:\n\n" + "\n\n".join(f"{i+1}. {s}" for i, s in enumerate(lines)),
            reply_markup=kb.as_markup(),
        )

    @router.callback_query(F.data == "back:catalog")
    async def back_catalog(cb: types.CallbackQuery):
        locs = await tariffs.list_locations()
        kb = InlineKeyboardBuilder()
        for loc in locs:
            kb.button(text=loc, callback_data=f"loc:{loc}")
        kb.adjust(1)
        await cb.message.edit_text("Выберите страну:", reply_markup=kb.as_markup())

    @router.callback_query(F.data.startswith("buy:"))
    async def buy_tariff(cb: types.CallbackQuery):
        t_id = int(cb.data.split(":", 1)[1])
        user = await users.upsert(cb.from_user.username, cb.from_user.id)
        # Convert RUB price to USDT (simple division by rate)
        price_row = await db.fetchrow("select price from tariffs where id=$1", t_id)
        price_rub = float(price_row["price"]) if price_row else 0.0
        # Prefer live rate from CryptoBot; fallback to env rate if provided
        if cryptobot:
            try:
                amount_usdt_exact = await cryptobot.rub_to_usdt(price_rub)
                amount_usdt = max(0.01, round(amount_usdt_exact, 2))
            except Exception:
                amount_usdt = max(0.01, round((price_rub / rub_usdt_rate), 2)) if rub_usdt_rate else 1
        else:
            amount_usdt = max(0.01, round((price_rub / rub_usdt_rate), 2)) if rub_usdt_rate else 1
        invoice = await cryptobot.create_invoice(asset="USDT", amount=amount_usdt, description=f"Order for tariff #{t_id}", payload={"tariffId": t_id, "userId": user["id"]})
        await orders.create(user_id=user["id"], tariff_id=t_id, invoice_id=invoice["invoice_id"])
        await cb.message.answer(f"Счет создан. Оплатите по ссылке:\n{invoice['pay_url']}")

    @router.message(F.text == "📦 Мои заказы")
    async def my_orders(msg: types.Message):
        user = await users.upsert(msg.from_user.username, msg.from_user.id)
        os = await orders.by_user(user["id"])
        if not os:
            return await msg.answer("У вас пока нет заказов.")
        lines = [
            f"#{o['id']} • {o['location']} • {o['specs']} • {o['price']} RUB • статус: {o['status']}" for o in os
        ]
        await msg.answer("\n".join(lines))

    @router.message(F.text == "🆘 Поддержка")
    async def support(msg: types.Message):
        await msg.answer("Связь с админом: @your_admin")

    @router.message(F.text == "💳 Оплатить заказ")
    async def pay_hint(msg: types.Message):
        await msg.answer("Откройте счет из каталога и оплатите ссылку.")

    # Admin
    def is_admin(user_id: int) -> bool:
        return user_id in admin_ids

    @router.message(F.text.startswith("/orders_paid"))
    async def orders_paid(msg: types.Message):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Недостаточно прав.")
        rows = await db.fetch(
            "select o.id, t.location, t.specs, t.price from orders o left join tariffs t on t.id=o.tariff_id where o.status='paid' order by o.id desc limit 20"
        )
        if not rows:
            return await msg.answer("Оплаченных заказов нет.")
        await msg.answer("\n".join(f"#{r['id']} • {r['location']} • {r['specs']} • {r['price']} RUB" for r in rows))

    @router.message(F.text.startswith("/set_delivered"))
    async def set_delivered(msg: types.Message):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Недостаточно прав.")
        parts = msg.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            return await msg.answer("Укажите номер заказа: /set_delivered <id>")
        order_id = int(parts[1])
        updated = await orders.set_status(order_id, "delivered")
        if not updated:
            return await msg.answer("Заказ не найден.")
        await msg.answer(f"Статус заказа #{order_id} обновлен на \"delivered\".")


