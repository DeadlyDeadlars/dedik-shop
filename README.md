# Telegram Dedik Shop Bot (Netlify + Webhooks)

Serverless scaffold: Telegraf bot on Netlify Functions with Telegram and CryptoBot webhooks.

## Setup

1) Install
```bash
npm i
```

2) Env vars (Netlify → Site settings → Environment variables)
- TELEGRAM_BOT_TOKEN
- CRYPTOBOT_WEBHOOK_SECRET
- optional: TELEGRAM_ADMIN_IDS, APP_BASE_URL, DATABASE_URL

3) Local run
```bash
npx netlify dev
```

## Endpoints
- POST /api/telegram-webhook — Telegram updates
- POST /api/cryptobot-webhook — CryptoBot payment events

## Webhook registration
- Telegram:
```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<site>.netlify.app/api/telegram-webhook"
```
- CryptoBot: set webhook URL to `https://<site>.netlify.app/api/cryptobot-webhook` and pass header secret that equals `CRYPTOBOT_WEBHOOK_SECRET` (adjust per CryptoBot docs).

## Notes
- CryptoBot signature check is a placeholder; implement HMAC per official docs.
- Add DB + idempotency for production.
