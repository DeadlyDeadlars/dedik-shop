from aiogram import Router, types, F
from aiogram.types import LinkPreviewOptions
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def build_main_menu() -> types.ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="🛒 Каталог серверов")
    kb.button(text="📦 Мои заказы")
    kb.button(text="👤 Мой профиль")
    kb.button(text="🎁 Промокоды")
    kb.button(text="🗑️ Очистить промокод")
    kb.button(text="👥 Реферальная система")
    kb.button(text="🆘 Техподдержка")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=False)


def setup_handlers(router: Router, services):
    db = services["db"]
    tariffs = services["tariffs"]
    users = services["users"]
    orders = services["orders"]
    cryptobot = services["cryptobot"]
    rub_usdt_rate: float = services.get("rub_usdt_rate", 0)
    price_markup_percent: float = services.get("price_markup_percent", 0)
    admin_ids = services["admin_ids"]
    log_channel_id = services.get("log_channel_id")
    support_contact = services.get("support_contact") or "@your_admin"

    def apply_markup(price_rub: float) -> int:
        # Return integer RUB price with markup applied
        try:
            return int(round(price_rub * (1.0 + (price_markup_percent or 0) / 100.0)))
        except Exception:
            return int(round(price_rub))

    @router.message(F.text.startswith("/start"))
    async def start_cmd(msg: types.Message):
        await db.ensure_schema()
        
        # Проверяем реферальную ссылку
        ref_id = None
        if msg.text.startswith("/start ref"):
            try:
                ref_id = int(msg.text.split("ref")[1])
            except (IndexError, ValueError):
                pass
        
        # Создаем или обновляем пользователя
        user = await users.upsert(msg.from_user.username, msg.from_user.id)
        
        # Если это реферальная регистрация
        if ref_id and ref_id != user["id"]:
            # Проверяем, что пользователь еще не имеет реферера
            current_user = await db.fetchrow("select referrer_id from users where id=?", user["id"])
            if not current_user or not current_user["referrer_id"]:
                # Устанавливаем реферера
                await db.execute("update users set referrer_id=? where id=?", ref_id, user["id"])
                
                # Отправляем уведомление рефереру
                try:
                    ref_user = await db.fetchrow("select telegram_id from users where id=?", ref_id)
                    if ref_user:
                        await msg.bot.send_message(
                            ref_user["telegram_id"],
                            f"🎉 <b>Новый реферал!</b>\n\n"
                            f"👤 Пользователь @{msg.from_user.username or msg.from_user.id} "
                            f"присоединился по вашей ссылке!\n\n"
                            f"💰 Вы получите бонус за его первый заказ!",
                            parse_mode="HTML"
                        )
                except Exception:
                    pass
        
        welcome_text = "🚀 <b>Добро пожаловать в DeadlyVDS</b> 🚀\n\n"
        if ref_id:
            welcome_text += "🎁 <b>Вы присоединились по реферальной ссылке!</b>\n\n"
        
        welcome_text += (
            "🔥 <b>Мощные VPS серверы по лучшим ценам</b>\n"
            "🌍 <b>Локации по всему миру</b>\n"
            "⚡ <b>Мгновенная активация</b>\n\n"
            "Выберите действие ниже:"
        )
        
        await msg.answer(
            welcome_text,
            reply_markup=build_main_menu(),
            parse_mode="HTML",
        )

    @router.message(F.text == "🛒 Каталог серверов")
    async def catalog(msg: types.Message):
        user = await users.upsert(msg.from_user.username, msg.from_user.id)
        
        # Проверяем активный промокод пользователя
        active_promo = await db.fetchrow(
            "select * from user_active_promocodes where user_id=?",
            user["id"]
        )
        
        locs = await tariffs.list_locations()
        kb = InlineKeyboardBuilder()
        if not locs:
            return await msg.answer(
                "😔 <b>Каталог пуст</b>\n\n"
                "📝 <i>Администратору необходимо выполнить команду /seed для загрузки тарифов</i>\n\n"
                "⏳ <i>Попробуйте позже или обратитесь в поддержку</i>",
                parse_mode="HTML"
            )
        
        # Если у пользователя есть активный промокод, показываем информацию о нем
        promo_info = ""
        if active_promo:
            promo_info = (
                f"\n🎁 <b>Активный промокод:</b> <code>{active_promo['promo_code']}</code>\n"
                f"💰 <b>Скидка:</b> {active_promo['discount_percent']}%\n"
            )
            if active_promo['min_amount'] > 0:
                promo_info += f"📊 <b>Мин. сумма заказа:</b> {active_promo['min_amount']} RUB\n"
            promo_info += "\n"
        
        for loc in locs:
            low = loc.lower()
            flag = (
                "🇷🇺" if "рос" in low else
                ("🇺🇸" if ("сша" in low or "usa" in low) else
                 ("🇸🇬" if ("сингап" in low or "singap" in low) else
                  ("🇫🇮" if ("фин" in low or "finland" in low) else
                   ("🇩🇪" if ("гер" in low or "germ" in low) else
                    ("🇫🇷" if ("франц" in low or "france" in low) else
                     ("🇳🇱" if ("нидер" in low or "neder" in low or "nether" in low) else
                      ("🇧🇬" if ("болгар" in low or "bulgar" in low) else
                       ("🇪🇸" if ("испан" in low or "spain" in low) else "📍"))))))))
            )
            kb.button(text=f"{flag} {loc}", callback_data=f"loc:{loc}")
        kb.adjust(2)
        
        message_text = "🌍 <b>Выберите страну для вашего сервера:</b>\n\n"
        if active_promo:
            message_text += promo_info
        message_text += "💡 <i>Каждая локация оптимизирована для максимальной производительности</i>"
        
        await msg.answer(
            message_text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

    @router.callback_query(F.data.startswith("loc:"))
    async def list_tariffs(cb: types.CallbackQuery):
        loc = cb.data.split(":", 1)[1]
        ts = await tariffs.list_by_location(loc)
        if not ts:
            return await cb.message.edit_text(
                f"😔 <b>Тарифы для {loc} не найдены</b>\n\n"
                "📝 <i>Возможно, администратор еще не добавил тарифы для этой локации</i>\n\n"
                "🔄 <i>Попробуйте выбрать другую страну или обратитесь в поддержку</i>",
                parse_mode="HTML"
            )
        kb = InlineKeyboardBuilder()
        for t in ts:
            price_marked = apply_markup(float(t['price']))
            label_full = f"{price_marked} RUB • {t['specs']}"
            label = (label_full[:60] + '…') if len(label_full) > 60 else label_full
            kb.button(text=label, callback_data=f"buy:{t['id']}")
        kb.button(text="↩️ Назад", callback_data="back:catalog")
        kb.adjust(1)
        await cb.message.edit_text(
            f"🖥️ <b>Тарифы — {loc}</b> 🖥️\n\n"
            f"💻 <i>Выберите конфигурацию сервера:</i>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    @router.callback_query(F.data == "back:catalog")
    async def back_catalog(cb: types.CallbackQuery):
        locs = await tariffs.list_locations()
        kb = InlineKeyboardBuilder()
        for loc in locs:
            kb.button(text=loc, callback_data=f"loc:{loc}")
        kb.adjust(1)
        await cb.message.edit_text(
            "🌍 <b>Выберите страну для вашего сервера:</b>\n\n"
            "💡 <i>Каждая локация оптимизирована для максимальной производительности</i>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

    @router.callback_query(F.data.startswith("buy:"))
    async def buy_tariff(cb: types.CallbackQuery):
        t_id = int(cb.data.split(":", 1)[1])
        user = await users.upsert(cb.from_user.username, cb.from_user.id)
        
        # Convert RUB price to USDT (simple division by rate)
        price_row = await db.fetchrow("select price from tariffs where id=$1", t_id)
        price_rub = float(price_row["price"]) if price_row else 0.0
        price_rub_marked = float(apply_markup(price_rub))
        
        # Получаем баланс бонусов пользователя
        user_info = await db.fetchrow("select bonus_balance from users where id=?", user["id"])
        bonus_balance = user_info['bonus_balance'] if user_info else 0
        
        # Проверяем активный промокод пользователя
        active_promo = await db.fetchrow(
            "select * from user_active_promocodes where user_id=?",
            user["id"]
        )
        
        # Создаем клавиатуру для выбора промокода и бонусов
        kb_promo = InlineKeyboardBuilder()
        
        # Если есть активный промокод, показываем его применение
        if active_promo:
            # Проверяем минимальную сумму заказа
            if active_promo['min_amount'] > 0 and price_rub_marked < active_promo['min_amount']:
                kb_promo.button(text="💳 Оплатить без промокода", callback_data=f"pay:{t_id}:0")
                kb_promo.button(text="🎁 Ввести другой промокод", callback_data=f"promo:{t_id}")
                if bonus_balance > 0:
                    kb_promo.button(text=f"💰 Использовать бонусы ({bonus_balance} RUB)", callback_data=f"bonus:{t_id}")
                
                await cb.message.edit_text(
                    f"🛒 <b>Оформление заказа</b> 🛒\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📦 <b>Тариф:</b> <code>#{t_id}</code>\n"
                    f"💰 <b>Цена:</b> <code>{int(price_rub_marked)} RUB</code>\n\n"
                    f"🎁 <b>Активный промокод:</b> <code>{active_promo['promo_code']}</code>\n"
                    f"💰 <b>Скидка:</b> {active_promo['discount_percent']}%\n"
                    f"📊 <b>Мин. сумма заказа:</b> {active_promo['min_amount']} RUB\n\n"
                    f"❌ <i>Сумма заказа меньше минимальной для применения промокода</i>",
                    reply_markup=kb_promo.as_markup(),
                    parse_mode="HTML"
                )
                return
            else:
                # Применяем промокод автоматически
                discount_amount = int(price_rub_marked * active_promo['discount_percent'] / 100)
                final_price = price_rub_marked - discount_amount
                
                kb_promo.button(text=f"💳 Оплатить со скидкой ({final_price} RUB)", callback_data=f"pay_promo:{t_id}:{active_promo['promo_code']}")
                kb_promo.button(text="💳 Оплатить без промокода", callback_data=f"pay:{t_id}:0")
                kb_promo.button(text="🎁 Ввести другой промокод", callback_data=f"promo:{t_id}")
                if bonus_balance > 0:
                    kb_promo.button(text=f"💰 Использовать бонусы ({bonus_balance} RUB)", callback_data=f"bonus:{t_id}")
                
                await cb.message.edit_text(
                    f"🛒 <b>Оформление заказа</b> 🛒\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📦 <b>Тариф:</b> <code>#{t_id}</code>\n"
                    f"💰 <b>Цена:</b> <code>{int(price_rub_marked)} RUB</code>\n\n"
                    f"🎁 <b>Активный промокод:</b> <code>{active_promo['promo_code']}</code>\n"
                    f"💰 <b>Скидка:</b> {active_promo['discount_percent']}% (-{discount_amount} RUB)\n"
                    f"💳 <b>Итоговая цена:</b> <code>{final_price} RUB</code>\n\n"
                    f"✅ <i>Промокод будет применен автоматически</i>",
                    reply_markup=kb_promo.as_markup(),
                    parse_mode="HTML"
                )
                return
        else:
            # Нет активного промокода
            kb_promo.button(text="💳 Оплатить без промокода", callback_data=f"pay:{t_id}:0")
            kb_promo.button(text="🎁 Ввести промокод", callback_data=f"promo:{t_id}")
            if bonus_balance > 0:
                kb_promo.button(text=f"💰 Использовать бонусы ({bonus_balance} RUB)", callback_data=f"bonus:{t_id}")
            kb_promo.adjust(1)
            
            await cb.message.edit_text(
                f"🛒 <b>Оформление заказа</b> 🛒\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📦 <b>Тариф:</b> <code>#{t_id}</code>\n"
                f"💰 <b>Цена:</b> <code>{int(price_rub_marked)} RUB</code>\n\n"
                "🎁 <i>Хотите использовать промокод?</i>",
                reply_markup=kb_promo.as_markup(),
                parse_mode="HTML"
            )
    
    @router.callback_query(F.data.startswith("promo:"))
    async def enter_promocode(cb: types.CallbackQuery):
        t_id = int(cb.data.split(":", 1)[1])
        
        # Сохраняем состояние ожидания промокода
        await cb.message.edit_text(
            f"🎁 <b>Введите промокод</b> 🎁\n\n"
            f"📝 <i>Отправьте промокод в следующем сообщении</i>\n\n"
            f"💡 <i>Или нажмите кнопку ниже для оплаты без промокода</i>",
            parse_mode="HTML"
        )
        
        # Создаем временное состояние для ожидания промокода
        await cb.answer("Введите промокод в следующем сообщении")
    
    @router.callback_query(F.data.startswith("bonus:"))
    async def use_bonus(cb: types.CallbackQuery):
        t_id = int(cb.data.split(":", 1)[1])
        user = await users.upsert(cb.from_user.username, cb.from_user.id)
        
        # Получаем баланс бонусов
        user_info = await db.fetchrow("select bonus_balance from users where id=?", user["id"])
        bonus_balance = user_info['bonus_balance'] if user_info else 0
        
        if bonus_balance <= 0:
            await cb.answer("У вас нет бонусов для использования")
            return
        
        # Получаем цену тарифа
        price_row = await db.fetchrow("select price from tariffs where id=$1", t_id)
        price_rub = float(price_row["price"]) if price_row else 0.0
        price_rub_marked = float(apply_markup(price_rub))
        
        # Определяем сколько бонусов можно использовать
        bonus_to_use = min(bonus_balance, price_rub_marked)
        final_price = max(0, price_rub_marked - bonus_to_use)
        
        # Создаем заказ с использованием бонусов
        invoice = await cryptobot.create_invoice(
            asset="USDT", 
            amount=max(0.01, round((final_price / rub_usdt_rate), 2)) if rub_usdt_rate else 1, 
            description=f"Order for tariff #{t_id} (bonus used)", 
            payload={"tariffId": t_id, "userId": user["id"]}
        )
        
        order = await orders.create(
            user_id=user["id"], 
            tariff_id=t_id, 
            invoice_id=invoice["invoice_id"]
        )
        
        # Обновляем дополнительные поля
        await db.execute(
            "update orders set discount_amount=?, final_price=? where id=?",
            int(bonus_to_use), int(final_price), order["id"]
        )
        
        # Списываем использованные бонусы
        await db.execute(
            "update users set bonus_balance=bonus_balance-? where id=?",
            bonus_to_use, user["id"]
        )
        
        # Создаем клавиатуру оплаты
        kb_pay = InlineKeyboardBuilder()
        kb_pay.button(text="💳 Оплатить", url=invoice['pay_url'])
        kb_pay.button(text="✅ Я оплатил", callback_data=f"paid:{order['id']}")
        kb_pay.adjust(1, 1)
        
        # Формируем сообщение
        message_text = (
            "🎉 <b>Счет создан с использованием бонусов!</b> 🎉\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 <b>Тариф:</b> <code>#{t_id}</code>\n"
            f"💰 <b>Исходная цена:</b> <code>{int(price_rub_marked)} RUB</code>\n"
            f"🎁 <b>Использовано бонусов:</b> <code>{int(bonus_to_use)} RUB</code>\n"
            f"💳 <b>Итоговая цена:</b> <code>{int(final_price)} RUB</code>\n"
            f"🔗 <b>Счет:</b> <code>{invoice['invoice_id']}</code>\n"
            f"💵 <b>К оплате:</b> <code>~ {max(0.01, round((final_price / rub_usdt_rate), 2)) if rub_usdt_rate else 1} USDT</code>\n\n"
            "💳 <i>Нажмите кнопку ниже для перехода к оплате</i>\n"
            "✅ <i>После оплаты нажмите \"Я оплатил\" для уведомления администратора</i>"
        )
        
        await cb.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=kb_pay.as_markup(),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    
    @router.callback_query(F.data.startswith("pay_promo:"))
    async def process_payment_with_promo(cb: types.CallbackQuery):
        parts = cb.data.split(":")
        t_id = int(parts[1])
        promo_code = parts[2]
        
        user = await users.upsert(cb.from_user.username, cb.from_user.id)
        
        # Получаем активный промокод пользователя
        active_promo = await db.fetchrow(
            "select * from user_active_promocodes where user_id=? and promo_code=?",
            user["id"], promo_code
        )
        
        if not active_promo:
            await cb.answer("Промокод не найден или недействителен")
            return
        
        # Convert RUB price to USDT
        price_row = await db.fetchrow("select price from tariffs where id=$1", t_id)
        price_rub = float(price_row["price"]) if price_row else 0.0
        price_rub_marked = float(apply_markup(price_rub))
        
        # Применяем промокод
        discount_amount = int(price_rub_marked * active_promo['discount_percent'] / 100)
        final_price = price_rub_marked - discount_amount
        
        # Prefer live rate from CryptoBot; fallback to env rate if provided
        if cryptobot:
            try:
                amount_usdt_exact = await cryptobot.rub_to_usdt(final_price)
                amount_usdt = max(0.01, round(amount_usdt_exact, 2))
            except Exception:
                amount_usdt = max(0.01, round((final_price / rub_usdt_rate), 2)) if rub_usdt_rate else 1
        else:
            amount_usdt = max(0.01, round((final_price / rub_usdt_rate), 2)) if rub_usdt_rate else 1
        
        # Создаем заказ
        invoice = await cryptobot.create_invoice(
            asset="USDT", 
            amount=amount_usdt, 
            description=f"Order for tariff #{t_id} with promo {promo_code}", 
            payload={"tariffId": t_id, "userId": user["id"]}
        )
        
        # Создаем заказ с базовыми полями
        order = await orders.create(
            user_id=user["id"], 
            tariff_id=t_id, 
            invoice_id=invoice["invoice_id"]
        )
        
        # Обновляем дополнительные поля
        await db.execute(
            "update orders set promo_code=?, discount_amount=?, final_price=? where id=?",
            promo_code, discount_amount, final_price, order["id"]
        )
        
        # Удаляем активный промокод пользователя (так как он использован)
        await db.execute(
            "delete from user_active_promocodes where user_id=? and promo_code=?",
            user["id"], promo_code
        )
        
        # Увеличиваем счетчик использований промокода
        promo_info = await db.fetchrow("select id from promocodes where code=?", promo_code)
        if promo_info:
            await db.execute("update promocodes set used_count=used_count+1 where id=?", promo_info["id"])
        
        # Создаем клавиатуру оплаты
        kb_pay = InlineKeyboardBuilder()
        kb_pay.button(text="💳 Оплатить", url=invoice['pay_url'])
        kb_pay.button(text="✅ Я оплатил", callback_data=f"paid:{order['id']}")
        kb_pay.adjust(1, 1)
        
        # Формируем сообщение
        message_text = (
            "🎉 <b>Счет успешно создан!</b> 🎉\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 <b>Тариф:</b> <code>#{t_id}</code>\n"
            f"💰 <b>Исходная цена:</b> <code>{int(price_rub_marked)} RUB</code>\n"
            f"🎁 <b>Промокод:</b> <code>{promo_code}</code>\n"
            f"💸 <b>Скидка:</b> <code>{discount_amount} RUB</code>\n"
            f"💳 <b>Итоговая цена:</b> <code>{int(final_price)} RUB</code>\n"
            f"💎 <b>К оплате:</b> <code>{amount_usdt} USDT</code>\n\n"
            "🔗 <i>Нажмите кнопку ниже для оплаты</i>"
        )
        
        await cb.message.edit_text(
            message_text,
            reply_markup=kb_pay.as_markup(),
            parse_mode="HTML"
        )
    
    @router.callback_query(F.data.startswith("pay:"))
    async def process_payment(cb: types.CallbackQuery):
        parts = cb.data.split(":")
        t_id = int(parts[1])
        promo_id = int(parts[2]) if len(parts) > 2 else 0
        
        user = await users.upsert(cb.from_user.username, cb.from_user.id)
        
        # Convert RUB price to USDT
        price_row = await db.fetchrow("select price from tariffs where id=$1", t_id)
        price_rub = float(price_row["price"]) if price_row else 0.0
        price_rub_marked = float(apply_markup(price_rub))
        
        # Применяем промокод если есть
        discount_amount = 0
        final_price = price_rub_marked
        promo_code = None
        
        if promo_id > 0:
            promo = await db.fetchrow("select * from promocodes where id=? and is_active=1", promo_id)
            if promo and promo['used_count'] < promo['max_uses']:
                if price_rub_marked >= promo['min_amount']:
                    discount_amount = int(price_rub_marked * promo['discount_percent'] / 100)
                    final_price = price_rub_marked - discount_amount
                    promo_code = promo['code']
                    
                    # Увеличиваем счетчик использований
                    await db.execute("update promocodes set used_count=used_count+1 where id=?", promo_id)
        
        # Prefer live rate from CryptoBot; fallback to env rate if provided
        if cryptobot:
            try:
                amount_usdt_exact = await cryptobot.rub_to_usdt(final_price)
                amount_usdt = max(0.01, round(amount_usdt_exact, 2))
            except Exception:
                amount_usdt = max(0.01, round((final_price / rub_usdt_rate), 2)) if rub_usdt_rate else 1
        else:
            amount_usdt = max(0.01, round((final_price / rub_usdt_rate), 2)) if rub_usdt_rate else 1
        
        # Создаем заказ
        order_data = {
            "user_id": user["id"],
            "tariff_id": t_id,
            "promo_code": promo_code,
            "discount_amount": discount_amount,
            "original_price": price_rub_marked,
            "final_price": final_price
        }
        
        invoice = await cryptobot.create_invoice(
            asset="USDT", 
            amount=amount_usdt, 
            description=f"Order for tariff #{t_id}", 
            payload={"tariffId": t_id, "userId": user["id"]}
        )
        
        # Создаем заказ с базовыми полями
        order = await orders.create(
            user_id=user["id"], 
            tariff_id=t_id, 
            invoice_id=invoice["invoice_id"]
        )
        
        # Обновляем дополнительные поля если есть
        if promo_code or discount_amount > 0:
            update_fields = []
            update_values = []
            if promo_code:
                update_fields.append("promo_code=?")
                update_values.append(promo_code)
            if discount_amount > 0:
                update_fields.append("discount_amount=?")
                update_values.append(discount_amount)
            
            if update_fields:
                update_values.append(order["id"])
                await db.execute(f"update orders set {', '.join(update_fields)} where id=?", *update_values)
        
        # Создаем клавиатуру оплаты
        kb_pay = InlineKeyboardBuilder()
        kb_pay.button(text="💳 Оплатить", url=invoice['pay_url'])
        kb_pay.button(text="✅ Я оплатил", callback_data=f"paid:{order['id']}")
        kb_pay.adjust(1, 1)
        
        # Формируем сообщение
        message_text = (
            "🎉 <b>Счет успешно создан!</b> 🎉\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 <b>Тариф:</b> <code>#{t_id}</code>\n"
            f"💰 <b>Исходная цена:</b> <code>{int(price_rub_marked)} RUB</code>\n"
        )
        
        if discount_amount > 0:
            message_text += (
                f"🎁 <b>Промокод:</b> <code>{promo_code}</code>\n"
                f"💸 <b>Скидка:</b> <code>{discount_amount} RUB</code>\n"
                f"💳 <b>Итоговая цена:</b> <code>{int(final_price)} RUB</code>\n"
            )
        
        message_text += (
            f"🔗 <b>Счет:</b> <code>{invoice['invoice_id']}</code>\n"
            f"💵 <b>К оплате:</b> <code>~ {amount_usdt} USDT</code>\n\n"
            "💳 <i>Нажмите кнопку ниже для перехода к оплате</i>\n"
            "✅ <i>После оплаты нажмите \"Я оплатил\" для уведомления администратора</i>"
        )
        
        await cb.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=kb_pay.as_markup(),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

    @router.message(F.text == "📦 Мои заказы")
    async def my_orders(msg: types.Message):
        user = await users.upsert(msg.from_user.username, msg.from_user.id)
        os = await orders.by_user(user["id"])
        if not os:
            return await msg.answer(
                "📦 <b>Мои заказы</b>\n\n"
                "😔 У вас пока нет заказов.\n\n"
                "🛒 <i>Перейдите в каталог, чтобы сделать первый заказ!</i>",
                parse_mode="HTML"
            )
        
        lines = []
        for o in os:
            price_marked = apply_markup(float(o['price']))
            status_emoji = {
                "created": "⏳",
                "paid": "✅", 
                "delivered": "🎉"
            }.get(o['status'], "❓")
            
            lines.append(
                f"{status_emoji} <b>Заказ #{o['id']}</b>\n"
                f"📍 <b>Локация:</b> {o['location']}\n"
                f"⚙️ <b>Характеристики:</b> {o['specs']}\n"
                f"💰 <b>Цена:</b> {price_marked} RUB\n"
                f"📊 <b>Статус:</b> {o['status']}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
        
        await msg.answer(
            f"📦 <b>Мои заказы</b> 📦\n\n" + "\n\n".join(lines),
            parse_mode="HTML"
        )

    @router.callback_query(F.data.startswith("paid:"))
    async def user_paid(cb: types.CallbackQuery):
        order_id = int(cb.data.split(":", 1)[1])
        user = await users.upsert(cb.from_user.username, cb.from_user.id)
        
        # Get order details
        order_row = await db.fetchrow(
            "select o.*, t.location, t.specs, t.price from orders o left join tariffs t on t.id=o.tariff_id where o.id=?",
            order_id
        )
        
        if not order_row:
            return await cb.answer("Заказ не найден")
        
        if order_row["user_id"] != user["id"]:
            return await cb.answer("Это не ваш заказ")
        
        # Send log to channel with admin buttons
        if log_channel_id:
            price_marked = apply_markup(float(order_row['price']))
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ Оплатил", callback_data=f"logpaid:{order_id}")
            kb.button(text="❌ Не оплатил", callback_data=f"logunpaid:{order_id}")
            kb.adjust(2)
            text = (
                f"🧾 Новый заказ #{order_id}\n"
                f"👤 Пользователь: @{cb.from_user.username or cb.from_user.id}\n"
                f"📦 Товар: тариф #{order_row['tariff_id']}\n"
                f"📍 Локация: {order_row['location']}\n"
                f"⚙️ Характеристики: {order_row['specs']}\n"
                f"💰 Цена: {int(price_marked)} RUB\n"
                f"🧾 invoice_id: {order_row['invoice_id']}\n"
                f"🔗 Пользователь утверждает, что оплатил"
            )
            try:
                await cb.bot.send_message(log_channel_id, text, reply_markup=kb.as_markup())
                await cb.answer("✅ Заявка отправлена администратору")
            except Exception:
                await cb.answer("❌ Ошибка отправки заявки")
        else:
            await cb.answer("✅ Заявка принята")

    @router.message(F.text == "🎁 Промокоды")
    async def promocodes(msg: types.Message):
        user = await users.upsert(msg.from_user.username, msg.from_user.id)
        
        # Получаем активные промокоды
        active_promos = await db.fetch(
            "select code, discount_percent, min_amount, max_uses, used_count from promocodes where is_active=true and (max_uses=0 or used_count < max_uses)"
        )
        
        if not active_promos:
            await msg.answer(
                "🎁 <b>Промокоды</b> 🎁\n\n"
                "😔 <i>В данный момент нет активных промокодов</i>\n\n"
                "📢 <i>Следите за нашими обновлениями!</i>",
                parse_mode="HTML"
            )
            return
        
        text = "🎁 <b>Активные промокоды</b> 🎁\n\n"
        for promo in active_promos:
            remaining_uses = "∞" if promo['max_uses'] == 0 else promo['max_uses'] - promo['used_count']
            text += (
                f"💎 <b>Код:</b> <code>{promo['code']}</code>\n"
                f"💰 <b>Скидка:</b> {promo['discount_percent']}%\n"
                f"📊 <b>Мин. сумма:</b> {promo['min_amount']} RUB\n"
                f"🎯 <b>Осталось использований:</b> {remaining_uses}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )
        
        text += "💡 <i>Используйте промокод при оформлении заказа</i>"
        
        await msg.answer(text, parse_mode="HTML")
    
    @router.message(F.text == "👥 Реферальная система")
    async def referral_system(msg: types.Message):
        user = await users.upsert(msg.from_user.username, msg.from_user.id)
        
        # Получаем реферальную ссылку
        bot_info = await msg.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref{user['id']}"
        
        # Получаем статистику рефералов
        ref_users = await db.fetch("select username, telegram_id, created_at from users where referrer_id=? order by created_at desc", user["id"])
        
        # Получаем награды за рефералов
        ref_rewards = await db.fetchrow("select sum(reward_amount) as total from referral_rewards where referrer_id=?", user["id"])
        total_rewards = ref_rewards['total'] if ref_rewards and ref_rewards['total'] else 0
        
        text = (
            f"👥 <b>Реферальная система</b> 👥\n\n"
            f"🔗 <b>Ваша реферальная ссылка:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"💰 <b>Заработано с рефералов:</b> <code>{total_rewards}</code> RUB\n\n"
            f"📊 <b>Статистика приглашений:</b>\n"
        )
        
        if ref_users:
            for i, ref_user in enumerate(ref_users[:10], 1):  # Показываем только первые 10
                username = f"@{ref_user['username']}" if ref_user['username'] else f"ID: {ref_user['telegram_id']}"
                date = ref_user['created_at'].strftime("%d.%m.%Y") if ref_user['created_at'] else "N/A"
                text += f"{i}. {username} - {date}\n"
            
            if len(ref_users) > 10:
                text += f"... и еще {len(ref_users) - 10} пользователей\n"
        else:
            text += "😔 <i>Пока никто не присоединился по вашей ссылке</i>\n"
        
        text += "\n💡 <i>Приглашайте друзей и получайте бонусы за каждый заказ!</i>"
        
        await msg.answer(text, parse_mode="HTML")
    
    @router.message(F.text == "🆘 Техподдержка")
    async def support(msg: types.Message):
        await msg.answer(
            f"🆘 <b>Поддержка</b> 🆘\n\n"
            f"📞 <b>Связь с администратором:</b> {support_contact}\n\n"
            "💬 <i>Опишите вашу проблему или вопрос</i>\n"
            "⏰ <i>Ответим в кратчайшие сроки</i>",
            parse_mode="HTML"
        )
    
    # Обработчик для ввода промокодов
    @router.message(lambda msg: msg.text and len(msg.text) >= 3 and msg.text.isupper())
    async def handle_promocode(msg: types.Message):
        user = await users.upsert(msg.from_user.username, msg.from_user.id)
        
        # Проверяем, есть ли активный промокод
        promo = await db.fetchrow(
            "select * from promocodes where code=? and is_active=1 and (max_uses=0 or used_count < max_uses)",
            msg.text
        )
        
        if not promo:
            await msg.answer(
                "❌ <b>Промокод не найден</b>\n\n"
                "😔 <i>Проверьте правильность написания или попробуйте другой промокод</i>\n\n"
                "🎁 <i>Активные промокоды можно посмотреть в разделе \"Промокоды\"</i>",
                parse_mode="HTML"
            )
            return
        
        # Удаляем предыдущий активный промокод пользователя (если есть)
        await db.execute(
            "delete from user_active_promocodes where user_id=?",
            user["id"]
        )
        
        # Сохраняем новый активный промокод для пользователя
        await db.execute(
            "insert into user_active_promocodes (user_id, promo_code, discount_percent, min_amount) values (?, ?, ?, ?)",
            user["id"], promo['code'], promo['discount_percent'], promo['min_amount']
        )
        
        # Проверяем минимальную сумму
        if promo['min_amount'] > 0:
            await msg.answer(
                f"💡 <b>Промокод найден!</b>\n\n"
                f"🎁 <b>Код:</b> <code>{promo['code']}</code>\n"
                f"💰 <b>Скидка:</b> {promo['discount_percent']}%\n"
                f"📊 <b>Минимальная сумма заказа:</b> {promo['min_amount']} RUB\n\n"
                f"🛒 <i>Перейдите в каталог и выберите тариф для применения промокода</i>",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"🎉 <b>Промокод найден!</b>\n\n"
                f"🎁 <b>Код:</b> <code>{promo['code']}</code>\n"
                f"💰 <b>Скидка:</b> {promo['discount_percent']}%\n\n"
                f"🛒 <i>Перейдите в каталог и выберите тариф для применения промокода</i>",
                parse_mode="HTML"
            )

    @router.message(F.text == "🗑️ Очистить промокод")
    async def clear_promocode(msg: types.Message):
        user = await users.upsert(msg.from_user.username, msg.from_user.id)
        
        # Удаляем активный промокод пользователя
        result = await db.execute(
            "delete from user_active_promocodes where user_id=?",
            user["id"]
        )
        
        await msg.answer(
            "🗑️ <b>Промокод очищен!</b>\n\n"
            "✅ <i>Активный промокод был удален из вашего профиля</i>\n\n"
            "🛒 <i>Теперь вы можете ввести новый промокод или совершить покупку без скидки</i>",
            parse_mode="HTML"
        )

    @router.message(F.text == "👤 Мой профиль")
    async def profile(msg: types.Message):
        user = await users.upsert(msg.from_user.username, msg.from_user.id)
        os = await orders.by_user(user["id"])
        total = len(os)
        paid = sum(1 for o in os if o.get("status") == "paid")
        delivered = sum(1 for o in os if o.get("status") == "delivered")
        created = total - paid - delivered
        
        # Получаем реферальную статистику
        ref_count = await db.fetchrow("select count(*) as c from users where referrer_id=?", user["id"])
        ref_count = ref_count['c'] if ref_count else 0
        
        # Получаем баланс бонусов
        bonus_balance = await db.fetchrow("select bonus_balance from users where id=?", user["id"])
        bonus_balance = bonus_balance['bonus_balance'] if bonus_balance else 0
        
        text = (
            f"👤 <b>Профиль пользователя</b> 👤\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 <b>ID:</b> <code>{msg.from_user.id}</code>\n"
            f"👤 <b>Username:</b> @{msg.from_user.username or '—'}\n\n"
            f"📊 <b>Статистика заказов:</b>\n"
            f"⏳ <b>Ожидают оплаты:</b> <code>{created}</code>\n"
            f"✅ <b>Оплачены:</b> <code>{paid}</code>\n"
            f"🎉 <b>Выданы:</b> <code>{delivered}</code>\n"
            f"📈 <b>Всего заказов:</b> <code>{total}</code>\n\n"
            f"🎁 <b>Бонусный баланс:</b> <code>{bonus_balance}</code> RUB\n"
            f"👥 <b>Приглашено друзей:</b> <code>{ref_count}</code>"
        )
        await msg.answer(text, parse_mode="HTML")

    # Убрали кнопку "Оплатить заказ" и автоматическую проверку — вручную проверяете вы.

    # Admin-only seed command to fill tariffs quickly
    @router.message(F.text == "/seed")
    async def seed_tariffs(msg: types.Message):
        if msg.from_user.id not in admin_ids:
            return await msg.answer("Недостаточно прав.")
        # Combined preset across all supported locations
        preset = [
            ("Россия", "3 Gb RAM / 2 Core CPU / SSD 40 Gb", 533),
            ("Россия", "4 Gb RAM / 3 Core CPU / SSD 40 Gb", 598),
            ("Россия", "4 Gb RAM / 2 Core CPU / SSD 40 Gb", 637),
            ("Россия", "6 Gb RAM / 4 Core CPU / SSD 40 Gb", 650),
            ("Россия", "8 Gb RAM / 4 Core CPU / SSD 70 Gb", 1014),
            ("Россия", "16 Gb RAM / 8 Core CPU / SSD 120 Gb", 2054),
            ("Россия", "24 Gb RAM / 10 Core CPU / SSD 120 Gb", 2405),
            ("Россия", "32 Gb RAM / 10 Core CPU / SSD 250 Gb", 3510),
            ("Россия", "64 Gb RAM / 20 Core CPU / SSD 500 Gb", 6354),
            ("Россия", "128 Gb RAM / 32 Core CPU / SSD 2000 Gb", 10244),
            ("Германия", "4 Gb RAM / 2 Core CPU / SSD 40 Gb", 624),
            ("США", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("США", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("США", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("США", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("США", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("США", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
            ("Сингапур", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("Сингапур", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("Сингапур", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("Сингапур", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("Сингапур", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("Сингапур", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
            ("Финляндия", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("Финляндия", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("Финляндия", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("Финляндия", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("Финляндия", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("Финляндия", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
            # Дополнительные страны с теми же тарифами, что и у Финляндии
            ("Франция", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("Франция", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("Франция", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("Франция", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("Франция", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("Франция", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
            ("Нидерланды", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("Нидерланды", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("Нидерланды", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("Нидерланды", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("Нидерланды", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("Нидерланды", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
            ("Болгария", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("Болгария", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("Болгария", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("Болгария", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("Болгария", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("Болгария", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
            ("Германия", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("Германия", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("Германия", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("Германия", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("Германия", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("Германия", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
            ("Испания", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("Испания", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("Испания", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("Испания", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("Испания", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("Испания", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
        ]
        added = 0
        updated_count = 0
        for loc, specs, price in preset:
            # Try to find existing by location + specs, update price; else insert
            existing = await db.fetchrow(
                "select id, price from tariffs where location=$1 and specs=$2 limit 1",
                loc,
                specs,
            )
            if existing:
                if float(existing["price"]) != float(price):
                    await db.execute(
                        "update tariffs set price=$1 where id=$2",
                        float(price),
                        existing["id"],
                    )
                    updated_count += 1
            else:
                await tariffs.create(loc, specs, float(price))
                added += 1
        await msg.answer(f"Готово. Добавлено: {added}, обновлено цен: {updated_count}")
    
    # Команда для добавления отдельного сервера
    @router.message(F.text.startswith("/add_server"))
    async def add_server(msg: types.Message):
        if msg.from_user.id not in admin_ids:
            return await msg.answer("Недостаточно прав.")
        
        try:
            # Формат: /add_server Россия|4 Gb RAM / 2 Core CPU / SSD 40 Gb|650
            parts = msg.text.replace("/add_server ", "").split("|")
            if len(parts) != 3:
                return await msg.answer(
                    "Неверный формат. Используйте:\n"
                    "/add_server Локация|Характеристики|Цена\n\n"
                    "Пример:\n"
                    "/add_server Россия|4 Gb RAM / 2 Core CPU / SSD 40 Gb|650"
                )
            
            location, specs, price = [p.strip() for p in parts]
            price_float = float(price)
            
            await tariffs.create(location, specs, price_float)
            await msg.answer(f"✅ Сервер добавлен:\n{location} • {specs} • {price} RUB")
            
        except ValueError:
            await msg.answer("Ошибка: цена должна быть числом")
        except Exception as e:
            await msg.answer(f"Ошибка при добавлении: {e}")
    
    # Команда для инициализации новых таблиц
    @router.message(F.text == "/init_db")
    async def init_database(msg: types.Message):
        if msg.from_user.id not in admin_ids:
            return await msg.answer("Недостаточно прав.")
        
        try:
            # Создаем таблицу промокодов
            await db.execute("""
                create table if not exists promocodes (
                    id integer primary key autoincrement,
                    code text unique not null,
                    discount_percent integer not null,
                    min_amount integer default 0,
                    max_uses integer default 0,
                    used_count integer default 0,
                    is_active integer default 1,
                    created_at timestamp default current_timestamp
                )
            """)
            
            # Создаем таблицу реферальных наград
            await db.execute("""
                create table if not exists referral_rewards (
                    id integer primary key autoincrement,
                    referrer_id integer,
                    referred_user_id integer,
                    order_id integer,
                    reward_amount integer not null,
                    created_at timestamp default current_timestamp,
                    foreign key (referrer_id) references users(id),
                    foreign key (referred_user_id) references users(id),
                    foreign key (order_id) references orders(id)
                )
            """)
            
            # Создаем таблицу настроек
            await db.execute("""
                create table if not exists settings (
                    key text primary key,
                    value text not null,
                    updated_at timestamp default current_timestamp
                )
            """)
            
            # Проверяем и добавляем поля в таблицу users
            try:
                await db.execute("alter table users add column referrer_id integer")
            except:
                pass  # Поле уже существует
            
            try:
                await db.execute("alter table users add column bonus_balance integer default 0")
            except:
                pass  # Поле уже существует
            
            # Проверяем и добавляем поля в таблицу orders
            try:
                await db.execute("alter table orders add column promo_code text")
            except:
                pass  # Поле уже существует
            
            try:
                await db.execute("alter table orders add column discount_amount integer default 0")
            except:
                pass  # Поле уже существует
            
            try:
                await db.execute("alter table orders add column final_price integer")
            except:
                pass  # Поле уже существует
            
            # Устанавливаем значение по умолчанию для реферальной награды
            try:
                await db.execute("insert into settings (key, value) values (?, ?)", ("referral_reward", "100"))
            except:
                pass  # Уже существует
            
            # Создаем таблицу активных промокодов пользователей
            await db.execute("""
                create table if not exists user_active_promocodes (
                    id integer primary key autoincrement,
                    user_id integer references users(id) on delete cascade,
                    promo_code text not null,
                    discount_percent integer not null,
                    min_amount integer default 0,
                    created_at timestamp default current_timestamp
                )
            """)
            
            await msg.answer(
                "✅ <b>База данных инициализирована!</b>\n\n"
                "📊 <b>Созданы таблицы:</b>\n"
                "• promocodes - для промокодов\n"
                "• referral_rewards - для реферальных наград\n"
                "• settings - для настроек\n"
                "• user_active_promocodes - для активных промокодов пользователей\n\n"
                "🔧 <b>Добавлены поля:</b>\n"
                "• referrer_id - ID реферера\n"
                "• bonus_balance - баланс бонусов\n"
                "• promo_code - использованный промокод\n"
                "• discount_amount - сумма скидки\n"
                "• final_price - итоговая цена\n\n"
                "💡 <b>Теперь можно использовать:</b>\n"
                "• /add_promo - создание промокодов\n"
                "• /set_ref_reward - настройка реферальных наград\n"
                "• /ref_stats - статистика рефералов",
                parse_mode="HTML"
            )
            
        except Exception as e:
            await msg.answer(f"❌ Ошибка при инициализации: {str(e)}")
    
    # Админские команды для промокодов
    @router.message(F.text.startswith("/add_promo"))
    async def add_promocode(msg: types.Message):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Недостаточно прав.")
        
        parts = msg.text.split()
        if len(parts) < 5:
            return await msg.answer(
                "Использование: /add_promo <код> <скидка_%> <мин_сумма> <макс_использований>\n"
                "Пример: /add_promo WELCOME 10 1000 100"
            )
        
        try:
            code = parts[1].upper()
            discount = int(parts[2])
            min_amount = int(parts[3])
            max_uses = int(parts[4])
            
            # Проверяем, не существует ли уже такой промокод
            existing = await db.fetchrow("select 1 from promocodes where code=?", code)
            if existing:
                return await msg.answer(f"❌ Промокод {code} уже существует!")
            
            # Создаем промокод
            await db.execute(
                "insert into promocodes (code, discount_percent, min_amount, max_uses, is_active) values (?, ?, ?, ?, 1)",
                code, discount, min_amount, max_uses
            )
            
            await msg.answer(
                f"✅ <b>Промокод создан!</b>\n\n"
                f"🎁 <b>Код:</b> <code>{code}</code>\n"
                f"💰 <b>Скидка:</b> {discount}%\n"
                f"📊 <b>Мин. сумма:</b> {min_amount} RUB\n"
                f"🎯 <b>Макс. использований:</b> {max_uses}",
                parse_mode="HTML"
            )
            
        except ValueError:
            await msg.answer("❌ Ошибка: все числовые значения должны быть целыми числами")
    
    @router.message(F.text.startswith("/del_promo"))
    async def delete_promocode(msg: types.Message):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Недостаточно прав.")
        
        parts = msg.text.split()
        if len(parts) < 2:
            return await msg.answer("Использование: /del_promo <код>")
        
        code = parts[1].upper()
        
        # Удаляем промокод
        result = await db.execute("delete from promocodes where code=?", code)
        
        if result:
            await msg.answer(f"✅ Промокод {code} удален!")
        else:
            await msg.answer(f"❌ Промокод {code} не найден!")
    
    @router.message(F.text.startswith("/list_promos"))
    async def list_promocodes(msg: types.Message):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Недостаточно прав.")
        
        promos = await db.fetch("select * from promocodes order by created_at desc")
        
        if not promos:
            await msg.answer("📝 Промокодов нет.")
            return
        
        text = "📝 <b>Список промокодов:</b>\n\n"
        for promo in promos:
            status = "✅ Активен" if promo['is_active'] else "❌ Неактивен"
            remaining = "∞" if promo['max_uses'] == 0 else promo['max_uses'] - promo['used_count']
            text += (
                f"🎁 <b>{promo['code']}</b> - {status}\n"
                f"💰 Скидка: {promo['discount_percent']}%\n"
                f"📊 Мин. сумма: {promo['min_amount']} RUB\n"
                f"🎯 Использований: {promo['used_count']}/{promo['max_uses']} (осталось: {remaining})\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )
        
        await msg.answer(text, parse_mode="HTML")
    
    # Админские команды для реферальной системы
    @router.message(F.text.startswith("/set_ref_reward"))
    async def set_referral_reward(msg: types.Message):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Недостаточно прав.")
        
        parts = msg.text.split()
        if len(parts) < 2:
            return await msg.answer("Использование: /set_ref_reward <сумма_в_RUB>")
        
        try:
            reward = int(parts[1])
            
            # Обновляем настройку реферальной награды
            await db.execute("update settings set value=? where key=?", str(reward), "referral_reward")
            
            await msg.answer(f"✅ Реферальная награда установлена: {reward} RUB")
            
        except ValueError:
            await msg.answer("❌ Ошибка: сумма должна быть целым числом")
    
    @router.message(F.text.startswith("/ref_stats"))
    async def referral_stats(msg: types.Message):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Недостаточно прав.")
        
        # Общая статистика рефералов
        total_users = await db.fetchrow("select count(*) as c from users")
        users_with_refs = await db.fetchrow("select count(*) as c from users where referrer_id is not null")
        total_rewards = await db.fetchrow("select sum(reward_amount) as total from referral_rewards")
        
        text = (
            "👥 <b>Статистика реферальной системы</b> 👥\n\n"
            f"👤 <b>Всего пользователей:</b> {total_users['c']}\n"
            f"🔗 <b>Приглашено по рефералам:</b> {users_with_refs['c']}\n"
            f"💰 <b>Выплачено наград:</b> {total_rewards['total'] or 0} RUB\n\n"
        )
        
        # Топ рефереров
        top_refs = await db.fetch(
            "select u.username, u.telegram_id, count(r.id) as ref_count, sum(r.reward_amount) as total_reward "
            "from users u left join users r on u.id=r.referrer_id "
            "where u.id in (select distinct referrer_id from users where referrer_id is not null) "
            "group by u.id, u.username, u.telegram_id "
            "order by ref_count desc limit 5"
        )
        
        if top_refs:
            text += "🏆 <b>Топ рефереров:</b>\n"
            for i, ref in enumerate(top_refs, 1):
                username = f"@{ref['username']}" if ref['username'] else f"ID: {ref['telegram_id']}"
                text += f"{i}. {username} - {ref['ref_count']} рефералов, {ref['total_reward'] or 0} RUB\n"
        
        await msg.answer(text, parse_mode="HTML")

    @router.message(F.text.startswith("/seed_usa"))
    async def seed_usa(msg: types.Message):
        if msg.from_user.id not in admin_ids:
            return await msg.answer("Недостаточно прав.")
        existing_usa = await db.fetchrow("select 1 from tariffs where lower(location) in ('сша','usa') limit 1")
        if existing_usa:
            return await msg.answer("Тарифы США уже добавлены.")
        usa_preset = [
            ("США", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("США", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("США", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("США", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("США", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("США", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
        ]
        cnt = 0
        for loc, specs, price in usa_preset:
            await tariffs.create(loc, specs, float(price))
            cnt += 1
        await msg.answer(f"Готово. Добавлено США тарифов: {cnt}")

    @router.message(F.text.startswith("/seed_sg"))
    async def seed_singapore(msg: types.Message):
        if msg.from_user.id not in admin_ids:
            return await msg.answer("Недостаточно прав.")
        exists = await db.fetchrow("select 1 from tariffs where lower(location) like '%сингап%' or lower(location) like '%singap%' limit 1")
        if exists:
            return await msg.answer("Тарифы Сингапура уже добавлены.")
        sg_preset = [
            ("Сингапур", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("Сингапур", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("Сингапур", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("Сингапур", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("Сингапур", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("Сингапур", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
        ]
        cnt = 0
        for loc, specs, price in sg_preset:
            await tariffs.create(loc, specs, float(price))
            cnt += 1
        await msg.answer(f"Готово. Добавлено тарифов Сингапура: {cnt}")

    @router.message(F.text.startswith("/seed_fin"))
    async def seed_finland(msg: types.Message):
        if msg.from_user.id not in admin_ids:
            return await msg.answer("Недостаточно прав.")
        exists = await db.fetchrow("select 1 from tariffs where lower(location) like '%финл%' or lower(location) like '%finland%' limit 1")
        if exists:
            return await msg.answer("Тарифы Финляндии уже добавлены.")
        fin_preset = [
            ("Финляндия", "1vCPU / 768 MB RAM / SSD 5 Gb", 259),
            ("Финляндия", "1vCPU / 1024 MB RAM / SSD 10 Gb", 429),
            ("Финляндия", "2vCPU / 2048 MB RAM / SSD 20 Gb", 759),
            ("Финляндия", "4vCPU / 3072 MB RAM / SSD 50 Gb", 1259),
            ("Финляндия", "6vCPU / 6144 MB RAM / SSD 100 Gb", 1759),
            ("Финляндия", "8vCPU / 8192 MB RAM / SSD 200 Gb", 2399),
        ]
        cnt = 0
        for loc, specs, price in fin_preset:
            await tariffs.create(loc, specs, float(price))
            cnt += 1
        await msg.answer(f"Готово. Добавлено тарифов Финляндии: {cnt}")

    @router.message(F.text.startswith("/check"))
    async def check_invoice(msg: types.Message):
        parts = msg.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            return await msg.answer("Использование: /check <invoice_id>")
        invoice_id = int(parts[1])
        if not cryptobot:
            return await msg.answer("Проверка недоступна: CRYPTOBOT_TOKEN не задан.")
        inv = await cryptobot.get_invoice(invoice_id)
        if not inv:
            return await msg.answer("Счет не найден.")
        if inv.get("status") == "paid":
            order = await orders.by_invoice_id(invoice_id)
            if order and order.get("status") != "paid":
                await orders.set_status(order["id"], "paid")
            await msg.answer("✅ Оплата подтверждена. Ждите выдачи от администратора.")
            for admin_id in admin_ids:
                try:
                    await msg.bot.send_message(admin_id, f"✅ Оплачен счет {invoice_id}")
                except Exception:
                    pass
        else:
            await msg.answer(f"Статус счета: {inv.get('status')}")

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
        await msg.answer("\n".join(
            f"#{r['id']} • {r['location']} • {r['specs']} • {apply_markup(float(r['price']))} RUB" for r in rows
        ))

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

    @router.message(F.text.startswith("/set_paid"))
    async def set_paid(msg: types.Message):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Недостаточно прав.")
        parts = msg.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            return await msg.answer("Укажите номер заказа: /set_paid <id>")
        order_id = int(parts[1])
        updated = await orders.set_status(order_id, "paid")
        if not updated:
            return await msg.answer("Заказ не найден.")
        await msg.answer(f"Статус заказа #{order_id} обновлен на \"paid\".")

    # Admin panel
    @router.message(F.text.startswith("/admin"))
    async def admin_panel(msg: types.Message):
        if not is_admin(msg.from_user.id):
            return await msg.answer("Недостаточно прав.")
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Оплаченные", callback_data="admin:paid")
        kb.button(text="📋 Все заказы", callback_data="admin:all")
        kb.button(text="📊 Статистика", callback_data="admin:stats")
        kb.adjust(2)
        await msg.answer(
            "⚙️ <b>Админ-панель</b> ⚙️\n\n"
            "🔧 <i>Управление заказами и статистикой</i>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )

    @router.callback_query(F.data == "admin:paid")
    async def admin_paid(cb: types.CallbackQuery):
        if not is_admin(cb.from_user.id):
            return await cb.answer("Нет прав")
        rows = await db.fetch(
            "select o.id, t.location, t.specs, t.price from orders o left join tariffs t on t.id=o.tariff_id where o.status='paid' order by o.id desc limit 20"
        )
        if not rows:
            return await cb.message.edit_text("Оплаченных заказов нет.")
        kb = InlineKeyboardBuilder()
        for r in rows:
            kb.button(text=f"Выдать #{r['id']}", callback_data=f"setdel:{r['id']}")
        kb.adjust(2)
        await cb.message.edit_text(
            "\n".join(
                f"#{r['id']} • {r['location']} • {r['specs']} • {apply_markup(float(r['price']))} RUB" for r in rows
            ),
            reply_markup=kb.as_markup(),
        )

    @router.callback_query(F.data == "admin:all")
    async def admin_all(cb: types.CallbackQuery):
        if not is_admin(cb.from_user.id):
            return await cb.answer("Нет прав")
        rows = await db.fetch(
            "select o.id, o.status, t.location, t.specs, t.price from orders o left join tariffs t on t.id=o.tariff_id order by o.id desc limit 30"
        )
        if not rows:
            return await cb.message.edit_text("Заказов нет.")
        kb = InlineKeyboardBuilder()
        for r in rows:
            if r["status"] == "created":
                kb.button(text=f"Оплачен #{r['id']}", callback_data=f"setpaid:{r['id']}")
            if r["status"] == "paid":
                kb.button(text=f"Выдать #{r['id']}", callback_data=f"setdel:{r['id']}")
        kb.adjust(2)
        await cb.message.edit_text(
            "\n".join(
                f"#{r['id']} • {r['status']} • {r['location']} • {r['specs']} • {apply_markup(float(r['price']))} RUB" for r in rows
            ),
            reply_markup=kb.as_markup(),
        )

    @router.callback_query(F.data == "admin:stats")
    async def admin_stats(cb: types.CallbackQuery):
        if not is_admin(cb.from_user.id):
            return await cb.answer("Нет прав")
        total = await db.fetchrow("select count(*) as c from orders")
        paid = await db.fetchrow("select count(*) as c from orders where status='paid'")
        delivered = await db.fetchrow("select count(*) as c from orders where status='delivered'")
        users_count = await db.fetchrow("select count(*) as c from users")
        rows_am = await db.fetch(
            "select t.price from orders o left join tariffs t on t.id=o.tariff_id where o.status in ('paid','delivered')"
        )
        revenue_sum = sum(apply_markup(float(r['price'])) for r in rows_am) if rows_am else 0
        text = (
            f"📊 <b>Статистика магазина</b> 📊\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 <b>Всего заказов:</b> <code>{total['c']}</code>\n"
            f"✅ <b>Оплачено:</b> <code>{paid['c']}</code>\n"
            f"🎉 <b>Выдано:</b> <code>{delivered['c']}</code>\n"
            f"👥 <b>Пользователей:</b> <code>{users_count['c']}</code>\n"
            f"💰 <b>Выручка (RUB):</b> <code>{revenue_sum:,}</code>"
        )
        await cb.message.edit_text(text, parse_mode="HTML")

    @router.callback_query(F.data.startswith("setdel:"))
    async def admin_set_delivered_btn(cb: types.CallbackQuery):
        if not is_admin(cb.from_user.id):
            return await cb.answer("Нет прав")
        order_id = int(cb.data.split(":",1)[1])
        updated = await orders.set_status(order_id, "delivered")
        if updated:
            await cb.answer("Выдано")
            await cb.message.edit_text(cb.message.text + f"\n\n✅ Заказ #{order_id} выдан.")
            if updated.get("telegram_id"):
                try:
                    await cb.bot.send_message(int(updated["telegram_id"]), f"Ваш заказ №{order_id}: статус <b>Выдан</b>.", parse_mode="HTML")
                except Exception:
                    pass
        else:
            await cb.answer("Не найдено")

    @router.callback_query(F.data.startswith("setpaid:"))
    async def admin_set_paid_btn(cb: types.CallbackQuery):
        if not is_admin(cb.from_user.id):
            return await cb.answer("Нет прав")
        order_id = int(cb.data.split(":",1)[1])
        updated = await orders.set_status(order_id, "paid")
        if updated:
            await cb.answer("Оплачен")
            await cb.message.edit_text(cb.message.text + f"\n\n✅ Заказ #{order_id} отмечен как оплачен.")
            if updated.get("telegram_id"):
                try:
                    text = (
                        f"<b>Ваш заказ №{order_id}</b>\n"
                        f"Статус: <b>Оплачен</b>\n"
                        f"{updated['location']} • {updated['specs']} • {apply_markup(float(updated['price']))} RUB"
                    )
                    await cb.bot.send_message(int(updated["telegram_id"]), text, parse_mode="HTML")
                except Exception:
                    pass
        else:
            await cb.answer("Не найдено")

    # Callbacks for log channel
    @router.callback_query(F.data.startswith("logpaid:"))
    async def mark_paid(cb: types.CallbackQuery):
        if not is_admin(cb.from_user.id):
            return await cb.answer("Нет прав")
        order_id = int(cb.data.split(":", 1)[1])
        updated = await orders.set_status(order_id, "paid")
        if updated:
            await cb.message.edit_text(cb.message.text + "\n\n✅ Отмечено: оплачен.")
            
            # Проверяем реферальную систему
            try:
                # Получаем информацию о пользователе и заказе
                order_info = await db.fetchrow(
                    "select o.user_id, o.final_price, u.referrer_id, u.telegram_id from orders o "
                    "left join users u on o.user_id=u.id where o.id=?", order_id
                )
                
                if order_info and order_info['referrer_id']:
                    # Получаем настройку реферальной награды
                    ref_reward_setting = await db.fetchrow("select value from settings where key=?", "referral_reward")
                    ref_reward_amount = int(ref_reward_setting['value']) if ref_reward_setting else 100  # По умолчанию 100 RUB
                    
                    # Начисляем бонус рефереру
                    await db.execute(
                        "insert into referral_rewards (referrer_id, referred_user_id, order_id, reward_amount) values (?, ?, ?, ?)",
                        order_info['referrer_id'], order_info['user_id'], order_id, ref_reward_amount
                    )
                    
                    # Увеличиваем баланс бонусов реферера
                    await db.execute(
                        "update users set bonus_balance=bonus_balance+? where id=?",
                        ref_reward_amount, order_info['referrer_id']
                    )
                    
                    # Уведомляем реферера о начислении бонуса
                    ref_user = await db.fetchrow("select telegram_id, username from users where id=?", order_info['referrer_id'])
                    if ref_user:
                        try:
                            await cb.bot.send_message(
                                ref_user['telegram_id'],
                                f"🎉 <b>Реферальный бонус!</b>\n\n"
                                f"👤 Ваш реферал @{order_info.get('username', 'пользователь')} "
                                f"оплатил заказ #{order_id}\n"
                                f"💰 Начислено бонусов: <code>{ref_reward_amount} RUB</code>\n\n"
                                f"💡 Бонусы можно использовать для оплаты заказов!",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
            except Exception as e:
                # Логируем ошибку, но не прерываем основной процесс
                print(f"Ошибка при начислении реферального бонуса: {e}")
            
            # уведомим пользователя
            full = updated
            if full and full.get("telegram_id"):
                try:
                    text = (
                        f"<b>Ваш заказ №{order_id}</b>\n"
                        f"Статус: <b>Оплачен</b>\n"
                        f"{full['location']} • {full['specs']} • {apply_markup(float(full['price']))} RUB\n\n"
                        f"Пожалуйста, перешлите сообщение от CryptoBot с подтверждением оплаты в {support_contact} для выдачи заказа."
                    )
                    await cb.bot.send_message(int(full["telegram_id"]), text, parse_mode="HTML")
                except Exception:
                    pass
            await cb.answer("Отмечено как оплачен")
        else:
            await cb.answer("Не найдено")

    @router.callback_query(F.data.startswith("logunpaid:"))
    async def mark_unpaid(cb: types.CallbackQuery):
        if not is_admin(cb.from_user.id):
            return await cb.answer("Нет прав")
        order_id = int(cb.data.split(":", 1)[1])
        updated = await orders.set_status(order_id, "created")
        if updated:
            await cb.message.edit_text(cb.message.text + "\n\n❌ Отмечено: не оплачен.")
            full = updated
            if full and full.get("telegram_id"):
                try:
                    text = (
                        f"<b>Ваш заказ №{order_id}</b>\n"
                        f"Статус: <b>Не оплачен</b>\n"
                        f"{full['location']} • {full['specs']} • {apply_markup(float(full['price']))} RUB\n\n"
                        f"Если оплачивали, перешлите подтверждение в {support_contact}."
                    )
                    await cb.bot.send_message(int(full["telegram_id"]), text, parse_mode="HTML")
                except Exception:
                    pass
            await cb.answer("Отмечено как не оплачен")
        else:
            await cb.answer("Не найдено")


