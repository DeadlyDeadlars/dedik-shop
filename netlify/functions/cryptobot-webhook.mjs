import { Orders } from './models.mjs';
import crypto from 'crypto';

const CRYPTOBOT_WEBHOOK_SECRET = process.env.CRYPTOBOT_WEBHOOK_SECRET || '';

function safeJsonParse(body) {
  try {
    return JSON.parse(body);
  } catch {
    return null;
  }
}

function verifySignature(headers, rawBody) {
  // Example HMAC-SHA256 signature verification; adjust to actual CryptoBot docs if needed
  const signatureHeader = headers['x-signature'] || headers['x-cryptobot-signature'];
  if (!CRYPTOBOT_WEBHOOK_SECRET || !signatureHeader) return false;
  const hmac = crypto.createHmac('sha256', CRYPTOBOT_WEBHOOK_SECRET).update(rawBody).digest('hex');
  return signatureHeader === hmac;
}

export async function handler(event) {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ ok: false, error: 'Method Not Allowed' }) };
  }

  const rawBody = typeof event.body === 'string' ? event.body : JSON.stringify(event.body || {});
  if (!verifySignature(event.headers || {}, rawBody)) {
    return { statusCode: 401, body: JSON.stringify({ ok: false, error: 'Unauthorized' }) };
  }

  const payload = typeof event.body === 'string' ? safeJsonParse(event.body) : event.body;
  if (!payload) {
    return { statusCode: 400, body: JSON.stringify({ ok: false, error: 'Invalid JSON' }) };
  }

  const eventType = payload.type || payload.update_type || payload.event || '';
  if (eventType !== 'invoice_paid') {
    return { statusCode: 204, body: '' };
  }

  const invoiceId = payload.invoice_id || payload.payload?.invoice_id || payload.payload?.invoiceId;
  if (invoiceId) {
    const order = await Orders.byInvoiceId(Number(invoiceId));
    if (order) {
      await Orders.setStatus(order.id, 'paid');
      // TODO: notify admin and user via Telegram using bot token if desired
    }
  }

  return { statusCode: 200, body: JSON.stringify({ ok: true }) };
}


