import asyncio, logging, os, random, string
from datetime import datetime, timedelta
from io import BytesIO
import psycopg2, qrcode
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile)
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

BOT_TOKEN = "8890056509:AAFvSsiaD0pZPHGRAa3iWRwfNdae3II7ttc"
ADMIN_ID = 7758384445
BOT_USERNAME = "Aura_Muqimjon_bot"
WEBHOOK_URL = "https://menu-master-bot.onrender.com/webhook"
PAYMENT_PHONE = "993337070"
PRICE_BASIC, PRICE_DESIGN, SUBSCRIPTION_DAYS = 50, 60, 30

CATEGORIES = {"salads":"🥗 Салаты","soups":"🍲 Супы","hot":"🍖 Горячее","fastfood":"🍔 Фастфуд","desserts":"🍰 Десерты","drinks":"🥤 Напитки","other":"🍽 Другое"}

DESIGNS = {
    "classic":{"name":"📋 Классик","desc":"Строгий","header":"━━━━━━━━━","item":"▫️","title":"🍽 Меню","price":"сомони","footer":"━━━━━━━━━"},
    "modern":{"name":"⚡ Модерн","desc":"Современный","header":"🔥🔥🔥🔥🔥","item":"⚡","title":"🍔 МЕНЮ","price":" TJS","footer":"🔥🔥🔥🔥🔥"},
    "elegant":{"name":"✨ Элегант","desc":"Премиум","header":"✦ ───── ✦","item":"✨","title":"👑 Избранное","price":"сомони","footer":"✦ ───── ✦"},
    "fun":{"name":"🎉 Весёлый","desc":"Яркий","header":"🎉🎊🎈🎊🎉","item":"🌟","title":"😋 Что покушаем?","price":"сом","footer":"🎈🎊🎉🎊🎈"},
    "night":{"name":"🌙 Ночной","desc":"Тёмный","header":"🌙 ─ ─ ─ 🌙","item":"🍷","title":"🌙 Ночное","price":"сомони","footer":"🌙 ─ ─ ─ 🌙"},
    "sea":{"name":"🌊 Морской","desc":"Свежий","header":"🌊≈≈≈≈≈🌊","item":"🐟","title":"🐚 Дары моря","price":"сомони","footer":"🌊≈≈≈≈≈🌊"},
    "fire":{"name":"🔥 Огненный","desc":"Горячий","header":"🔥▬▬🔥▬▬🔥","item":"🔥","title":"🍖 Горячее!","price":"сом","footer":"🔥▬▬🔥▬▬🔥"},
    "royal":{"name":"👑 Королевский","desc":"Царский","header":"⚜️ ═══ ⚜️","item":"👑","title":"🏰 Королевский стол","price":"сомони","footer":"⚜️ ═══ ⚜️"},
    "sakura":{"name":"🌸 Сакура","desc":"Нежный","header":"🌸 ⋆｡°✩ 🌸","item":"🌸","title":"🍡 Нежное меню","price":"сомони","footer":"🌸 ⋆｡°✩ 🌸"},
    "cafe":{"name":"☕ Кофейня","desc":"Уютный","header":"☕ ━ ☕ ━ ☕","item":"☕","title":"🍰 Уютное меню","price":"сомони","footer":"☕ ━ ☕ ━ ☕"},
    "kids":{"name":"🧸 Детский","desc":"Милый","header":"🧸🎀🧸🎀🧸","item":"🎈","title":"🍭 Для детей","price":"сом","footer":"🧸🎀🧸🎀🧸"},
    "sport":{"name":"💪 Спортивный","desc":"Энергичный","header":"💪▬💪▬💪","item":"🥩","title":"🏋️ Спорт-меню","price":"сом","footer":"💪▬💪▬💪"},
    "vegan":{"name":"🥗 Веган","desc":"Здоровый","header":"🌱═══🌱","item":"🥬","title":"🥗 Полезное меню","price":"сомони","footer":"🌱═══🌱"},
    "grill":{"name":"🍖 Гриль","desc":"Мясной","header":"🔥🍖🔥🍖🔥","item":"🍗","title":"🍖 Мясное меню","price":"сом","footer":"🔥🍖🔥🍖🔥"},
    "italy":{"name":"🇮🇹 Италия","desc":"Средиземномор.","header":"🇮🇹 ═ 🍕 ═ 🇮🇹","item":"🍕","title":"🍕 Итальянское меню","price":"сомони","footer":"🇮🇹 ═ 🍕 ═ 🇮🇹"},
    "asia":{"name":"🥢 Азия","desc":"Восточный","header":"🏮═══🏮","item":"🥢","title":"🍜 Восточное меню","price":"сомони","footer":"🏮═══🏮"},
    "burger":{"name":"🍔 Бургерная","desc":"Фастфуд","header":"🍔🍟🥤🍔🍟","item":"🍔","title":"🍟 Быстро и вкусно","price":"сом","footer":"🥤🍟🍔🍟🥤"},
    "sweet":{"name":"🍰 Сладкий","desc":"Десерты","header":"🍩🍰🧁🍰🍩","item":"🧁","title":"🍭 Сладкое меню","price":"сом","footer":"🍩🍰🧁🍰🍩"},
    "cocktail":{"name":"🍹 Бар","desc":"Напитки","header":"🍸━🍹━🍸","item":"🍸","title":"🍹 Барное меню","price":"сомони","footer":"🍸━🍹━🍸"},
    "street":{"name":"🛵 Стритфуд","desc":"Уличная еда","header":"🛵▪▪▪🛵","item":"🌭","title":"🌭 Стрит-меню","price":"сом","footer":"🛵▪▪▪🛵"},
}

STATUSES = {"new":"🆕 Новый","accepted":"✅ Принят","cooking":"👨‍🍳 Готовится","ready":"🍽 Готов","delivering":"🚚 В пути","delivered":"🏁 Доставлен","cancelled":"❌ Отменён"}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(); router = Router(); dp.include_router(router)

