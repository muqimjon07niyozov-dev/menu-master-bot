# === ЗАПУСК (WEBHOOK) ===
import os
from flask import Flask, request
import asyncio

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
async def webhook():
    update = request.get_json()
    await dp.feed_webhook_update(bot, update)
    return 'ok'

async def set_webhook():
    webhook_url = "https://menu-master-bot.onrender.com/webhook"
    await bot.set_webhook(webhook_url)

if __name__ == "__main__":
    asyncio.run(set_webhook())
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
