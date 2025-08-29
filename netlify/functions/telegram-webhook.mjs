import { Telegraf, Markup } from 'telegraf';
import { ensureSchema } from './db.mjs';
import { Tariffs, Users, Orders } from './models.mjs';
import { createCryptoInvoice } from './cryptobot.mjs';

const botToken = process.env.TELEGRAM_BOT_TOKEN;
if (!botToken) {
  console.warn('TELEGRAM_BOT_TOKEN is not set');
}

// Singleton Telegraf instance across invocations
let telegrafInstance;
function getBot() {
  if (!telegrafInstance) {
    telegrafInstance = new Telegraf(botToken || '');

    // Basic menu handlers (placeholder)
    telegrafInstance.start(async (ctx) => {
      await ensureSchema();
      await ctx.reply(
        'Главное меню',
        {
          reply_markup: {
            keyboard: [[{ text: '🛒 Каталог' }, { text: '📦 Мои заказы' }], [{ text: '💳 Оплатить заказ' }, { text: '🆘 Поддержка' }]],
            resize_keyboard: true,
          },
        }
      );
    });

    telegrafInstance.hears('🛒 Каталог', async (ctx) => {
      await ensureSchema();
      const locations = await Tariffs.listLocations();
      const buttons = locations.map((loc) => [Markup.button.callback(loc, `loc:${loc}`)]);
      await ctx.reply('Выберите страну:', Markup.inlineKeyboard(buttons));
    });

    telegrafInstance.action(/loc:(.+)/, async (ctx) => {
      const location = ctx.match[1];
      const tariffs = await Tariffs.listByLocation(location);
      if (tariffs.length === 0) {
        return ctx.editMessageText(`Тарифы для ${location} не найдены.`);
      }
      const items = tariffs.map(t => `${t.specs}\nЦена: ${t.price} RUB`);
      await ctx.editMessageText(`Тарифы — ${location}:\n\n${items.map((s,i)=>`${i+1}. ${s}`).join('\n\n')}`, Markup.inlineKeyboard(
        tariffs.map(t => [Markup.button.callback(`Купить за ${t.price}`, `buy:${t.id}`)]).concat([[Markup.button.callback('↩️ Назад', 'back:catalog')]])
      ));
    });

    telegrafInstance.action('back:catalog', async (ctx) => {
      const locations = await Tariffs.listLocations();
      const buttons = locations.map((loc) => [Markup.button.callback(loc, `loc:${loc}`)]);
      await ctx.editMessageText('Выберите страну:', Markup.inlineKeyboard(buttons));
    });

    telegrafInstance.action(/buy:(\d+)/, async (ctx) => {
      const tariffId = Number(ctx.match[1]);
      const username = ctx.from?.username || `id_${ctx.from.id}`;
      const user = await Users.upsertByTelegram({ username, telegramId: ctx.from.id });
      // Placeholder: create invoice via CryptoBot
      const invoice = await createCryptoInvoice({
        amount: 1, // will be replaced with RUB to crypto conversion externally
        description: `Order for tariff #${tariffId}`,
        payload: { tariffId, userId: user.id }
      });
      await Orders.create({ userId: user.id, tariffId, invoiceId: invoice.invoice_id, status: 'created' });
      await ctx.reply(`Счет создан. Оплатите по ссылке:\n${invoice.pay_url}`);
    });

    telegrafInstance.hears('📦 Мои заказы', async (ctx) => {
      const username = ctx.from?.username || `id_${ctx.from.id}`;
      const user = await Users.upsertByTelegram({ username, telegramId: ctx.from.id });
      const orders = await Orders.byUser(user.id);
      if (orders.length === 0) return ctx.reply('У вас пока нет заказов.');
      const lines = orders.map(o => `#${o.id} • ${o.location} • ${o.specs} • ${o.price} RUB • статус: ${o.status}`);
      return ctx.reply(lines.join('\n'));
    });
    
    // Minimal admin command: /orders_paid and /set_delivered <orderId>
    const adminIds = (process.env.ADMIN_IDS || '').split(',').filter(Boolean).map(s => Number(s.trim()));
    function isAdmin(id) { return adminIds.includes(Number(id)); }

    telegrafInstance.command('orders_paid', async (ctx) => {
      if (!isAdmin(ctx.from.id)) return ctx.reply('Недостаточно прав.');
      const res = await (await import('./models.mjs')).Orders;
      const { rows } = await (await import('./db.mjs')).query("select o.id, t.location, t.specs, t.price from orders o left join tariffs t on t.id=o.tariff_id where o.status='paid' order by o.id desc limit 20");
      if (rows.length === 0) return ctx.reply('Оплаченных заказов нет.');
      await ctx.reply(rows.map(r => `#${r.id} • ${r.location} • ${r.specs} • ${r.price} RUB`).join('\n'));
    });

    telegrafInstance.command('set_delivered', async (ctx) => {
      if (!isAdmin(ctx.from.id)) return ctx.reply('Недостаточно прав.');
      const [, idStr] = ctx.message.text.split(' ');
      const orderId = Number(idStr);
      if (!orderId) return ctx.reply('Укажите номер заказа: /set_delivered <id>');
      const updated = await Orders.setStatus(orderId, 'delivered');
      if (!updated) return ctx.reply('Заказ не найден.');
      await ctx.reply(`Статус заказа #${orderId} обновлен на "delivered".`);
    });
    telegrafInstance.hears('💳 Оплатить заказ', (ctx) => ctx.reply('Выберите заказ для оплаты.'));
    telegrafInstance.hears('🆘 Поддержка', (ctx) => ctx.reply('Связь с админом: @your_admin'));
  }
  return telegrafInstance;
}

export async function handler(event) {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ ok: false, error: 'Method Not Allowed' }) };
  }
  if (!botToken) {
    return { statusCode: 500, body: JSON.stringify({ ok: false, error: 'Bot token missing' }) };
  }

  const bot = getBot();
  try {
    const update = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
    await bot.handleUpdate(update);
    return { statusCode: 200, body: JSON.stringify({ ok: true }) };
  } catch (err) {
    console.error('Telegram webhook error', err);
    return { statusCode: 500, body: JSON.stringify({ ok: false }) };
  }
}


