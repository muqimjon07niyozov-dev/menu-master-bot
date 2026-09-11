import asyncio
import logging
import os
import random
import string
from datetime import datetime, timedelta
from io import BytesIO

import psycopg2
import qrcode
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile
)
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

BOT_TOKEN = "8890056509:AAFvSsiaD0pZPHGRAa3iWRwfNdae3II7ttc"
ADMIN_ID = 7758384445
BOT_USERNAME = "Aura_Muqimjon_bot"
WEBHOOK_URL = "https://menu-master-bot.onrender.com/webhook"
PAYMENT_PHONE = "993337070"
PRICE_BASIC = 50
PRICE_DESIGN = 60
SUBSCRIPTION_DAYS = 30

CATEGORIES = {
    "salads": "🥗 Салаты", "soups": "🍲 Супы", "hot": "🍖 Горячее",
    "fastfood": "🍔 Фастфуд", "desserts": "🍰 Десерты", "drinks": "🥤 Напитки",
    "other": "🍽 Другое",
}

DESIGNS = {
    "classic": {"name": "📋 Классик", "desc": "Строгий", "header": "━━━━━━━━━", "item": "▫️", "title": "🍽 Меню", "price": "сомони", "footer": "━━━━━━━━━"},
    "modern": {"name": "⚡ Модерн", "desc": "Современный", "header": "🔥🔥🔥🔥🔥", "item": "⚡", "title": "🍔 МЕНЮ", "price": " TJS", "footer": "🔥🔥🔥🔥🔥"},
    "elegant": {"name": "✨ Элегант", "desc": "Премиум", "header": "✦ ───── ✦", "item": "✨", "title": "👑 Избранное", "price": "сомони", "footer": "✦ ───── ✦"},
    "fun": {"name": "🎉 Весёлый", "desc": "Яркий", "header": "🎉🎊🎈🎊🎉", "item": "🌟", "title": "😋 Что покушаем?", "price": "сом", "footer": "🎈🎊🎉🎊🎈"},
    "night": {"name": "🌙 Ночной", "desc": "Тёмный", "header": "🌙 ─ ─ ─ 🌙", "item": "🍷", "title": "🌙 Ночное", "price": "сомони", "footer": "🌙 ─ ─ ─ 🌙"},
}

STATUSES = {
    "new": "🆕 Новый", "accepted": "✅ Принят", "cooking": "👨‍🍳 Готовится",
    "ready": "🍽 Готов", "delivering": "🚚 В пути", "delivered": "🏁 Доставлен",
    "cancelled": "❌ Отменён",
}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

DATABASE_URL = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS rest (
    id SERIAL PRIMARY KEY, name TEXT NOT NULL, address TEXT, phone TEXT,
    owner_id BIGINT, subscribed INTEGER DEFAULT 0, blocked INTEGER DEFAULT 0,
    subscribe_until TEXT, design TEXT DEFAULT 'none', active_design TEXT DEFAULT 'classic',
    history TEXT, work_hours TEXT, delivery_price REAL DEFAULT 0, min_order REAL DEFAULT 0
)''')

for col, ct in [("design","TEXT DEFAULT 'none'"),("active_design","TEXT DEFAULT 'classic'"),
                ("history","TEXT"),("work_hours","TEXT"),
                ("delivery_price","REAL DEFAULT 0"),("min_order","REAL DEFAULT 0")]:
    try:
        cursor.execute(f"ALTER TABLE rest ADD COLUMN IF NOT EXISTS {col} {ct}")
        conn.commit()
    except: conn.rollback()

cursor.execute('''CREATE TABLE IF NOT EXISTS menu (
    id SERIAL PRIMARY KEY, rest_id INTEGER, name TEXT, description TEXT,
    price REAL, category TEXT DEFAULT 'other', photo_id TEXT,
    stoplist INTEGER DEFAULT 0,
    FOREIGN KEY(rest_id) REFERENCES rest(id))''')
for col, ct in [("category","TEXT DEFAULT 'other'"),("photo_id","TEXT"),("stoplist","INTEGER DEFAULT 0")]:
    try:
        cursor.execute(f"ALTER TABLE menu ADD COLUMN IF NOT EXISTS {col} {ct}")
        conn.commit()
    except: conn.rollback()

cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY, rest_id INTEGER, client_id BIGINT,
    client_name TEXT, client_phone TEXT, client_address TEXT,
    items_text TEXT, total REAL, subtotal REAL, delivery_type TEXT DEFAULT 'delivery',
    promo_code TEXT, discount REAL DEFAULT 0,
    status TEXT DEFAULT 'new', created_at TEXT, updated_at TEXT,
    FOREIGN KEY(rest_id) REFERENCES rest(id))''')
for col, ct in [("subtotal","REAL"),("delivery_type","TEXT DEFAULT 'delivery'"),
                ("promo_code","TEXT"),("discount","REAL DEFAULT 0"),
                ("updated_at","TEXT"),("client_id","BIGINT")]:
    try:
        cursor.execute(f"ALTER TABLE orders ADD COLUMN IF NOT EXISTS {col} {ct}")
        conn.commit()
    except: conn.rollback()

cursor.execute('''CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY, rest_id INTEGER, owner_id BIGINT, amount INTEGER,
    receipt_file_id TEXT, status TEXT DEFAULT 'pending', created_at TEXT,
    FOREIGN KEY(rest_id) REFERENCES rest(id))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS cart (
    id SERIAL PRIMARY KEY, client_id BIGINT, rest_id INTEGER, item_id INTEGER,
    quantity INTEGER DEFAULT 1, created_at TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY, rest_id INTEGER, client_id BIGINT,
    client_name TEXT, rating INTEGER, comment TEXT, created_at TEXT,
    FOREIGN KEY(rest_id) REFERENCES rest(id))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS promocodes (
    id SERIAL PRIMARY KEY, rest_id INTEGER, code TEXT UNIQUE,
    discount_percent INTEGER DEFAULT 10, max_uses INTEGER DEFAULT 100,
    used_count INTEGER DEFAULT 0, active INTEGER DEFAULT 1, created_at TEXT,
    FOREIGN KEY(rest_id) REFERENCES rest(id))''')
conn.commit()

def get_restaurant_by_owner(owner_id):
    cursor.execute("SELECT * FROM rest WHERE owner_id=%s", (owner_id,))
    return cursor.fetchone()

def get_restaurant_by_id(rest_id):
    cursor.execute("SELECT * FROM rest WHERE id=%s", (rest_id,))
    return cursor.fetchone()