DATABASE_URL = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL); cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS rest (id SERIAL PRIMARY KEY, name TEXT NOT NULL, address TEXT, phone TEXT, owner_id BIGINT, subscribed INTEGER DEFAULT 0, blocked INTEGER DEFAULT 0, subscribe_until TEXT, design TEXT DEFAULT 'none', active_design TEXT DEFAULT 'classic', history TEXT, work_hours TEXT, delivery_price REAL DEFAULT 0, min_order REAL DEFAULT 0, map_link TEXT, logo_file_id TEXT, banner_file_id TEXT)''')
for col, ct in [("design","TEXT DEFAULT 'none'"),("active_design","TEXT DEFAULT 'classic'"),("history","TEXT"),("work_hours","TEXT"),("delivery_price","REAL DEFAULT 0"),("min_order","REAL DEFAULT 0"),("map_link","TEXT"),("logo_file_id","TEXT"),("banner_file_id","TEXT")]:
    try: cursor.execute(f"ALTER TABLE rest ADD COLUMN IF NOT EXISTS {col} {ct}"); conn.commit()
    except: conn.rollback()

cursor.execute('''CREATE TABLE IF NOT EXISTS menu (id SERIAL PRIMARY KEY, rest_id INTEGER, name TEXT, description TEXT, price REAL, category TEXT DEFAULT 'other', photo_id TEXT, stoplist INTEGER DEFAULT 0)''')
for col, ct in [("category","TEXT DEFAULT 'other'"),("photo_id","TEXT"),("stoplist","INTEGER DEFAULT 0")]:
    try: cursor.execute(f"ALTER TABLE menu ADD COLUMN IF NOT EXISTS {col} {ct}"); conn.commit()
    except: conn.rollback()

cursor.execute('''CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, rest_id INTEGER, client_id BIGINT, client_name TEXT, client_phone TEXT, client_address TEXT, items_text TEXT, total REAL, subtotal REAL, delivery_type TEXT DEFAULT 'delivery', promo_code TEXT, discount REAL DEFAULT 0, status TEXT DEFAULT 'new', created_at TEXT, updated_at TEXT)''')
for col, ct in [("subtotal","REAL"),("delivery_type","TEXT DEFAULT 'delivery'"),("promo_code","TEXT"),("discount","REAL DEFAULT 0"),("updated_at","TEXT"),("client_id","BIGINT")]:
    try: cursor.execute(f"ALTER TABLE orders ADD COLUMN IF NOT EXISTS {col} {ct}"); conn.commit()
    except: conn.rollback()

cursor.execute('''CREATE TABLE IF NOT EXISTS payments (id SERIAL PRIMARY KEY, rest_id INTEGER, owner_id BIGINT, amount INTEGER, receipt_file_id TEXT, status TEXT DEFAULT 'pending', created_at TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS cart (id SERIAL PRIMARY KEY, client_id BIGINT, rest_id INTEGER, item_id INTEGER, quantity INTEGER DEFAULT 1, created_at TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (id SERIAL PRIMARY KEY, rest_id INTEGER, client_id BIGINT, client_name TEXT, rating INTEGER, comment TEXT, created_at TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS promocodes (id SERIAL PRIMARY KEY, rest_id INTEGER, code TEXT UNIQUE, discount_percent INTEGER DEFAULT 10, max_uses INTEGER DEFAULT 100, used_count INTEGER DEFAULT 0, active INTEGER DEFAULT 1, created_at TEXT)''')
conn.commit()

def get_restaurant_by_owner(oid):
    cursor.execute("SELECT * FROM rest WHERE owner_id=%s", (oid,)); return cursor.fetchone()
def get_restaurant_by_id(rid):
    cursor.execute("SELECT * FROM rest WHERE id=%s", (rid,)); return cursor.fetchone()
def get_active_restaurants():
    cursor.execute("SELECT * FROM rest WHERE blocked=0 AND subscribed=1"); return cursor.fetchall()
def get_menu_items(rid, cat=None):
    if cat: cursor.execute("SELECT * FROM menu WHERE rest_id=%s AND category=%s AND stoplist=0", (rid, cat))
    else: cursor.execute("SELECT * FROM menu WHERE rest_id=%s AND stoplist=0", (rid,))
    return cursor.fetchall()
def search_menu(rid, q):
    cursor.execute("SELECT * FROM menu WHERE rest_id=%s AND stoplist=0 AND (LOWER(name) LIKE %s OR LOWER(description) LIKE %s)", (rid, f"%{q.lower()}%", f"%{q.lower()}%")); return cursor.fetchall()
def get_menu_item(iid):
    cursor.execute("SELECT * FROM menu WHERE id=%s", (iid,)); return cursor.fetchone()
def add_menu_item(rid, n, d, p, c, ph):
    cursor.execute("INSERT INTO menu (rest_id,name,description,price,category,photo_id) VALUES (%s,%s,%s,%s,%s,%s)", (rid,n,d,p,c,ph)); conn.commit()
def delete_menu_item(iid):
    cursor.execute("DELETE FROM menu WHERE id=%s", (iid,)); conn.commit()
def toggle_stoplist(iid):
    cursor.execute("UPDATE menu SET stoplist=1-stoplist WHERE id=%s", (iid,)); conn.commit()
def update_price(iid, np):
    cursor.execute("UPDATE menu SET price=%s WHERE id=%s", (np, iid)); conn.commit()
def add_order(rid, cid, cn, cp, ca, it, tot, sub, dt, promo, disc):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO orders (rest_id,client_id,client_name,client_phone,client_address,items_text,total,subtotal,delivery_type,promo_code,discount,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (rid,cid,cn,cp,ca,it,tot,sub,dt,promo,disc,now,now)); conn.commit(); return cursor.lastrowid
def get_orders_by_restaurant(rid):
    cursor.execute("SELECT * FROM orders WHERE rest_id=%s ORDER BY id DESC LIMIT 30", (rid,)); return cursor.fetchall()
def get_client_orders(cid):
    cursor.execute("SELECT * FROM orders WHERE client_id=%s ORDER BY id DESC LIMIT 20", (cid,)); return cursor.fetchall()
def get_order(oid):
    cursor.execute("SELECT * FROM orders WHERE id=%s", (oid,)); return cursor.fetchone()
def update_order_status(oid, st):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE orders SET status=%s,updated_at=%s WHERE id=%s", (st,now,oid)); conn.commit()
def update_restaurant_info(rid, hist, hrs, dp_, mo, mp):
    cursor.execute("UPDATE rest SET history=%s,work_hours=%s,delivery_price=%s,min_order=%s,map_link=%s WHERE id=%s", (hist,hrs,dp_,mo,mp,rid)); conn.commit()
def is_subscription_active(r):
    if not r: return False
    if r[6]==1 or r[5]!=1 or not r[7]: return False
    try: return datetime.strptime(r[7],"%Y-%m-%d") >= datetime.now()
    except: return False
def activate_subscription(rid, days=30):
    until = (datetime.now()+timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("UPDATE rest SET subscribed=1,subscribe_until=%s WHERE id=%s", (until,rid)); conn.commit(); return until
def set_design(rid, k):
    cursor.execute("UPDATE rest SET design=%s,active_design=%s WHERE id=%s", (k,k,rid)); conn.commit()
def clear_design(rid):
    cursor.execute("UPDATE rest SET design='none' WHERE id=%s", (rid,)); conn.commit()
def get_price(r):
    return PRICE_DESIGN if r and r[8] and r[8]!='none' else PRICE_BASIC
def add_payment(rid, oid, amt, fid):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO payments (rest_id,owner_id,amount,receipt_file_id,created_at) VALUES (%s,%s,%s,%s,%s)", (rid,oid,amt,fid,now)); conn.commit(); return cursor.lastrowid
def get_payment(pid):
    cursor.execute("SELECT * FROM payments WHERE id=%s", (pid,)); return cursor.fetchone()
def update_payment_status(pid, st):
    cursor.execute("UPDATE payments SET status=%s WHERE id=%s", (st,pid)); conn.commit()
def get_pending_payments():
    cursor.execute("SELECT * FROM payments WHERE status='pending'"); return cursor.fetchall()
def get_cart(cid, rid):
    cursor.execute("SELECT c.id,c.item_id,c.quantity,m.name,m.price FROM cart c JOIN menu m ON c.item_id=m.id WHERE c.client_id=%s AND c.rest_id=%s", (cid,rid)); return cursor.fetchall()
def add_to_cart(cid, rid, iid):
    cursor.execute("SELECT id FROM cart WHERE client_id=%s AND item_id=%s", (cid,iid)); ex = cursor.fetchone()
    if ex: cursor.execute("UPDATE cart SET quantity=quantity+1 WHERE id=%s", (ex[0],))
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO cart (client_id,rest_id,item_id,created_at) VALUES (%s,%s,%s,%s)", (cid,rid,iid,now))
    conn.commit()
def clear_cart(cid, rid):
    cursor.execute("DELETE FROM cart WHERE client_id=%s AND rest_id=%s", (cid,rid)); conn.commit()
def remove_cart(cid):
    cursor.execute("DELETE FROM cart WHERE id=%s", (cid,)); conn.commit()
def generate_qr(rid):
    url = f"https://t.me/{BOT_USERNAME}?start=rest_{rid}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4); qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO(); img.save(buf, format="PNG"); buf.seek(0); return buf, url
def add_review(rid, cid, nm, rt, cm):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO reviews (rest_id,client_id,client_name,rating,comment,created_at) VALUES (%s,%s,%s,%s,%s,%s)", (rid,cid,nm,rt,cm,now)); conn.commit()
def get_reviews(rid, lim=10):
    cursor.execute("SELECT client_name,rating,comment,created_at FROM reviews WHERE rest_id=%s ORDER BY id DESC LIMIT %s", (rid,lim)); return cursor.fetchall()
def get_avg_rating(rid):
    cursor.execute("SELECT AVG(rating),COUNT(*) FROM reviews WHERE rest_id=%s", (rid,)); row = cursor.fetchone()
    if row and row[0]: return round(float(row[0]),1), row[1]
    return 0, 0
def create_promo(rid, code, disc, mu):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("INSERT INTO promocodes (rest_id,code,discount_percent,max_uses,created_at) VALUES (%s,%s,%s,%s,%s)", (rid,code.upper(),disc,mu,now)); conn.commit(); return True
    except: conn.rollback(); return False
def get_promo(code):
    cursor.execute("SELECT * FROM promocodes WHERE code=%s AND active=1", (code.upper(),)); return cursor.fetchone()
def use_promo(pid):
    cursor.execute("UPDATE promocodes SET used_count=used_count+1 WHERE id=%s", (pid,)); conn.commit()
def get_promos(rid):
    cursor.execute("SELECT * FROM promocodes WHERE rest_id=%s ORDER BY id DESC", (rid,)); return cursor.fetchall()
def delete_promo(pid):
    cursor.execute("DELETE FROM promocodes WHERE id=%s", (pid,)); conn.commit()
def get_analytics(rid, days=30):
    fd = (datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*),COALESCE(SUM(total),0) FROM orders WHERE rest_id=%s AND status IN ('accepted','cooking','ready','delivering','delivered') AND created_at>=%s", (rid,fd))
    row = cursor.fetchone(); to, tr = (row[0],row[1]) if row else (0,0)
    cursor.execute("SELECT COUNT(*),COALESCE(SUM(total),0) FROM orders WHERE rest_id=%s AND status='delivered' AND created_at>=%s", (rid,fd))
    row = cursor.fetchone(); dl, dr = (row[0],row[1]) if row else (0,0)
    cursor.execute("SELECT status,COUNT(*) FROM orders WHERE rest_id=%s AND created_at>=%s GROUP BY status", (rid,fd))
    sts = dict(cursor.fetchall())
    cursor.execute("""SELECT m.name, COUNT(*) FROM orders o JOIN menu m ON o.items_text LIKE '%%'||m.name||'%%' WHERE o.rest_id=%s AND o.created_at>=%s GROUP BY m.name ORDER BY COUNT(*) DESC LIMIT 5""", (rid,fd))
    top = cursor.fetchall()
    return {"total_orders":to,"revenue":tr,"delivered":dl,"delivered_rev":dr,"statuses":sts,"top_items":top}
def get_all_clients(rid):
    cursor.execute("SELECT DISTINCT client_id,client_name,client_phone FROM orders WHERE rest_id=%s", (rid,)); return cursor.fetchall()
def get_all_restaurants_clients(rid):
    cursor.execute("SELECT DISTINCT client_id FROM orders WHERE rest_id=%s", (rid,)); return [x[0] for x in cursor.fetchall() if x[0]]

def cabinet_keyboard(has_design):
    kb = [
        [InlineKeyboardButton(text="📝 Добавить блюдо", callback_data="add_item")],
        [InlineKeyboardButton(text="🍽 Мои блюда", callback_data="my_items")],
        [InlineKeyboardButton(text="🛒 Заказы", callback_data="my_orders")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="analytics")],
        [InlineKeyboardButton(text="👥 Клиенты", callback_data="clients")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton(text="🎁 Промокоды", callback_data="my_promos")],
        [InlineKeyboardButton(text="🖼 Логотип и баннер", callback_data="edit_brand")],
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
    kb = []
    items = list(DESIGNS.items())
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(text=items[i][1]['name'], callback_data=f"set_design_{items[i][0]}")]
        if i+1 < len(items): row.append(InlineKeyboardButton(text=items[i+1][1]['name'], callback_data=f"set_design_{items[i+1][0]}"))
        kb.append(row)
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def category_choice_keyboard(prefix="newcat"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=n, callback_data=f"{prefix}_{k}")] for k,n in CATEGORIES.items()])

def payment_confirm_keyboard(pid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_pay_{pid}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_pay_{pid}")],
    ])

def client_categories_keyboard(rid, cats_list):
    kb = [[InlineKeyboardButton(text=n, callback_data=f"viewcat_{rid}_{k}")] for k,n in cats_list]
    kb.append([InlineKeyboardButton(text="🔍 Поиск", callback_data=f"search_{rid}")])
    kb.append([InlineKeyboardButton(text="🛒 Корзина", callback_data=f"show_cart_{rid}")])
    kb.append([InlineKeyboardButton(text="⭐ Отзывы", callback_data=f"reviews_{rid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def order_status_keyboard(oid, cs):
    flow = ["accepted","cooking","ready","delivering","delivered"]
    kb = []
    if cs == "new":
        kb.append([InlineKeyboardButton(text="✅ Принять", callback_data=f"setstat_{oid}_accepted")])
        kb.append([InlineKeyboardButton(text="❌ Отклонить", callback_data=f"setstat_{oid}_cancelled")])
    elif cs in flow:
        idx = flow.index(cs)
        if idx+1 < len(flow):
            kb.append([InlineKeyboardButton(text=f"➡️ {STATUSES[flow[idx+1]]}", callback_data=f"setstat_{oid}_{flow[idx+1]}")])
        kb.append([InlineKeyboardButton(text="❌ Отменить", callback_data=f"setstat_{oid}_cancelled")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear(); await message.answer("Действие отменено.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    r = get_restaurant_by_owner(message.from_user.id)
    if r: return await message.answer(f"📖 /mycabinet — кабинет\n💰 {PRICE_BASIC}/{PRICE_DESIGN} сомони\n📞 @MuqimjonNiyozov")
    if message.from_user.id == ADMIN_ID: return await message.answer("👑 /admin, /addrest, /subscribe, /block, /unblock, /qr, /pending")
    await message.answer("📖 /start — рестораны\n📋 /myorders — мои заказы")

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT * FROM rest"); rs = cursor.fetchall()
    if not rs: return await message.answer("Ресторанов нет.")
    text = "📋 <b>Рестораны:</b>\n\n"
    for r in rs:
        a = "✅" if is_subscription_active(r) else "❌"; b = "🚫" if r[6]==1 else "🟢"
        d = DESIGNS.get(r[8],{}).get('name','—') if r[8] and r[8]!='none' else '—'
        text += f"<b>ID {r[0]}:</b> {r[1]}\nВладелец: {r[4]}\n{a} до {r[7] or '—'} | {b}\n🎨 {d} | 💵 {get_price(r)}\n\n"
    await message.answer(text)

class AddRest(StatesGroup):
    waiting_for_owner = State()

@router.message(Command("addrest"))
async def cmd_addrest(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split(maxsplit=3)
    if len(args) < 4: return await message.answer("Формат: /addrest Название | Адрес | Телефон")
    await state.update_data(name=args[1], address=args[2], phone=args[3])
    await message.answer("Перешли сообщение от владельца или введи его Telegram ID:")
    await state.set_state(AddRest.waiting_for_owner)

@router.message(AddRest.waiting_for_owner)
async def process_owner(message: Message, state: FSMContext):
    if message.forward_from: oid = message.forward_from.id
    elif message.forward_from_chat: oid = message.forward_from_chat.id
    else:
        try: oid = int(message.text.strip())
        except: return await message.answer("Некорректный ID или /cancel")
    d = await state.get_data()
    cursor.execute("INSERT INTO rest (name,address,phone,owner_id,subscribed,blocked) VALUES (%s,%s,%s,%s,%s,%s)", (d['name'],d['address'],d['phone'],oid,0,0)); conn.commit()
    await message.answer(f"✅ Добавлен! Владелец {oid}\nАктивируй: /subscribe ID 30")
    try: await bot.send_message(oid, f"🎉 «{d['name']}» добавлен!\n💰 {PRICE_BASIC}/{PRICE_DESIGN}\n📱 Оплата: {PAYMENT_PHONE}\nОтправь фото чека.")
    except: pass
    await state.clear()

@router.message(Command("block"))
async def cmd_block(message: Message):
    if message.from_user.id != ADMIN_ID: return
    a = message.text.split()
    if len(a) < 2: return await message.answer("/block ID")
    cursor.execute("UPDATE rest SET blocked=1 WHERE id=%s", (a[1],)); conn.commit()
    await message.answer(f"🚫 Заблокирован {a[1]}")

@router.message(Command("unblock"))
async def cmd_unblock(message: Message):
    if message.from_user.id != ADMIN_ID: return
    a = message.text.split()
    if len(a) < 2: return await message.answer("/unblock ID")
    cursor.execute("UPDATE rest SET blocked=0 WHERE id=%s", (a[1],)); conn.commit()
    await message.answer(f"🟢 Разблокирован {a[1]}")

@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    if message.from_user.id != ADMIN_ID: return
    a = message.text.split()
    if len(a) < 3: return await message.answer("/subscribe ID дней")
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
    if not ps: return await message.answer("Нет платежей")
    for p in ps:
        r = get_restaurant_by_id(p[1])
        await message.answer_photo(p[4], caption=f"💳 Платёж #{p[0]}\nРесторан: {r[1] if r else '?'}\nСумма: {p[3]}\n{p[6]}", reply_markup=payment_confirm_keyboard(p[0]))

@router.message(Command("qr"))
async def cmd_qr(message: Message):
    if message.from_user.id != ADMIN_ID: return
    a = message.text.split()
    if len(a) < 2: return await message.answer("/qr ID")
    r = get_restaurant_by_id(int(a[1]))
    if not r: return await message.answer("Не найден")
    buf, url = generate_qr(int(a[1]))
    await message.answer_photo(BufferedInputFile(buf.read(), filename="qr.png"), caption=f"📱 QR «{r[1]}»\n🔗 {url}")

@router.callback_query(F.data.startswith("confirm_pay_"))
async def confirm_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return await callback.answer("Нет", show_alert=True)
    pid = int(callback.data.split("_")[2]); p = get_payment(pid)
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
    pid = int(callback.data.split("_")[2]); p = get_payment(pid)
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
    dl = DESIGNS.get(r[8],{}).get('name','—') if hd else '❌ нет'
    await message.answer(f"👋 «{r[1]}»\n📅 До: {r[7]}\n🎨 {dl}\n💵 {get_price(r)} сомони", reply_markup=cabinet_keyboard(hd))

@router.callback_query(F.data == "back_to_cabinet")
async def back_to_cabinet(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r: return await callback.answer("Нет", show_alert=True)
    hd = r[8] and r[8] != 'none'
    dl = DESIGNS.get(r[8],{}).get('name','—') if hd else '❌ нет'
    await callback.message.edit_text(f"👋 «{r[1]}»\n📅 До: {r[7]}\n🎨 {dl}\n💵 {get_price(r)} сомони", reply_markup=cabinet_keyboard(hd))
    await callback.answer()

class EditInfo(StatesGroup):
    waiting_for_history = State()
    waiting_for_hours = State()
    waiting_for_delivery = State()
    waiting_for_min = State()
    waiting_for_map = State()

@router.callback_query(F.data == "edit_info")
async def edit_info(callback: CallbackQuery, state: FSMContext):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await callback.message.answer(f"📖 История (сейчас: {r[10] or '—'})\nНапиши новую или '-' :")
    await state.set_state(EditInfo.waiting_for_history); await callback.answer()

@router.message(EditInfo.waiting_for_history)
async def info_h(message: Message, state: FSMContext):
    h = "" if message.text.strip() == '-' else message.text
    await state.update_data(history=h)
    await message.answer("🕐 Часы работы:")
    await state.set_state(EditInfo.waiting_for_hours)

@router.message(EditInfo.waiting_for_hours)
async def info_hours(message: Message, state: FSMContext):
    await state.update_data(hours=message.text)
    await message.answer("🚚 Стоимость доставки (0 если бесплатно):")
    await state.set_state(EditInfo.waiting_for_delivery)

@router.message(EditInfo.waiting_for_delivery)
async def info_del(message: Message, state: FSMContext):
    try: dp_ = float(message.text.replace(',','.'))
    except: return await message.answer("Число")
    await state.update_data(del_price=dp_)
    await message.answer("💰 Минимальная сумма заказа:")
    await state.set_state(EditInfo.waiting_for_min)

@router.message(EditInfo.waiting_for_min)
async def info_min(message: Message, state: FSMContext):
    try: mo = float(message.text.replace(',','.'))
    except: return await message.answer("Число")
    await state.update_data(min_order=mo)
    await message.answer("🗺 Ссылка на Google Maps или '-' :")
    await state.set_state(EditInfo.waiting_for_map)

@router.message(EditInfo.waiting_for_map)
async def info_map(message: Message, state: FSMContext):
    mp = "" if message.text.strip() == '-' else message.text
    d = await state.get_data()
    r = get_restaurant_by_owner(message.from_user.id)
    if r:
        update_restaurant_info(r[0], d['history'], d['hours'], d['del_price'], d['min_order'], mp)
        await message.answer("✅ Информация обновлена!")
    await state.clear()

class EditBrand(StatesGroup):
    waiting_for_logo = State()
    waiting_for_banner = State()

@router.callback_query(F.data == "edit_brand")
async def edit_brand(callback: CallbackQuery, state: FSMContext):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await callback.message.answer("🖼 <b>Логотип и баннер</b>\n\n1️⃣ Отправь <b>логотип</b> (квадрат). Или '-' :")
    await state.set_state(EditBrand.waiting_for_logo); await callback.answer()

@router.message(EditBrand.waiting_for_logo, F.photo)
async def brand_logo(message: Message, state: FSMContext):
    r = get_restaurant_by_owner(message.from_user.id)
    if r:
        cursor.execute("UPDATE rest SET logo_file_id=%s WHERE id=%s", (message.photo[-1].file_id, r[0])); conn.commit()
    await message.answer("✅ Логотип сохранён.\n\n2️⃣ Теперь <b>баннер</b> (1200×600). Или '-' :")
    await state.set_state(EditBrand.waiting_for_banner)

@router.message(EditBrand.waiting_for_logo, F.text == "-")
async def brand_logo_skip(message: Message, state: FSMContext):
    await message.answer("Пропущено.\n\n2️⃣ Теперь <b>баннер</b> или '-' :")
    await state.set_state(EditBrand.waiting_for_banner)

@router.message(EditBrand.waiting_for_banner, F.photo)
async def brand_banner(message: Message, state: FSMContext):
    r = get_restaurant_by_owner(message.from_user.id)
    if r:
        cursor.execute("UPDATE rest SET banner_file_id=%s WHERE id=%s", (message.photo[-1].file_id, r[0])); conn.commit()
    await message.answer("✅ Баннер сохранён! Клиенты увидят его при открытии меню.")
    await state.clear()

@router.message(EditBrand.waiting_for_banner, F.text == "-")
async def brand_banner_skip(message: Message, state: FSMContext):
    await message.answer("✅ Готово."); await state.clear()

@router.callback_query(F.data == "my_qr")
async def show_my_qr(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    buf, url = generate_qr(r[0])
    await callback.message.answer_photo(BufferedInputFile(buf.read(), filename="qr.png"), caption=f"📱 QR «{r[1]}»\n🔗 <code>{url}</code>\n\nРаспечатайте и положите на столики!")
    await callback.answer()

@router.callback_query(F.data == "choose_design")
async def choose_design(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await callback.message.edit_text(f"🎨 <b>Выберите дизайн</b> (20 шт.)\n\n💵 С дизайном: {PRICE_DESIGN}\n💵 Без: {PRICE_BASIC}", reply_markup=design_choice_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("set_design_"))
async def set_design_handler(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    k = callback.data.replace("set_design_","")
    if k not in DESIGNS: return await callback.answer("Нет", show_alert=True)
    set_design(r[0], k)
    d = DESIGNS[k]
    preview = f"{d['header']}\n{d['title']}\n{d['footer']}\n\n{d['item']} Пример — 25 {d['price']}"
    await callback.message.edit_text(f"✅ Дизайн: <b>{d['name']}</b>\n\n{preview}\n\n⚠️ Оплатите {PRICE_DESIGN} сомони.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")]]))
    await callback.answer("Готово!")

@router.callback_query(F.data == "remove_design")
async def remove_design(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r: return await callback.answer("Нет", show_alert=True)
    clear_design(r[0])
    await callback.message.edit_text(f"✅ Дизайн убран. Тариф: {PRICE_BASIC} сомони.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")]]))
    await callback.answer()

@router.callback_query(F.data == "pay_subscription")
async def pay_subscription(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    await callback.message.answer(f"💳 Сумма: <b>{get_price(r)} сомони</b>\n📱 Номер: <code>{PAYMENT_PHONE}</code>\n\nОтправьте фото чека.")
    await callback.answer()

@router.message(StateFilter(None), F.photo)
async def handle_receipt(message: Message):
    r = get_restaurant_by_owner(message.from_user.id)
    if not r: return
    if r[6] == 1: return await message.answer("🚫 Заблокирован.")
    if is_subscription_active(r): return await message.answer("✅ Подписка активна.")
    price = get_price(r); fid = message.photo[-1].file_id
    pid = add_payment(r[0], message.from_user.id, price, fid)
    try:
        await bot.send_photo(ADMIN_ID, fid, caption=f"💳 Чек\n{r[1]} (ID {r[0]})\nСумма: {price} сомони\nДизайн: {'есть' if r[8] and r[8]!='none' else 'нет'}", reply_markup=payment_confirm_keyboard(pid))
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
    await state.set_state(AddItem.waiting_for_category); await callback.answer()

@router.callback_query(F.data.startswith("newcat_"), AddItem.waiting_for_category)
async def add_item_cat(callback: CallbackQuery, state: FSMContext):
    k = callback.data.replace("newcat_","")
    if k not in CATEGORIES: return await callback.answer("Нет")
    await state.update_data(category=k)
    await callback.message.answer(f"Категория: {CATEGORIES[k]}\n\nНазвание блюда:")
    await state.set_state(AddItem.waiting_for_name); await callback.answer()

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
    try: p = float(message.text.replace(',','.'))
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
    else: await message.answer("Ошибка.")
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
            stop = "🚫" if i[7]==1 else "✅"
            kb.append([InlineKeyboardButton(text=f"{stop} {i[2]} — {i[4]}с", callback_data=f"iteminfo_{i[0]}")])
        await callback.message.answer(f"<b>{CATEGORIES.get(ck,ck)}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("iteminfo_"))
async def item_info(callback: CallbackQuery):
    iid = int(callback.data.split("_")[1]); i = get_menu_item(iid)
    if not i: return await callback.answer("Нет")
    kb = [
        [InlineKeyboardButton(text="✏️ Изменить цену", callback_data=f"editprice_{iid}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_item_{iid}")],
        [InlineKeyboardButton(text="🚫 В стоп-лист" if i[7]==0 else "✅ Из стоп-листа", callback_data=f"stop_{iid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="my_items_back")],
    ]
    await callback.message.answer(f"<b>{i[2]}</b>\n{i[3]}\n💰 {i[4]} сомони", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

class EditPrice(StatesGroup):
    waiting = State()

@router.callback_query(F.data.startswith("editprice_"))
async def edit_price(callback: CallbackQuery, state: FSMContext):
    iid = int(callback.data.split("_")[1])
    await state.update_data(item_id=iid)
    await callback.message.answer("Введите новую цену (число):")
    await state.set_state(EditPrice.waiting); await callback.answer()

@router.message(EditPrice.waiting)
async def save_price(message: Message, state: FSMContext):
    try: np = float(message.text.replace(',','.'))
    except: return await message.answer("Число!")
    d = await state.get_data(); update_price(d['item_id'], np)
    await message.answer(f"✅ Цена обновлена: {np} сомони"); await state.clear()

@router.callback_query(F.data == "my_items_back")
async def mi_back(callback: CallbackQuery):
    await callback.message.delete(); await show_my_items(callback)

@router.callback_query(F.data.startswith("del_item_"))
async def delete_item(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    iid = int(callback.data.split("_")[2]); delete_menu_item(iid)
    await callback.message.answer("🗑 Удалено."); await callback.answer()

@router.callback_query(F.data.startswith("stop_"))
async def stop_item(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    iid = int(callback.data.split("_")[1]); toggle_stoplist(iid)
    await callback.message.answer("✅ Изменено."); await callback.answer()

@router.callback_query(F.data == "my_orders")
async def show_orders(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    orders = get_orders_by_restaurant(r[0])
    if not orders: return await callback.message.answer("Заказов нет.")
    for o in orders[:10]:
        text = f"<b>Заказ #{o[0]}</b> — {STATUSES.get(o[12],o[12])}\n👤 {o[3]}\n📞 {o[4]}\n🏠 {o[5]}\n🚚 {'Доставка' if o[9]=='delivery' else 'Самовывоз'}\n🍽 {o[6]}\n💰 {o[7]} сомони"
        await callback.message.answer(text, reply_markup=order_status_keyboard(o[0], o[12]))
    await callback.answer()

@router.callback_query(F.data.startswith("setstat_"))
async def set_status(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    parts = callback.data.split("_"); oid = int(parts[1]); ns = parts[2]
    update_order_status(oid, ns)
    await callback.message.edit_text(callback.message.text + f"\n\n➡️ Статус: {STATUSES.get(ns,ns)}", reply_markup=order_status_keyboard(oid, ns))
    o = get_order(oid)
    if o and o[2]:
        try:
            if ns == 'delivered':
                await bot.send_message(o[2], f"✅ Заказ #{oid} доставлен!\n\nОставьте отзыв:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"rev_start_{oid}_{o[1]}")]]))
            else: await bot.send_message(o[2], f"📢 Заказ #{oid}: {STATUSES.get(ns,ns)}")
        except: pass
    await callback.answer("OK")

@router.callback_query(F.data == "analytics")
async def analytics(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    a = get_analytics(r[0], 30)
    text = f"📊 <b>Аналитика за 30 дней</b>\n\n🛒 Заказов: <b>{a['total_orders']}</b>\n💰 Выручка: <b>{a['revenue']:.0f} сомони</b>\n✅ Доставлено: {a['delivered']}\n💵 Оплачено: {a['delivered_rev']:.0f} сомони\n\n<b>По статусам:</b>\n"
    for st, cnt in a['statuses'].items(): text += f"{STATUSES.get(st,st)}: {cnt}\n"
    if a['top_items']:
        text += "\n<b>🔥 Топ блюд:</b>\n"
        for name, cnt in a['top_items']: text += f"• {name} — {cnt}\n"
    await callback.message.answer(text); await callback.answer()

@router.callback_query(F.data == "clients")
async def show_clients(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    cl = get_all_clients(r[0])
    text = f"👥 <b>Клиенты ({len(cl)}):</b>\n\n"
    for c in cl[:50]: text += f"• {c[1] or 'Аноним'} — {c[2] or '—'}\n"
    if not cl: text += "Пока нет клиентов."
    await callback.message.answer(text); await callback.answer()

class Broadcast(StatesGroup):
    waiting_for_text = State()

@router.callback_query(F.data == "broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await callback.message.answer("📢 Напишите текст рассылки:")
    await state.set_state(Broadcast.waiting_for_text); await callback.answer()

@router.message(Broadcast.waiting_for_text)
async def broadcast_send(message: Message, state: FSMContext):
    r = get_restaurant_by_owner(message.from_user.id)
    if not r: await state.clear(); return
    clients = get_all_restaurants_clients(r[0]); sent = 0
    for cid in clients:
        try:
            await bot.send_message(cid, f"📢 <b>{r[1]}</b>\n\n{message.text}"); sent += 1
        except: pass
    await message.answer(f"✅ Отправлено {sent} из {len(clients)}"); await state.clear()

@router.callback_query(F.data == "my_promos")
async def my_promos(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    promos = get_promos(r[0]); text = "🎁 <b>Промокоды</b>\n\n"
    kb = [[InlineKeyboardButton(text="➕ Создать", callback_data="new_promo")]]
    if promos:
        for p in promos:
            text += f"<code>{p[2]}</code> — {p[3]}% ({p[4]}/{p[5]})\n"
            kb.append([InlineKeyboardButton(text=f"❌ {p[2]}", callback_data=f"delpromo_{p[0]}")])
    else: text += "Пока нет промокодов."
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)); await callback.answer()

class AddPromo(StatesGroup):
    waiting_for_code = State()
    waiting_for_discount = State()
    waiting_for_uses = State()

@router.callback_query(F.data == "new_promo")
async def new_promo(callback: CallbackQuery, state: FSMContext):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await callback.message.answer("Код промокода (например SALE10) или '-' :")
    await state.set_state(AddPromo.waiting_for_code); await callback.answer()

@router.message(AddPromo.waiting_for_code)
async def promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper() if message.text.strip() != '-' else ''.join(random.choices(string.ascii_uppercase+string.digits, k=6))
    await state.update_data(code=code)
    await message.answer(f"Код: <code>{code}</code>\n\nСкидка % (1-90):")
    await state.set_state(AddPromo.waiting_for_discount)

@router.message(AddPromo.waiting_for_discount)
async def promo_disc(message: Message, state: FSMContext):
    try: d = int(message.text)
    except: return await message.answer("Число!")
    if d < 1 or d > 90: return await message.answer("1-90")
    await state.update_data(discount=d)
    await message.answer("Максимум использований:")
    await state.set_state(AddPromo.waiting_for_uses)

@router.message(AddPromo.waiting_for_uses)
async def promo_uses(message: Message, state: FSMContext):
    try: u = int(message.text)
    except: return await message.answer("Число!")
    d = await state.get_data()
    r = get_restaurant_by_owner(message.from_user.id)
    if r and create_promo(r[0], d['code'], d['discount'], u):
        await message.answer(f"✅ Промокод <code>{d['code']}</code> на {d['discount']}%")
    else: await message.answer("❌ Такой код уже есть.")
    await state.clear()

@router.callback_query(F.data.startswith("delpromo_"))
async def del_promo(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    delete_promo(int(callback.data.split("_")[1]))
    await callback.answer("Удалён"); await my_promos(callback)

@router.callback_query(F.data.startswith("reviews_"))
async def show_reviews(callback: CallbackQuery):
    rid = int(callback.data.split("_")[1]); r = get_restaurant_by_id(rid)
    if not r: return await callback.answer("Нет", show_alert=True)
    avg, cnt = get_avg_rating(rid); revs = get_reviews(rid, 10)
    text = f"⭐ <b>Отзывы «{r[1]}»</b>\n\nСредняя: <b>{avg}/5</b> ({cnt})\n\n"
    for rv in revs: text += f"{'⭐'*rv[1]} {rv[0]}\n{rv[2] or ''}\n📅 {rv[3]}\n\n"
    if not revs: text += "Отзывов пока нет."
    await callback.message.answer(text); await callback.answer()

class AddReview(StatesGroup):
    waiting_for_rating = State()
    waiting_for_comment = State()

@router.callback_query(F.data.startswith("rev_start_"))
async def rev_start(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    await state.update_data(order_id=int(parts[2]), rest_id=int(parts[3]))
    kb = [[InlineKeyboardButton(text=f"{'⭐'*i} {i}", callback_data=f"rate_{i}")] for i in range(5,0,-1)]
    await callback.message.answer("Оцените заказ:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(AddReview.waiting_for_rating); await callback.answer()

@router.callback_query(F.data.startswith("rate_"), AddReview.waiting_for_rating)
async def rev_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)
    await callback.message.answer(f"{'⭐'*rating}\n\nКомментарий (или '-'):")
    await state.set_state(AddReview.waiting_for_comment); await callback.answer()

@router.message(AddReview.waiting_for_comment)
async def rev_comment(message: Message, state: FSMContext):
    d = await state.get_data()
    cm = "" if message.text.strip() == '-' else message.text
    add_review(d['rest_id'], message.from_user.id, message.from_user.full_name, d['rating'], cm)
    await message.answer("✅ Спасибо за отзыв!"); await state.clear()

class SearchItem(StatesGroup):
    waiting = State()

@router.callback_query(F.data.startswith("search_"))
async def search_start(callback: CallbackQuery, state: FSMContext):
    rid = int(callback.data.split("_")[1])
    await state.update_data(rest_id=rid)
    await callback.message.answer("🔍 Введите название блюда:")
    await state.set_state(SearchItem.waiting); await callback.answer()

@router.message(SearchItem.waiting)
async def search_do(message: Message, state: FSMContext):
    d = await state.get_data(); rid = d.get('rest_id')
    r = get_restaurant_by_id(rid)
    if not r: await state.clear(); return
    items = search_menu(rid, message.text)
    if not items: return await message.answer("❌ Ничего не найдено. Попробуйте ещё:")
    dk = r[9] if r[9] and r[9] in DESIGNS else 'classic'; dd = DESIGNS[dk]
    kb = [[InlineKeyboardButton(text=f"{dd['item']} {i[2]} — {i[4]} {dd['price']}", callback_data=f"item_{i[0]}")] for i in items]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_rest_{rid}")])
    await message.answer(f"🔍 Найдено {len(items)}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.clear()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("rest_"):
        try: rid = int(args[1].replace("rest_",""))
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
    if r[14]: info += f"\n🗺 <a href='{r[14]}'>Открыть на карте</a>\n"
    avg, cnt = get_avg_rating(r[0])
    if cnt: info += f"\n⭐ {avg}/5 ({cnt})\n"
    info += "\nВыберите категорию:"
    cats = set(i[5] or 'other' for i in items)
    cats_list = [(k, CATEGORIES[k]) for k in CATEGORIES if k in cats]
    kb = client_categories_keyboard(r[0], cats_list)
    banner = r[16] if len(r) > 16 else None
    if banner:
        try:
            await msg.answer_photo(banner, caption=info, reply_markup=kb); return
        except: pass
    await msg.answer(info, reply_markup=kb)

@router.callback_query(F.data.startswith("show_menu_"))
async def show_menu_cb(callback: CallbackQuery):
    rid = int(callback.data.split("_")[2]); r = get_restaurant_by_id(rid)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    await show_rest_to_client(callback.message, r); await callback.answer()

@router.callback_query(F.data.startswith("viewcat_"))
async def view_cat(callback: CallbackQuery):
    parts = callback.data.split("_"); rid = int(parts[1]); ck = parts[2]
    r = get_restaurant_by_id(rid)
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    items = get_menu_items(rid, ck)
    if not items: return await callback.answer("Пусто", show_alert=True)
    dk = r[9] if r[9] and r[9] in DESIGNS else 'classic'
    d = DESIGNS[dk]
    text = f"{d['header']}\n{d['title']} — {CATEGORIES[ck]}\n{d['footer']}"
    kb = []
    for i in items:
        kb.append([InlineKeyboardButton(text=f"{d['item']} {i[2]} — {i[4]} {d['price']}", callback_data=f"item_{i[0]}")])
    kb.append([InlineKeyboardButton(text="🛒 Корзина", callback_data=f"show_cart_{rid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_rest_{rid}")])
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)); await callback.answer()

@router.callback_query(F.data.startswith("back_to_rest_"))
async def back_rest(callback: CallbackQuery):
    rid = int(callback.data.split("_")[3]); r = get_restaurant_by_id(rid)
    if not r: return await callback.answer("Нет", show_alert=True)
    await show_rest_to_client(callback.message, r); await callback.answer()

@router.callback_query(F.data.startswith("item_"))
async def show_item(callback: CallbackQuery):
    iid = int(callback.data.split("_")[1]); i = get_menu_item(iid)
    if not i: return await callback.answer("Нет", show_alert=True)
    r = get_restaurant_by_id(i[1])
    if not r or not is_subscription_active(r): return await callback.answer("Нет", show_alert=True)
    cap = f"<b>{i[2]}</b>\n"
    if i[3] and i[3] != '-': cap += f"\n{i[3]}\n"
    cap += f"\n💰 <b>{i[4]} сомони</b>"
    kb = [[InlineKeyboardButton(text="➕ В корзину", callback_data=f"addcart_{iid}")],
          [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"viewcat_{i[1]}_{i[5] or 'other'}")]]
    if i[6]: await callback.message.answer_photo(i[6], caption=cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else: await callback.message.answer(cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("addcart_"))
async def addcart(callback: CallbackQuery):
    iid = int(callback.data.split("_")[1]); i = get_menu_item(iid)
    if not i: return await callback.answer("Нет", show_alert=True)
    add_to_cart(callback.from_user.id, i[1], iid)
    await callback.answer("✅ Добавлено!", show_alert=True)

@router.callback_query(F.data.startswith("show_cart_"))
async def show_cart_cb(callback: CallbackQuery):
    rid = int(callback.data.split("_")[2]); r = get_restaurant_by_id(rid)
    if not r: return await callback.answer("Нет", show_alert=True)
    items = get_cart(callback.from_user.id, rid)
    if not items: return await callback.answer("Корзина пуста", show_alert=True)
    total = 0; text = "🛒 <b>Корзина:</b>\n\n"; kb = []
    for c in items:
        cid_, iid, qty, name, price = c; st = price*qty; total += st
        text += f"• {name} × {qty} = {st} сомони\n"
        kb.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"rmcart_{cid_}_{rid}")])
    text += f"\n💰 <b>Итого: {total} сомони</b>"
    if r[13] and total < r[13]: text += f"\n⚠️ Мин. заказ: {r[13]}"
    else: kb.append([InlineKeyboardButton(text="✅ Оформить", callback_data=f"checkout_{rid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_rest_{rid}")])
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)); await callback.answer()

@router.callback_query(F.data.startswith("rmcart_"))
async def rmcart(callback: CallbackQuery):
    parts = callback.data.split("_"); remove_cart(int(parts[1]))
    await callback.message.delete(); rid = int(parts[2])
    callback.data = f"show_cart_{rid}"; await show_cart_cb(callback)

class Checkout(StatesGroup):
    waiting_for_type = State()
    waiting_for_promo = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_address = State()

@router.callback_query(F.data.startswith("checkout_"))
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    rid = int(callback.data.split("_")[1]); await state.update_data(rest_id=rid)
    kb = [[InlineKeyboardButton(text="🚚 Доставка", callback_data="dtype_delivery")],
          [InlineKeyboardButton(text="🏃 Самовывоз", callback_data="dtype_pickup")]]
    await callback.message.answer("Как получите заказ?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(Checkout.waiting_for_type); await callback.answer()

@router.callback_query(F.data.startswith("dtype_"), Checkout.waiting_for_type)
async def choose_dtype(callback: CallbackQuery, state: FSMContext):
    dt = callback.data.replace("dtype_",""); await state.update_data(dtype=dt)
    await callback.message.answer("🎁 Промокод? Введите или '-' :")
    await state.set_state(Checkout.waiting_for_promo); await callback.answer()

@router.message(Checkout.waiting_for_promo)
async def checkout_promo(message: Message, state: FSMContext):
    code = message.text.strip()
    if code == '-': await state.update_data(promo=None, discount=0)
    else:
        p = get_promo(code)
        if not p: return await message.answer("❌ Не найден. Ещё раз или '-' :")
        await state.update_data(promo=p[2], discount=p[3])
        await message.answer(f"✅ Промокод -{p[3]}%")
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
    if d.get('dtype') == 'pickup': await finalize_order(message, state)
    else:
        await message.answer("🏠 Адрес доставки:")
        await state.set_state(Checkout.waiting_for_address)

@router.message(Checkout.waiting_for_address)
async def checkout_addr(message: Message, state: FSMContext):
    await state.update_data(client_address=message.text)
    await finalize_order(message, state)

async def finalize_order(message: Message, state: FSMContext):
    d = await state.get_data(); rid = d['rest_id']
    r = get_restaurant_by_id(rid)
    if not r or not is_subscription_active(r):
        await message.answer("Ресторан недоступен."); return await state.clear()
    cart_items = get_cart(message.from_user.id, rid)
    if not cart_items:
        await message.answer("Корзина пуста."); return await state.clear()
    subtotal = sum(c[4]*c[2] for c in cart_items)
    if r[13] and subtotal < r[13]:
        await message.answer(f"⚠️ Мин. сумма: {r[13]} сомони"); return await state.clear()
    items_text = ""
    for c in cart_items:
        _, _, qty, name, price = c
        items_text += f"{name} × {qty} = {price*qty} сомони\n"
    discount = subtotal * d['discount'] / 100 if d.get('discount') else 0
    delivery = r[12] if (d['dtype'] == 'delivery' and r[12]) else 0
    total = subtotal - discount + delivery
    addr = d.get('client_address', 'Самовывоз')
    oid = add_order(rid, message.from_user.id, d['client_name'], d['client_phone'], addr, items_text, total, subtotal, d['dtype'], d.get('promo'), discount)
    if d.get('promo'):
        p = get_promo(d['promo'])
        if p: use_promo(p[0])
    clear_cart(message.from_user.id, rid)
    if r[4]:
        try:
            promo_line = f"🎁 Промокод: {d['promo']} (-{discount:.0f})\n" if d.get('promo') else ""
            del_line = f"🚚 Доставка: {delivery} сомони\n" if delivery else ""
            await bot.send_message(r[4], f"🔔 <b>НОВЫЙ ЗАКАЗ #{oid}!</b>\n\n👤 {d['client_name']}\n📞 {d['client_phone']}\n{'🏠 '+addr if d['dtype']=='delivery' else '🏃 Самовывоз'}\n\n🍽 {items_text}\n{promo_line}{del_line}💰 <b>Итого: {total:.0f} сомони</b>")
        except: pass
    await message.answer(f"✅ <b>Заказ #{oid} оформлен!</b>\n\n💰 Сумма: {total:.0f} сомони")
    await state.clear()

@router.message(Command("myorders"))
async def my_orders_client(message: Message):
    orders = get_client_orders(message.from_user.id)
    if not orders: return await message.answer("У вас нет заказов.")
    text = "📋 <b>Ваши заказы:</b>\n\n"
    for o in orders[:10]:
        r = get_restaurant_by_id(o[1])
        text += f"#{o[0]} — {r[1] if r else '?'}\n{STATUSES.get(o[12],o[12])} | {o[7]} сомони\n\n"
    await message.answer(text)

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
