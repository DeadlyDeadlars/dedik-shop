import { query } from './db.mjs';

export const Tariffs = {
  async listByLocation(location) {
    const res = await query('select * from tariffs where location = $1 order by price asc', [location]);
    return res.rows;
  },
  async listLocations() {
    const res = await query('select distinct location from tariffs order by location');
    return res.rows.map(r => r.location);
  },
  async create({ location, specs, price }) {
    const res = await query('insert into tariffs(location,specs,price) values($1,$2,$3) returning *', [location, specs, price]);
    return res.rows[0];
  },
  async all() {
    const res = await query('select * from tariffs order by location, price');
    return res.rows;
  }
};

export const Users = {
  async upsertByTelegram({ username, telegramId }) {
    const existing = telegramId
      ? await query('select * from users where telegram_id=$1', [telegramId])
      : await query('select * from users where username=$1', [username]);
    if (existing.rowCount > 0) return existing.rows[0];
    const res = await query('insert into users(username, telegram_id) values($1,$2) returning *', [username, telegramId || null]);
    return res.rows[0];
  },
};

export const Orders = {
  async create({ userId, tariffId, invoiceId, status = 'created' }) {
    const res = await query('insert into orders(user_id, tariff_id, status, invoice_id) values($1,$2,$3,$4) returning *', [userId, tariffId, status, invoiceId || null]);
    return res.rows[0];
  },
  async byUser(userId) {
    const res = await query('select o.*, t.location, t.specs, t.price from orders o left join tariffs t on t.id=o.tariff_id where user_id=$1 order by o.id desc', [userId]);
    return res.rows;
  },
  async byInvoiceId(invoiceId) {
    const res = await query('select * from orders where invoice_id=$1', [invoiceId]);
    return res.rows[0] || null;
  },
  async byId(orderId) {
    const res = await query('select * from orders where id=$1', [orderId]);
    return res.rows[0] || null;
  },
  async setStatus(orderId, status) {
    const res = await query('update orders set status=$2 where id=$1 returning *', [orderId, status]);
    return res.rows[0];
  }
};