def get_active_restaurants():
    cursor.execute("SELECT * FROM rest WHERE blocked=0 AND subscribed=1")
    return cursor.fetchall()

def get_menu_items(rest_id, category=None):
    if category:
        cursor.execute("SELECT * FROM menu WHERE rest_id=%s AND category=%s AND stoplist=0", (rest_id, category))
    else:
        cursor.execute("SELECT * FROM menu WHERE rest_id=%s AND stoplist=0", (rest_id,))
    return cursor.fetchall()

def get_menu_item(item_id):
    cursor.execute("SELECT * FROM menu WHERE id=%s", (item_id,))
    return cursor.fetchone()

def add_menu_item(rest_id, name, description, price, category, photo_id):
    cursor.execute("INSERT INTO menu (rest_id, name, description, price, category, photo_id) VALUES (%s,%s,%s,%s,%s,%s)",
                   (rest_id, name, description, price, category, photo_id))
    conn.commit()

def delete_menu_item(item_id):
    cursor.execute("DELETE FROM menu WHERE id=%s", (item_id,))
    conn.commit()

def toggle_stoplist(item_id):
    cursor.execute("UPDATE menu SET stoplist = 1 - stoplist WHERE id=%s", (item_id,))
    conn.commit()

def add_order(rest_id, client_id, cn, cp, ca, items, total, subtotal, dtype, promo, discount):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""INSERT INTO orders (rest_id,client_id,client_name,client_phone,client_address,items_text,total,subtotal,delivery_type,promo_code,discount,created_at,updated_at) 
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                   (rest_id, client_id, cn, cp, ca, items, total, subtotal, dtype, promo, discount, now, now))
    conn.commit()
    return cursor.lastrowid

def get_orders_by_restaurant(rest_id, status=None):
    if status:
        cursor.execute("SELECT * FROM orders WHERE rest_id=%s AND status=%s ORDER BY id DESC", (rest_id, status))
    else:
        cursor.execute("SELECT * FROM orders WHERE rest_id=%s ORDER BY id DESC LIMIT 30", (rest_id,))
    return cursor.fetchall()

def get_order(order_id):
    cursor.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
    return cursor.fetchone()

def update_order_status(oid, status):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE orders SET status=%s, updated_at=%s WHERE id=%s", (status, now, oid))
    conn.commit()

def update_restaurant_info(rest_id, history, hours, del_price, min_order):
    cursor.execute("UPDATE rest SET history=%s, work_hours=%s, delivery_price=%s, min_order=%s WHERE id=%s",
                   (history, hours, del_price, min_order, rest_id))
    conn.commit()

def is_subscription_active(r):
    if not r: return False
    if r[6] == 1: return False
    if r[5] != 1: return False
    if not r[7]: return False
    try: return datetime.strptime(r[7], "%Y-%m-%d") >= datetime.now()
    except: return False

def activate_subscription(rest_id, days=30):
    until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("UPDATE rest SET subscribed=1, subscribe_until=%s WHERE id=%s", (until, rest_id))
    conn.commit()
    return until

def set_design(rest_id, key):
    cursor.execute("UPDATE rest SET design=%s, active_design=%s WHERE id=%s", (key, key, rest_id))
    conn.commit()

def clear_design(rest_id):
    cursor.execute("UPDATE rest SET design='none' WHERE id=%s", (rest_id,))
    conn.commit()

def get_price(r):
    return PRICE_DESIGN if r and r[8] and r[8] != 'none' else PRICE_BASIC

def add_payment(rest_id, owner_id, amount, fid):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO payments (rest_id,owner_id,amount,receipt_file_id,created_at) VALUES (%s,%s,%s,%s,%s)",
                   (rest_id, owner_id, amount, fid, now))
    conn.commit()
    return cursor.lastrowid

def get_payment(pid):
    cursor.execute("SELECT * FROM payments WHERE id=%s", (pid,))
    return cursor.fetchone()

def update_payment_status(pid, st):
    cursor.execute("UPDATE payments SET status=%s WHERE id=%s", (st, pid))
    conn.commit()

def get_pending_payments():
    cursor.execute("SELECT * FROM payments WHERE status='pending'")
    return cursor.fetchall()

def get_cart(client_id, rest_id):
    cursor.execute("""SELECT c.id,c.item_id,c.quantity,m.name,m.price FROM cart c 
                      JOIN menu m ON c.item_id=m.id WHERE c.client_id=%s AND c.rest_id=%s""",
                   (client_id, rest_id))
    return cursor.fetchall()

def add_to_cart(cid, rid, iid):
    cursor.execute("SELECT id FROM cart WHERE client_id=%s AND item_id=%s", (cid, iid))
    ex = cursor.fetchone()
    if ex:
        cursor.execute("UPDATE cart SET quantity=quantity+1 WHERE id=%s", (ex[0],))
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO cart (client_id,rest_id,item_id,created_at) VALUES (%s,%s,%s,%s)",
                       (cid, rid, iid, now))
    conn.commit()

def clear_cart(cid, rid):
    cursor.execute("DELETE FROM cart WHERE client_id=%s AND rest_id=%s", (cid, rid))
    conn.commit()

def remove_cart(cart_id):
    cursor.execute("DELETE FROM cart WHERE id=%s", (cart_id,))
    conn.commit()

def generate_qr(rest_id):
    url = f"https://t.me/{BOT_USERNAME}?start=rest_{rest_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return buf, url

def add_review(rest_id, cid, name, rating, comment):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO reviews (rest_id,client_id,client_name,rating,comment,created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                   (rest_id, cid, name, rating, comment, now))
    conn.commit()

def get_reviews(rest_id, limit=10):
    cursor.execute("SELECT client_name,rating,comment,created_at FROM reviews WHERE rest_id=%s ORDER BY id DESC LIMIT %s", (rest_id, limit))
    return cursor.fetchall()

def get_avg_rating(rest_id):
    cursor.execute("SELECT AVG(rating), COUNT(*) FROM reviews WHERE rest_id=%s", (rest_id,))
    row = cursor.fetchone()
    if row and row[0]:
        return round(float(row[0]), 1), row[1]
    return 0, 0

def create_promo(rest_id, code, discount, max_uses):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("INSERT INTO promocodes (rest_id,code,discount_percent,max_uses,created_at) VALUES (%s,%s,%s,%s,%s)",
                       (rest_id, code.upper(), discount, max_uses, now))
        conn.commit()
        return True
    except: 
        conn.rollback()
        return False

