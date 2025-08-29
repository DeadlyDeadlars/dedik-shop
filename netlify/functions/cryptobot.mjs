import { request } from 'undici';

const CRYPTOBOT_TOKEN = process.env.CRYPTOBOT_TOKEN || '';
const CRYPTOBOT_API = 'https://pay.crypt.bot/api';

export async function createCryptoInvoice({ amount, description, payload }) {
  if (!CRYPTOBOT_TOKEN) throw new Error('CRYPTOBOT_TOKEN missing');
  const body = {
    asset: 'USDT',
    amount, // USDT amount
    description,
    payload: JSON.stringify(payload || {}),
  };
  const { body: resBody } = await request(`${CRYPTOBOT_API}/createInvoice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Crypto-Pay-API-Token': CRYPTOBOT_TOKEN },
    body: JSON.stringify(body),
  });
  const json = await resBody.json();
  if (!json.ok) throw new Error('CryptoBot API error');
  return json.result;
}