def get_promo(code):
    cursor.execute("SELECT * FROM promocodes WHERE code=%s AND active=1", (code.upper(),))
    return cursor.fetchone()

def use_promo(promo_id):
    cursor.execute("UPDATE promocodes SET used_count=used_count+1 WHERE id=%s", (promo_id,))
    conn.commit()

def get_promos(rest_id):
    cursor.execute("SELECT * FROM promocodes WHERE rest_id=%s ORDER BY id DESC", (rest_id,))
    return cursor.fetchall()

def delete_promo(promo_id):
    cursor.execute("DELETE FROM promocodes WHERE id=%s", (promo_id,))
    conn.commit()

def get_analytics(rest_id, days=30):
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("""SELECT COUNT(*), COALESCE(SUM(total),0) FROM orders 
                      WHERE rest_id=%s AND status IN ('accepted','cooking','ready','delivering','delivered') 
                      AND created_at >= %s""", (rest_id, from_date))
    row = cursor.fetchone()
    total_orders = row[0] if row else 0
    total_revenue = row[1] if row else 0
    cursor.execute("""SELECT COUNT(*), COALESCE(SUM(total),0) FROM orders 
                      WHERE rest_id=%s AND status='delivered' AND created_at >= %s""", (rest_id, from_date))
    row = cursor.fetchone()
    delivered = row[0] if row else 0
    delivered_rev = row[1] if row else 0
    cursor.execute("""SELECT status, COUNT(*) FROM orders WHERE rest_id=%s AND created_at >= %s GROUP BY status""",
                   (rest_id, from_date))
    statuses = cursor.fetchall()
    return {"total_orders": total_orders, "revenue": total_revenue,
            "delivered": delivered, "delivered_revenue": delivered_rev,
            "statuses": dict(statuses)}

def cabinet_keyboard(has_design):
    kb = [
        [InlineKeyboardButton(text="📝 Добавить блюдо", callback_data="add_item")],
        [InlineKeyboardButton(text="🍽 Мои блюда", callback_data="my_items")],
        [InlineKeyboardButton(text="🛒 Заказы", callback_data="my_orders")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="analytics")],
        [InlineKeyboardButton(text="🎁 Промокоды", callback_data="my_promos")],
        [InlineKeyboardButton(text="📱 QR-код", callback_data="my_qr")],
        [InlineKeyboardButton(text="ℹ️ О ресторане", callback_data="edit_info")],
    ]
    if has_design:
        kb.append([InlineKeyboardButton(text="🎨 Сменить дизайн", callback_data="choose_design")])
        kb.append([InlineKeyboardButton(text="🚫 Убрать дизайн", callback_data="remove_design")])
    else:
        kb.append([InlineKeyboardButton(text="🎨 Выбрать дизайн (+10с)", callback_data="choose_design")])
    kb.append([InlineKeyboardButton(text="💳 Оплатить подписку", callback_data="pay_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def design_choice_keyboard():
    kb = [[InlineKeyboardButton(text=f"{d['name']} — {d['desc']}", callback_data=f"set_design_{k}")] for k, d in DESIGNS.items()]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def category_choice_keyboard(prefix="newcat"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=n, callback_data=f"{prefix}_{k}")] for k, n in CATEGORIES.items()])

def payment_confirm_keyboard(pid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_pay_{pid}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_pay_{pid}")],
    ])

def client_categories_keyboard(rest_id, cats_list, has_cart=False):
    kb = [[InlineKeyboardButton(text=n, callback_data=f"viewcat_{rest_id}_{k}")] for k, n in cats_list]
    cart_btn = "🛒 Корзина" if not has_cart else "🛒 Корзина (товары есть)"
    kb.append([InlineKeyboardButton(text=cart_btn, callback_data=f"show_cart_{rest_id}")])
    kb.append([InlineKeyboardButton(text="⭐ Отзывы", callback_data=f"reviews_{rest_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def order_status_keyboard(order_id, current_status):
    flow = ["accepted", "cooking", "ready", "delivering", "delivered"]
    kb = []
    if current_status == "new":
        kb.append([InlineKeyboardButton(text="✅ Принять", callback_data=f"setstat_{order_id}_accepted")])
        kb.append([InlineKeyboardButton(text="❌ Отклонить", callback_data=f"setstat_{order_id}_cancelled")])
    elif current_status in flow:
        idx = flow.index(current_status)
        if idx + 1 < len(flow):
            nxt = flow[idx + 1]
            kb.append([InlineKeyboardButton(text=f"➡️ {STATUSES[nxt]}", callback_data=f"setstat_{order_id}_{nxt}")])
        kb.append([InlineKeyboardButton(text="❌ Отменить", callback_data=f"setstat_{order_id}_cancelled")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    r = get_restaurant_by_owner(message.from_user.id)
    if r:
        await message.answer(f"📖 /mycabinet — кабинет\n💰 Тарифы: {PRICE_BASIC}/{PRICE_DESIGN} сомони\n📞 @MuqimjonNiyozov")
        return
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 /admin, /addrest, /subscribe, /block, /unblock, /qr, /pending")
        return
    await message.answer("📖 /start — рестораны\n🍽 Выбирай блюда → корзина → заказ\n📞 @MuqimjonNiyozov")

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT * FROM rest")
    rs = cursor.fetchall()
    if not rs:
        await message.answer("Ресторанов нет."); return
    text = "📋 <b>Рестораны:</b>\n\n"
    for r in rs:
        a = "✅" if is_subscription_active(r) else "❌"
        b = "🚫" if r[6] == 1 else "🟢"
        d = DESIGNS.get(r[8], {}).get('name', '—') if r[8] and r[8] != 'none' else '—'
        text += f"<b>ID {r[0]}:</b> {r[1]}\nВладелец: {r[4]}\n{a} до {r[7] or '—'} | {b}\n🎨 {d} | 💵 {get_price(r)}\n\n"
    await message.answer(text)

class AddRest(StatesGroup):
    waiting_for_owner = State()

@router.message(Command("addrest"))
async def cmd_addrest(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer("Формат: /addrest Название | Адрес | Телефон"); return
    await state.update_data(name=args[1], address=args[2], phone=args[3])
    await message.answer("Перешли сообщение от владельца или введи его Telegram ID:")
    await state.set_state(AddRest.waiting_for_owner)

@router.message(AddRest.waiting_for_owner)
async def process_owner(message: Message, state: FSMContext):
    if message.forward_from: owner_id = message.forward_from.id
    elif message.forward_from_chat: owner_id = message.forward_from_chat.id
    else:
        try: owner_id = int(message.text.strip())
        except: await message.answer("Некорректный ID или /cancel"); return
    data = await state.get_data()
    cursor.execute("INSERT INTO rest (name,address,phone,owner_id,subscribed,blocked) VALUES (%s,%s,%s,%s,%s,%s)",
                   (data['name'], data['address'], data['phone'], owner_id, 0, 0))
    conn.commit()
    await message.answer(f"✅ Добавлен! Владелец {owner_id}\nАктивируй: /subscribe ID 30")
    try:
        await bot.send_message(owner_id, f"🎉 «{data['name']}» добавлен!\n💰 {PRICE_BASIC}/{PRICE_DESIGN} сомони\n📱 Оплата: {PAYMENT_PHONE}\nОтправь фото чека.")
    except: pass
    await state.clear()

@router.message(Command("block"))
async def cmd_block(message: Message):
    if message.from_user.id != ADMIN_ID: return
    a = message.text.split()
    if len(a) < 2: await message.answer("/block ID"); return
    cursor.execute("UPDATE rest SET blocked=1 WHERE id=%s", (a[1],)); conn.commit()
    await message.answer(f"🚫 Заблокирован {a[1]}")

@router.message(Command("unblock"))
async def cmd_unblock(message: Message):
    if message.from_user.id != ADMIN_ID: return
    a = message.text.split()
    if len(a) < 2: await message.answer("/unblock ID"); return
    cursor.execute("UPDATE rest SET blocked=0 WHERE id=%s", (a[1],)); conn.commit()
    await message.answer(f"🟢 Разблокирован {a[1]}")

@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    if message.from_user.id != ADMIN_ID: return
    a = message.text.split()
    if len(a) < 3: await message.answer("/subscribe ID дней"); return
    until = activate_subscription(int(a[1]), int(a[2]))
    await message.answer(f"✅ Подписка {a[1]} до {until}")
    r = get_restaurant_by_id(int(a[1]))
    if r and r[4]:
        try: await bot.send_message(r[4], f"✅ Подписка активна до {until}")
        except: pass

@router.message(Command("pending"))
async def cmd_pending(message: Message):
    if message.from_user.id != ADMIN_ID: return
    ps = get_pending_payments()
    if not ps: await message.answer("Нет платежей"); return
    for p in ps:
        r = get_restaurant_by_id(p[1])
        await message.answer_photo(p[4], caption=f"💳 Платёж #{p[0]}\nРесторан: {r[1] if r else '?'}\nСумма: {p[3]}\n{p[6]}", reply_markup=payment_confirm_keyboard(p[0]))

@router.message(Command("qr"))
async def cmd_qr(message: Message):
    if message.from_user.id != ADMIN_ID: return
    a = message.text.split()
    if len(a) < 2: await message.answer("/qr ID"); return
    r = get_restaurant_by_id(int(a[1]))
    if not r: await message.answer("Не найден"); return
    buf, url = generate_qr(int(a[1]))
    await message.answer_photo(BufferedInputFile(buf.read(), filename="qr.png"), caption=f"📱 QR «{r[1]}»\n🔗 {url}")

@router.callback_query(F.data.startswith("confirm_pay_"))
async def confirm_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return await callback.answer("Нет", show_alert=True)
    pid = int(callback.data.split("_")[2])
    p = get_payment(pid)
    if not p or p[5] != 'pending': return await callback.answer("Обработан", show_alert=True)
    until = activate_subscription(p[1], SUBSCRIPTION_DAYS)
    update_payment_status(pid, 'approved')
    r = get_restaurant_by_id(p[1])
    await callback.message.edit_caption(caption=callback.message.caption + f"\n\n✅ До {until}")
    if r and r[4]:
        try: await bot.send_message(r[4], f"🎉 Оплата подтверждена! До {until}")
        except: pass
    await callback.answer("Готово!")

@router.callback_query(F.data.startswith("reject_pay_"))
async def reject_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return await callback.answer("Нет", show_alert=True)
    pid = int(callback.data.split("_")[2])
    p = get_payment(pid)
    if not p or p[5] != 'pending': return await callback.answer("Обработан", show_alert=True)
    update_payment_status(pid, 'rejected')
    r = get_restaurant_by_id(p[1])
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ Отклонён")
    if r and r[4]:
        try: await bot.send_message(r[4], "❌ Чек отклонён")
        except: pass
    await callback.answer("Готово!")

@router.message(Command("mycabinet"))
async def cmd_mycabinet(message: Message, state: FSMContext):
    await state.clear()
    r = get_restaurant_by_owner(message.from_user.id)
    if not r: return await message.answer("У вас нет ресторана.")
    if r[6] == 1: return await message.answer("🚫 Заблокирован.")
    if not is_subscription_active(r):
        return await message.answer(f"⚠️ Подписка не активна\n💰 {PRICE_BASIC}/{PRICE_DESIGN}\n📱 {PAYMENT_PHONE}\nОтправьте чек.")
    hd = r[8] and r[8] != 'none'
    dl = DESIGNS.get(r[8], {}).get('name', '—') if hd else '❌ нет'
    await message.answer(f"👋 «{r[1]}»\n📅 До: {r[7]}\n🎨 {dl}\n💵 {get_price(r)} сомони", reply_markup=cabinet_keyboard(hd))

@router.callback_query(F.data == "back_to_cabinet")
async def back_to_cabinet(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r: return await callback.answer("Нет", show_alert=True)
    hd = r[8] and r[8] != 'none'
    dl = DESIGNS.get(r[8], {}).get('name', '—') if hd else '❌ нет'
    await callback.message.edit_text(f"👋 «{r[1]}»\n📅 До: {r[7]}\n🎨 {dl}\n💵 {get_price(r)} сомони", reply_markup=cabinet_keyboard(hd))
    await callback.answer()

class EditInfo(StatesGroup):
    waiting_for_history = State()
    waiting_for_hours = State()
    waiting_for_delivery = State()
    waiting_for_min = State()

@router.callback_query(F.data == "edit_info")
async def edit_info(callback: CallbackQuery, state: FSMContext):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await callback.message.answer(f"📖 История (сейчас: {r[10] or '—'})\nНапиши новую или '-' :")
    await state.set_state(EditInfo.waiting_for_history)
    await callback.answer()

@router.message(EditInfo.waiting_for_history)
async def info_h(message: Message, state: FSMContext):
    h = "" if message.text.strip() == '-' else message.text
    await state.update_data(history=h)
    await message.answer("🕐 Часы работы (Пн-Вс 10:00-22:00):")
    await state.set_state(EditInfo.waiting_for_hours)

@router.message(EditInfo.waiting_for_hours)
async def info_hours(message: Message, state: FSMContext):
    await state.update_data(hours=message.text)
    await message.answer("🚚 Стоимость доставки в сомони (0 если бесплатно):")
    await state.set_state(EditInfo.waiting_for_delivery)

@router.message(EditInfo.waiting_for_delivery)
async def info_del(message: Message, state: FSMContext):
    try: dp_ = float(message.text.replace(',', '.'))
    except: return await message.answer("Число")
    await state.update_data(del_price=dp_)
    await message.answer("💰 Минимальная сумма заказа:")
    await state.set_state(EditInfo.waiting_for_min)

@router.message(EditInfo.waiting_for_min)
async def info_min(message: Message, state: FSMContext):
    try: mo = float(message.text.replace(',', '.'))
    except: return await message.answer("Число")
    d = await state.get_data()
    r = get_restaurant_by_owner(message.from_user.id)
    if r:
        update_restaurant_info(r[0], d['history'], d['hours'], d['del_price'], mo)
        await message.answer("✅ Информация обновлена!")
    await state.clear()

@router.callback_query(F.data == "my_qr")
async def show_my_qr(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    buf, url = generate_qr(r[0])
    await callback.message.answer_photo(BufferedInputFile(buf.read(), filename="qr.png"),
                                        caption=f"📱 QR «{r[1]}»\n🔗 <code>{url}</code>\n\nРаспечатайте и положите на столики!")
    await callback.answer()

@router.callback_query(F.data == "choose_design")
async def choose_design(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await callback.message.edit_text(f"🎨 Выберите дизайн\n💵 С дизайном: {PRICE_DESIGN}\n💵 Без: {PRICE_BASIC}", reply_markup=design_choice_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("set_design_"))
async def set_design_handler(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    k = callback.data.replace("set_design_", "")
    if k not in DESIGNS: return await callback.answer("Нет", show_alert=True)
    set_design(r[0], k)
    await callback.message.edit_text(f"✅ Дизайн: {DESIGNS[k]['name']}\n⚠️ Оплатите {PRICE_DESIGN} сомони.",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")]]))
    await callback.answer("Готово!")

@router.callback_query(F.data == "remove_design")
async def remove_design(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r: return await callback.answer("Нет", show_alert=True)
    clear_design(r[0])
    await callback.message.edit_text(f"✅ Дизайн убран. Тариф: {PRICE_BASIC} сомони.",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")]]))
    await callback.answer()

@router.callback_query(F.data == "pay_subscription")
async def pay_subscription(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    await callback.message.answer(f"💳 Сумма: <b>{get_price(r)} сомони</b>\n📱 Номер: <code>{PAYMENT_PHONE}</code>\n\nОтправьте фото чека.")
    await callback.answer()

@router.message(F.photo)
async def handle_receipt(message: Message, state: FSMContext):
    cur_state = await state.get_state()
    if cur_state and (cur_state.startswith("AddItem") or cur_state.startswith("AddPromo") or cur_state.startswith("EditInfo")):
        return
    r = get_restaurant_by_owner(message.from_user.id)
    if not r: return
    if r[6] == 1: return await message.answer("🚫 Заблокирован.")
    if is_subscription_active(r): return await message.answer("✅ Подписка активна.")
    price = get_price(r)
    fid = message.photo[-1].file_id
    pid = add_payment(r[0], message.from_user.id, price, fid)
    try:
        await bot.send_photo(ADMIN_ID, fid, caption=f"💳 Чек\n{r[1]} (ID {r[0]})\nСумма: {price} сомони\nДизайн: {'есть' if r[8] and r[8] != 'none' else 'нет'}",
                             reply_markup=payment_confirm_keyboard(pid))
        await message.answer("📨 Чек отправлен админу.")
    except Exception as e: await message.answer(f"Ошибка: {e}")

class AddItem(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_photo = State()

@router.callback_query(F.data == "add_item")
async def start_add_item(callback: CallbackQuery, state: FSMContext):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await callback.message.answer("Выберите категорию:", reply_markup=category_choice_keyboard("newcat"))
    await state.set_state(AddItem.waiting_for_category)
    await callback.answer()

@router.callback_query(F.data.startswith("newcat_"), AddItem.waiting_for_category)
async def add_item_cat(callback: CallbackQuery, state: FSMContext):
    k = callback.data.replace("newcat_", "")
    if k not in CATEGORIES: return await callback.answer("Нет")
    await state.update_data(category=k)
    await callback.message.answer(f"Категория: {CATEGORIES[k]}\n\nНазвание блюда:")
    await state.set_state(AddItem.waiting_for_name)
    await callback.answer()

@router.message(AddItem.waiting_for_name)
async def add_item_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Описание (или '-'):")
    await state.set_state(AddItem.waiting_for_description)

@router.message(AddItem.waiting_for_description)
async def add_item_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Цена (число):")
    await state.set_state(AddItem.waiting_for_price)

@router.message(AddItem.waiting_for_price)
async def add_item_price(message: Message, state: FSMContext):
    try: p = float(message.text.replace(',', '.'))
    except: return await message.answer("Число!")
    await state.update_data(price=p)
    await message.answer("📸 Фото блюда (или '-' если нет):")
    await state.set_state(AddItem.waiting_for_photo)

@router.message(AddItem.waiting_for_photo, F.photo)
async def add_item_photo(message: Message, state: FSMContext):
    await save_item(message, state, message.photo[-1].file_id)

@router.message(AddItem.waiting_for_photo, F.text == "-")
async def add_item_nophoto(message: Message, state: FSMContext):
    await save_item(message, state, None)

async def save_item(message: Message, state: FSMContext, photo_id):
    d = await state.get_data()
    r = get_restaurant_by_owner(message.from_user.id)
    if r and is_subscription_active(r):
        add_menu_item(r[0], d['name'], d['description'], d['price'], d['category'], photo_id)
        await message.answer(f"✅ «{d['name']}» добавлено в {CATEGORIES[d['category']]}!")
    else:
        await message.answer("Ошибка.")
    await state.clear()

@router.callback_query(F.data == "my_items")
async def show_my_items(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    items = get_menu_items(r[0])
    if not items: return await callback.message.answer("Нет блюд.")
    by_cat = {}
    for i in items: by_cat.setdefault(i[5] or 'other', []).append(i)
    for ck, ci in by_cat.items():
        kb = []
        for i in ci:
            stop = "🚫" if i[7] == 1 else "✅"
            kb.append([InlineKeyboardButton(text=f"{stop} {i[2]} — {i[4]}с", callback_data=f"iteminfo_{i[0]}")])
        await callback.message.answer(f"<b>{CATEGORIES.get(ck, ck)}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("iteminfo_"))
async def item_info(callback: CallbackQuery):
    iid = int(callback.data.split("_")[1])
    i = get_menu_item(iid)
    if not i: return await callback.answer("Нет")
    kb = [
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_item_{iid}")],
        [InlineKeyboardButton(text="🚫 В стоп-лист" if i[7] == 0 else "✅ Убрать из стоп-листа", callback_data=f"stop_{iid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="my_items_back")],
    ]
    await callback.message.answer(f"<b>{i[2]}</b>\n{i[3]}\n💰 {i[4]} сомони", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data == "my_items_back")
async def mi_back(callback: CallbackQuery):
    await callback.message.delete()
    await show_my_items(callback)

@router.callback_query(F.data.startswith("del_item_"))
async def delete_item(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    iid = int(callback.data.split("_")[2])
    delete_menu_item(iid)
    await callback.message.answer("🗑 Удалено.")
    await callback.answer()

@router.callback_query(F.data.startswith("stop_"))
async def stop_item(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    iid = int(callback.data.split("_")[1])
    toggle_stoplist(iid)
    await callback.message.answer("✅ Изменено.")
    await callback.answer()

@router.callback_query(F.data == "my_orders")
async def show_orders(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    orders = get_orders_by_restaurant(r[0])
    if not orders: return await callback.message.answer("Заказов нет.")
    for o in orders[:10]:
        text = (f"<b>Заказ #{o[0]}</b> — {STATUSES.get(o[12], o[12])}\n"
                f"👤 {o[3]}\n📞 {o[4]}\n🏠 {o[5]}\n"
                f"🚚 {'Доставка' if o[9] == 'delivery' else 'Самовывоз'}\n"
                f"🍽 {o[6]}\n💰 {o[7]} сомони\n📅 {o[10]}")
        await callback.message.answer(text, reply_markup=order_status_keyboard(o[0], o[12]))
    await callback.answer()

@router.callback_query(F.data.startswith("setstat_"))
async def set_status(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    parts = callback.data.split("_")
    oid = int(parts[1]); new_st = parts[2]
    update_order_status(oid, new_st)
    await callback.message.edit_text(callback.message.text + f"\n\n➡️ Статус: {STATUSES.get(new_st, new_st)}",
                                     reply_markup=order_status_keyboard(oid, new_st))
    o = get_order(oid)
    if o and o[2]:
        try:
            if new_st == 'delivered':
                await bot.send_message(o[2], f"✅ Заказ #{oid} доставлен!\n\nОставьте отзыв:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"rev_start_{oid}_{o[1]}")]
                ]))
            else:
                await bot.send_message(o[2], f"📢 Заказ #{oid}: {STATUSES.get(new_st, new_st)}")
        except: pass
    await callback.answer("OK")

@router.callback_query(F.data == "analytics")
async def analytics(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    a = get_analytics(r[0], 30)
    text = (f"📊 <b>Аналитика за 30 дней</b>\n\n"
            f"🛒 Заказов: <b>{a['total_orders']}</b>\n"
            f"💰 Выручка: <b>{a['revenue']:.0f} сомони</b>\n"
            f"✅ Доставлено: {a['delivered']}\n"
            f"💵 Оплачено: {a['delivered_revenue']:.0f} сомони\n\n"
            f"<b>По статусам:</b>\n")
    for st, cnt in a['statuses'].items():
        text += f"{STATUSES.get(st, st)}: {cnt}\n"
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data == "my_promos")
async def my_promos(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    promos = get_promos(r[0])
    text = "🎁 <b>Промокоды</b>\n\n"
    kb = [[InlineKeyboardButton(text="➕ Создать промокод", callback_data="new_promo")]]
    if promos:
        for p in promos:
            text += f"<code>{p[2]}</code> — {p[3]}% ({p[4]}/{p[5]})\n"
            kb.append([InlineKeyboardButton(text=f"❌ {p[2]}", callback_data=f"delpromo_{p[0]}")])
    else:
        text += "Пока нет промокодов."
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

class AddPromo(StatesGroup):
    waiting_for_code = State()
    waiting_for_discount = State()
    waiting_for_uses = State()

@router.callback_query(F.data == "new_promo")
async def new_promo(callback: CallbackQuery, state: FSMContext):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await callback.message.answer("Введите код промокода (например SALE10) или '-' для автогенерации:")
    await state.set_state(AddPromo.waiting_for_code)
    await callback.answer()

@router.message(AddPromo.waiting_for_code)
async def promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper() if message.text.strip() != '-' else ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    await state.update_data(code=code)
    await message.answer(f"Код: <code>{code}</code>\n\nСкидка в % (1-90):")
    await state.set_state(AddPromo.waiting_for_discount)

@router.message(AddPromo.waiting_for_discount)
async def promo_disc(message: Message, state: FSMContext):
    try: d = int(message.text)
    except: return await message.answer("Число!")
    if d < 1 or d > 90: return await message.answer("1-90")
    await state.update_data(discount=d)
    await message.answer("Максимум использований (число):")
    await state.set_state(AddPromo.waiting_for_uses)

@router.message(AddPromo.waiting_for_uses)
async def promo_uses(message: Message, state: FSMContext):
    try: u = int(message.text)
    except: return await message.answer("Число!")
    d = await state.get_data()
    r = get_restaurant_by_owner(message.from_user.id)
    if r and create_promo(r[0], d['code'], d['discount'], u):
        await message.answer(f"✅ Промокод <code>{d['code']}</code> на {d['discount']}% создан!")
    else:
        await message.answer("❌ Такой код уже есть.")
    await state.clear()

@router.callback_query(F.data.startswith("delpromo_"))
async def del_promo(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    delete_promo(int(callback.data.split("_")[1]))
    await callback.answer("Удалён")
    await my_promos(callback)

@router.callback_query(F.data.startswith("reviews_"))
async def show_reviews(callback: CallbackQuery):
    rid = int(callback.data.split("_")[1])
    r = get_restaurant_by_id(rid)
    if not r: return await callback.answer("Нет", show_alert=True)
    avg, cnt = get_avg_rating(rid)
    revs = get_reviews(rid, 10)
    text = f"⭐ <b>Отзывы «{r[1]}»</b>\n\nСредняя: <b>{avg}/5</b> ({cnt} отзывов)\n\n"
    for rv in revs:
        stars = "⭐" * rv[1]
        text += f"{stars} {rv[0]}\n{rv[2] or ''}\n📅 {rv[3]}\n\n"
    if not revs: text += "Отзывов пока нет."
    await callback.message.answer(text)
    await callback.answer()

class AddReview(StatesGroup):
    waiting_for_rating = State()
    waiting_for_comment = State()

@router.callback_query(F.data.startswith("rev_start_"))
async def rev_start(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    oid = int(parts[2]); rid = int(parts[3])
    await state.update_data(order_id=oid, rest_id=rid)
    kb = [[InlineKeyboardButton(text=f"{'⭐'*i} {i}", callback_data=f"rate_{i}")] for i in range(5, 0, -1)]
    await callback.message.answer("Оцените заказ:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(AddReview.waiting_for_rating)
    await callback.answer()

@router.callback_query(F.data.startswith("rate_"), AddReview.waiting_for_rating)
async def rev_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)
    await callback.message.answer(f"{'⭐'*rating}\n\nНапишите комментарий (или '-'):")
    await state.set_state(AddReview.waiting_for_comment)
    await callback.answer()

@router.message(AddReview.waiting_for_comment)
async def rev_comment(message: Message, state: FSMContext):
    d = await state.get_data()
    comment = "" if message.text.strip() == '-' else message.text
    add_review(d['rest_id'], message.from_user.id, message.from_user.full_name, d['rating'], comment)
    await message.answer("✅ Спасибо за отзыв!")
    await state.clear()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("rest_"):
        try: rid = int(args[1].replace("rest_", ""))
        except: rid = None
        if rid:
            r = get_restaurant_by_id(rid)
            if not r or not is_subscription_active(r): return await message.answer("❌ Ресторан недоступен.")
            return await show_rest_to_client(message, r)
    r = get_restaurant_by_owner(message.from_user.id)
    if r:
        if is_subscription_active(r): return await message.answer("👋 Ваш кабинет: /mycabinet")
        return await message.answer(f"⚠️ Подписка не активна. Оплата: {get_price(r)} на {PAYMENT_PHONE}")
    rests = get_active_restaurants()
    if not rests: return await message.answer("Пока нет доступных ресторанов.")
    kb = [[InlineKeyboardButton(text=x[1], callback_data=f"show_menu_{x[0]}")] for x in rests]
    await message.answer("🍽 Выбери ресторан:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_rest_to_client(msg, r):
    items = get_menu_items(r[0])
    if not items: return await msg.answer(f"🍽 «{r[1]}»\n\nМеню пока пусто.")
    info = f"🍽 <b>{r[1]}</b>\n"
    if r[2]: info += f"📍 {r[2]}\n"
    if r[3]: info += f"📞 {r[3]}\n"
    if r[11]: info += f"🕐 {r[11]}\n"
    if r[12] and r[12] > 0: info += f"🚚 Доставка: {r[12]} сомони\n"
    else: info += f"🚚 Доставка: бесплатно\n"
    if r[13] and r[13] > 0: info += f"💰 Мин. заказ: {r[13]} сомони\n"
    if r[10]: info += f"\n📖 {r[10]}\n"
    avg, cnt = get_avg_rating(r[0])
    if cnt: info += f"\n⭐ {avg}/5 ({cnt})\n"
    info += "\nВыберите категорию:"
    cats = set(i[5] or 'other' for i in items)
    cats_list = [(k, CATEGORIES[k]) for k in CATEGORIES if k in cats]
    has_cart = len(get_cart(0, r[0])) > 0
    await msg.answer(info, reply_markup=client_categories_keyboard(r[0], cats_list, has_cart))

@router.callback_query(F.data.startswith("show_menu_"))
async def show_menu_cb(callback: CallbackQuery):
    rid = int(callback.data.split("_")[2])
    r = get_restaurant_by_id(rid)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await show_rest_to_client(callback.message, r)
    await callback.answer()

@router.callback_query(F.data.startswith("viewcat_"))
async def view_cat(callback: CallbackQuery):
    parts = callback.data.split("_")
    rid = int(parts[1]); ck = parts[2]
    r = get_restaurant_by_id(rid)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    items = get_menu_items(rid, ck)
    if not items: return await callback.answer("Пусто", show_alert=True)
    dk = r[9] if r[9] and r[9] in DESIGNS else 'classic'
    d = DESIGNS[dk]
    text = f"{d['header']}\n{d['title']} — {CATEGORIES[ck]}\n{d['footer']}"
    kb = [[InlineKeyboardButton(text=f"{d['item']} {i[2]} — {i[4]} {d['price']}", callback_data=f"item_{i[0]}")] for i in items]
    kb.append([InlineKeyboardButton(text="🛒 Корзина", callback_data=f"show_cart_{rid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_rest_{rid}")])
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("back_to_rest_"))
async def back_rest(callback: CallbackQuery):
    rid = int(callback.data.split("_")[3])
    r = get_restaurant_by_id(rid)
    if not r: return await callback.answer("Нет", show_alert=True)
    await show_rest_to_client(callback.message, r)
    await callback.answer()

@router.callback_query(F.data.startswith("item_"))
async def show_item(callback: CallbackQuery):
    iid = int(callback.data.split("_")[1])
    i = get_menu_item(iid)
    if not i: return await callback.answer("Нет", show_alert=True)
    r = get_restaurant_by_id(i[1])
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    cap = f"<b>{i[2]}</b>\n"
    if i[3] and i[3] != '-': cap += f"\n{i[3]}\n"
    cap += f"\n💰 <b>{i[4]} сомони</b>"
    kb = [
        [InlineKeyboardButton(text="➕ В корзину", callback_data=f"addcart_{iid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"viewcat_{i[1]}_{i[5] or 'other'}")],
    ]
    if i[6]:
        await callback.message.answer_photo(i[6], caption=cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await callback.message.answer(cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("addcart_"))
async def addcart(callback: CallbackQuery):
    iid = int(callback.data.split("_")[1])
    i = get_menu_item(iid)
    if not i: return await callback.answer("Нет", show_alert=True)
    add_to_cart(callback.from_user.id, i[1], iid)
    await callback.answer("✅ Добавлено!", show_alert=True)

@router.callback_query(F.data.startswith("show_cart_"))
async def show_cart_cb(callback: CallbackQuery):
    rid = int(callback.data.split("_")[2])
    r = get_restaurant_by_id(rid)
    if not r: return await callback.answer("Нет", show_alert=True)
    items = get_cart(callback.from_user.id, rid)
    if not items: return await callback.answer("Корзина пуста", show_alert=True)
    total = 0
    text = "🛒 <b>Корзина:</b>\n\n"
    kb = []
    for c in items:
        cid_, iid, qty, name, price = c
        st = price * qty
        total += st
        text += f"• {name} × {qty} = {st} сомони\n"
        kb.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"rmcart_{cid_}_{rid}")])
    text += f"\n💰 <b>Итого: {total} сомони</b>"
    if r[13] and total < r[13]:
        text += f"\n⚠️ Мин. заказ: {r[13]} сомони"
    else:
        kb.append([InlineKeyboardButton(text="✅ Оформить", callback_data=f"checkout_{rid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_rest_{rid}")])
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("rmcart_"))
async def rmcart(callback: CallbackQuery):
    parts = callback.data.split("_")
    remove_cart(int(parts[1]))
    await callback.message.delete()
    rid = int(parts[2])
    callback.data = f"show_cart_{rid}"
    await show_cart_cb(callback)

class Checkout(StatesGroup):
    waiting_for_type = State()
    waiting_for_promo = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_address = State()

@router.callback_query(F.data.startswith("checkout_"))
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    rid = int(callback.data.split("_")[1])
    await state.update_data(rest_id=rid)
    kb = [
        [InlineKeyboardButton(text="🚚 Доставка", callback_data="dtype_delivery")],
        [InlineKeyboardButton(text="🏃 Самовывоз", callback_data="dtype_pickup")],
    ]
    await callback.message.answer("Как получите заказ?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(Checkout.waiting_for_type)
    await callback.answer()

@router.callback_query(F.data.startswith("dtype_"), Checkout.waiting_for_type)
async def choose_dtype(callback: CallbackQuery, state: FSMContext):
    dt = callback.data.replace("dtype_", "")
    await state.update_data(dtype=dt)
    await callback.message.answer("🎁 Есть промокод? Введите или '-' :")
    await state.set_state(Checkout.waiting_for_promo)
    await callback.answer()

@router.message(Checkout.waiting_for_promo)
async def checkout_promo(message: Message, state: FSMContext):
    code = message.text.strip()
    if code == '-':
        await state.update_data(promo=None, discount=0)
    else:
        p = get_promo(code)
        if not p:
            await message.answer("❌ Промокод не найден. Попробуйте ещё или '-' :")
            return
        await state.update_data(promo=p[2], discount=p[3])
        await message.answer(f"✅ Промокод применён: -{p[3]}%")
    await message.answer("📝 Ваше имя:")
    await state.set_state(Checkout.waiting_for_name)

@router.message(Checkout.waiting_for_name)
async def checkout_name(message: Message, state: FSMContext):
    await state.update_data(client_name=message.text)
    await message.answer("📞 Телефон:")
    await state.set_state(Checkout.waiting_for_phone)

@router.message(Checkout.waiting_for_phone)
async def checkout_phone(message: Message, state: FSMContext):
    await state.update_data(client_phone=message.text)
    d = await state.get_data()
    if d.get('dtype') == 'pickup':
        await finalize_order(message, state)
    else:
        await message.answer("🏠 Адрес доставки:")
        await state.set_state(Checkout.waiting_for_address)

@router.message(Checkout.waiting_for_address)
async def checkout_addr(message: Message, state: FSMContext):
    await state.update_data(client_address=message.text)
    await finalize_order(message, state)

async def finalize_order(message: Message, state: FSMContext):
    d = await state.get_data()
    rid = d['rest_id']
    r = get_restaurant_by_id(rid)
    if not r or not is_subscription_active(r):
        await message.answer("Ресторан недоступен.")
        return await state.clear()
    cart_items = get_cart(message.from_user.id, rid)
    if not cart_items:
        await message.answer("Корзина пуста.")
        return await state.clear()
    subtotal = sum(c[4] * c[2] for c in cart_items)
    if r[13] and subtotal < r[13]:
        await message.answer(f"⚠️ Минимальная сумма: {r[13]} сомони")
        return await state.clear()
    items_text = ""
    for c in cart_items:
        _, _, qty, name, price = c
        items_text += f"{name} × {qty} = {price*qty} сомони\n"
    discount = 0
    if d.get('discount'):
        discount = subtotal * d['discount'] / 100
    delivery = 0
    if d['dtype'] == 'delivery' and r[12]:
        delivery = r[12]
    total = subtotal - discount + delivery
    addr = d.get('client_address', 'Самовывоз')
    oid = add_order(rid, message.from_user.id, d['client_name'], d['client_phone'],
                    addr, items_text, total, subtotal, d['dtype'], d.get('promo'), discount)
    if d.get('promo'):
        p = get_promo(d['promo'])
        if p: use_promo(p[0])
    clear_cart(message.from_user.id, rid)
    if r[4]:
        try:
            promo_line = f"🎁 Промокод: {d['promo']} (-{discount:.0f})\n" if d.get('promo') else ""
            del_line = f"🚚 Доставка: {delivery} сомони\n" if delivery else ""
            await bot.send_message(r[4],
                f"🔔 <b>НОВЫЙ ЗАКАЗ #{oid}!</b>\n\n"
                f"👤 {d['client_name']}\n📞 {d['client_phone']}\n"
                f"{'🏠 ' + addr if d['dtype'] == 'delivery' else '🏃 Самовывоз'}\n\n"
                f"🍽 {items_text}\n"
                f"{promo_line}{del_line}"
                f"💰 <b>Итого: {total:.0f} сомони</b>\n\n→ /mycabinet → 🛒 Заказы")
        except: pass
    dtype_text = "доставлен" if d['dtype'] == 'delivery' else "готов к самовывозу"
    await message.answer(f"✅ <b>Заказ #{oid} оформлен!</b>\n\n💰 Сумма: {total:.0f} сомони\nБудет {dtype_text}.")
    await state.clear()

async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook set to {WEBHOOK_URL}")

def main():
    dp.startup.register(on_startup)
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    port = int(os.environ.get("PORT", 5000))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
