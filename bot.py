import asyncio
import logging
import os
from datetime import datetime, timedelta

import psycopg2
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# === НАСТРОЙКИ ===
BOT_TOKEN = "8890056509:AAFvSsiaD0pZPHGRAa3iWRwfNdae3II7ttc"
ADMIN_ID = 7758384445
WEBHOOK_URL = "https://menu-master-bot.onrender.com/webhook"
PAYMENT_PHONE = "993337070"
PRICE_BASIC = 50        # без дизайна
PRICE_DESIGN = 60       # с дизайном
SUBSCRIPTION_DAYS = 30

# === ДИЗАЙНЫ (темы для клиентского меню) ===
DESIGNS = {
    "classic": {
        "name": "📋 Классик",
        "desc": "Строгий деловой стиль",
        "header": "━━━━━━━━━━━━━━━",
        "item": "▫️",
        "title": "🍽 Меню",
        "price": "сомони",
        "footer": "━━━━━━━━━━━━━━━",
    },
    "modern": {
        "name": "⚡ Модерн",
        "desc": "Современный стиль с эмодзи",
        "header": "🔥🔥🔥🔥🔥🔥🔥",
        "item": "⚡",
        "title": "🍔 МЕНЮ БУДУЩЕГО",
        "price": " TJS",
        "footer": "🔥🔥🔥🔥🔥🔥🔥",
    },
    "elegant": {
        "name": "✨ Элегант",
        "desc": "Роскошный премиум-стиль",
        "header": "✦ ─────────── ✦",
        "item": "✨",
        "title": "👑 Изысканное меню",
        "price": "сомони",
        "footer": "✦ ─────────── ✦",
    },
    "fun": {
        "name": "🎉 Весёлый",
        "desc": "Яркий и дружелюбный",
        "header": "🎉🎊🎈🎊🎉",
        "item": "🌟",
        "title": "😋 Что покушаем?",
        "price": "сом",
        "footer": "🎈🎊🎉🎊🎈",
    },
    "night": {
        "name": "🌙 Ночной",
        "desc": "Тёмный стиль для гурманов",
        "header": "🌙 ─ ─ ─ ─ ─ 🌙",
        "item": "🍷",
        "title": "🌙 Ночное меню",
        "price": "сомони",
        "footer": "🌙 ─ ─ ─ ─ ─ 🌙",
    },
}

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# === БАЗА ДАННЫХ ===
DATABASE_URL = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS rest (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    owner_id BIGINT,
    subscribed INTEGER DEFAULT 0,
    blocked INTEGER DEFAULT 0,
    subscribe_until TEXT,
    design TEXT DEFAULT 'none',
    active_design TEXT DEFAULT 'classic'
)
''')

# На случай, если таблица уже была — добавим колонки
for col, coltype in [("design", "TEXT DEFAULT 'none'"), ("active_design", "TEXT DEFAULT 'classic'")]:
    try:
        cursor.execute(f"ALTER TABLE rest ADD COLUMN IF NOT EXISTS {col} {coltype}")
        conn.commit()
    except:
        conn.rollback()

cursor.execute('''
CREATE TABLE IF NOT EXISTS menu (
    id SERIAL PRIMARY KEY,
    rest_id INTEGER,
    name TEXT,
    description TEXT,
    price REAL,
    FOREIGN KEY(rest_id) REFERENCES rest(id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    rest_id INTEGER,
    client_name TEXT,
    client_phone TEXT,
    client_address TEXT,
    items_text TEXT,
    total REAL,
    status TEXT DEFAULT 'new',
    created_at TEXT,
    FOREIGN KEY(rest_id) REFERENCES rest(id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    rest_id INTEGER,
    owner_id BIGINT,
    amount INTEGER,
    receipt_file_id TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    FOREIGN KEY(rest_id) REFERENCES rest(id)
)
''')
conn.commit()

# === ФУНКЦИИ ===
def get_restaurant_by_owner(owner_id):
    cursor.execute("SELECT * FROM rest WHERE owner_id=%s", (owner_id,))
    return cursor.fetchone()

def get_restaurant_by_id(rest_id):
    cursor.execute("SELECT * FROM rest WHERE id=%s", (rest_id,))
    return cursor.fetchone()

def get_active_restaurants():
    cursor.execute("SELECT * FROM rest WHERE blocked=0 AND subscribed=1")
    return cursor.fetchall()

def get_menu_items(rest_id):
    cursor.execute("SELECT * FROM menu WHERE rest_id=%s", (rest_id,))
    return cursor.fetchall()

def add_menu_item(rest_id, name, description, price):
    cursor.execute("INSERT INTO menu (rest_id, name, description, price) VALUES (%s,%s,%s,%s)",
                   (rest_id, name, description, price))
    conn.commit()

def delete_menu_item(item_id):
    cursor.execute("DELETE FROM menu WHERE id=%s", (item_id,))
    conn.commit()

def add_order(rest_id, client_name, client_phone, client_address, items_text, total):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO orders (rest_id, client_name, client_phone, client_address, items_text, total, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                   (rest_id, client_name, client_phone, client_address, items_text, total, created_at))
    conn.commit()
    return cursor.lastrowid

def get_orders_by_restaurant(rest_id, status='new'):
    cursor.execute("SELECT * FROM orders WHERE rest_id=%s AND status=%s", (rest_id, status))
    return cursor.fetchall()

def update_order_status(order_id, new_status):
    cursor.execute("UPDATE orders SET status=%s WHERE id=%s", (new_status, order_id))
    conn.commit()

def is_subscription_active(r):
    if not r:
        return False
    if r[6] == 1:
        return False
    if r[5] != 1:
        return False
    if not r[7]:
        return False
    try:
        return datetime.strptime(r[7], "%Y-%m-%d") >= datetime.now()
    except:
        return False

def activate_subscription(rest_id, days=30):
    until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("UPDATE rest SET subscribed=1, subscribe_until=%s WHERE id=%s", (until, rest_id))
    conn.commit()
    return until

def deactivate_subscription(rest_id):
    cursor.execute("UPDATE rest SET subscribed=0 WHERE id=%s", (rest_id,))
    conn.commit()

def set_design(rest_id, design_key):
    cursor.execute("UPDATE rest SET design=%s, active_design=%s WHERE id=%s",
                   (design_key, design_key, rest_id))
    conn.commit()

def clear_design(rest_id):
    cursor.execute("UPDATE rest SET design='none' WHERE id=%s", (rest_id,))
    conn.commit()

def get_price(r):
    """Если есть дизайн — 60, иначе 50"""
    return PRICE_DESIGN if r and r[8] and r[8] != 'none' else PRICE_BASIC

def add_payment(rest_id, owner_id, amount, receipt_file_id):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO payments (rest_id, owner_id, amount, receipt_file_id, created_at) VALUES (%s,%s,%s,%s,%s)",
                   (rest_id, owner_id, amount, receipt_file_id, created_at))
    conn.commit()
    return cursor.lastrowid

def get_payment_by_id(pid):
    cursor.execute("SELECT * FROM payments WHERE id=%s", (pid,))
    return cursor.fetchone()

def update_payment_status(pid, status):
    cursor.execute("UPDATE payments SET status=%s WHERE id=%s", (status, pid))
    conn.commit()

def get_pending_payments():
    cursor.execute("SELECT * FROM payments WHERE status='pending'")
    return cursor.fetchall()

# === КЛАВИАТУРЫ ===
def cabinet_keyboard(has_design):
    kb = [
        [InlineKeyboardButton(text="📝 Добавить блюдо", callback_data="add_item")],
        [InlineKeyboardButton(text="🍽 Мои блюда", callback_data="my_items")],
        [InlineKeyboardButton(text="🛒 Заказы", callback_data="my_orders")],
    ]
    if has_design:
        kb.append([InlineKeyboardButton(text="🎨 Сменить дизайн", callback_data="choose_design")])
        kb.append([InlineKeyboardButton(text="🚫 Убрать дизайн", callback_data="remove_design")])
    else:
        kb.append([InlineKeyboardButton(text="🎨 Выбрать дизайн (+10 сомони)", callback_data="choose_design")])
    kb.append([InlineKeyboardButton(text="💳 Оплатить подписку", callback_data="pay_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def design_choice_keyboard():
    kb = []
    for key, d in DESIGNS.items():
        kb.append([InlineKeyboardButton(text=f"{d['name']} — {d['desc']}", callback_data=f"set_design_{key}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def payment_confirm_keyboard(pid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_pay_{pid}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_pay_{pid}")],
    ])

# === ОТМЕНА ===
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.")

# === АДМИН ===
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    cursor.execute("SELECT * FROM rest")
    restaurants = cursor.fetchall()
    if not restaurants:
        await message.answer("Ресторанов нет.")
        return
    text = "📋 <b>Список ресторанов:</b>\n\n"
    for r in restaurants:
        active = "✅ Активна" if is_subscription_active(r) else "❌ Не активна"
        block = "🚫 Заблокирован" if r[6] == 1 else "🟢 ОК"
        design = DESIGNS.get(r[8], {}).get('name', '—') if r[8] and r[8] != 'none' else '—'
        text += (f"<b>ID:</b> {r[0]}\n"
                 f"<b>Название:</b> {r[1]}\n"
                 f"<b>Владелец ID:</b> {r[4]}\n"
                 f"<b>Подписка:</b> {active} до {r[7] or '—'}\n"
                 f"<b>Дизайн:</b> {design}\n"
                 f"<b>Цена:</b> {get_price(r)} сомони\n"
                 f"<b>Статус:</b> {block}\n\n")
    await message.answer(text)

class AddRest(StatesGroup):
    waiting_for_owner = State()

@router.message(Command("addrest"))
async def cmd_addrest(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer("Формат: /addrest Название | Адрес | Телефон")
        return
    await state.update_data(name=args[1], address=args[2], phone=args[3])
    await message.answer("Перешли сообщение от владельца ресторана (или введи его Telegram ID):")
    await state.set_state(AddRest.waiting_for_owner)

@router.message(AddRest.waiting_for_owner)
async def process_owner(message: Message, state: FSMContext):
    if message.forward_from:
        owner_id = message.forward_from.id
    elif message.forward_from_chat:
        owner_id = message.forward_from_chat.id
    else:
        try:
            owner_id = int(message.text.strip())
        except ValueError:
            await message.answer("Некорректный ID. Попробуй ещё раз или /cancel")
            return
    data = await state.get_data()
    cursor.execute("INSERT INTO rest (name, address, phone, owner_id, subscribed, blocked) VALUES (%s,%s,%s,%s,%s,%s)",
                   (data['name'], data['address'], data['phone'], owner_id, 0, 0))
    conn.commit()
    await message.answer(f"✅ Ресторан добавлен! Владелец ID: {owner_id}\n\n"
                         f"⚠️ Подписка не активна. Активируй: /subscribe ID 30")
    try:
        await bot.send_message(owner_id,
            f"🎉 Ваш ресторан «{data['name']}» добавлен!\n\n"
            f"💰 Тарифы:\n"
            f"• Без дизайна — <b>{PRICE_BASIC} сомони/мес</b>\n"
            f"• С дизайном — <b>{PRICE_DESIGN} сомони/мес</b>\n\n"
            f"📱 Оплата на номер: <code>{PAYMENT_PHONE}</code>\n\n"
            f"После оплаты отправьте <b>фото чека</b> сюда.")
    except:
        pass
    await state.clear()

@router.message(Command("block"))
async def cmd_block(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Формат: /block ID")
        return
    cursor.execute("UPDATE rest SET blocked=1 WHERE id=%s", (args[1],))
    conn.commit()
    await message.answer(f"🚫 Ресторан {args[1]} заблокирован.")

@router.message(Command("unblock"))
async def cmd_unblock(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Формат: /unblock ID")
        return
    cursor.execute("UPDATE rest SET blocked=0 WHERE id=%s", (args[1],))
    conn.commit()
    await message.answer(f"🟢 Ресторан {args[1]} разблокирован.")

@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Формат: /subscribe ID дней")
        return
    rest_id = int(args[1])
    days = int(args[2])
    until = activate_subscription(rest_id, days)
    await message.answer(f"✅ Подписка ресторана {rest_id} активирована до {until}")
    r = get_restaurant_by_id(rest_id)
    if r and r[4]:
        try:
            await bot.send_message(r[4], f"✅ Ваша подписка активирована до {until}!")
        except:
            pass

@router.message(Command("pending"))
async def cmd_pending(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    payments = get_pending_payments()
    if not payments:
        await message.answer("Нет неподтверждённых платежей.")
        return
    for p in payments:
        r = get_restaurant_by_id(p[1])
        name = r[1] if r else "?"
        await message.answer_photo(
            p[4],
            caption=f"💳 <b>Платёж #{p[0]}</b>\n"
                    f"Ресторан: {name} (ID {p[1]})\n"
                    f"Сумма: {p[3]} сомони\n"
                    f"Дата: {p[6]}\n"
                    f"Статус: {p[5]}",
            reply_markup=payment_confirm_keyboard(p[0])
        )

# === ПОДТВЕРЖДЕНИЕ ПЛАТЕЖА ===
@router.callback_query(F.data.startswith("confirm_pay_"))
async def confirm_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    pid = int(callback.data.split("_")[2])
    p = get_payment_by_id(pid)
    if not p or p[5] != 'pending':
        await callback.answer("Уже обработан.", show_alert=True)
        return
    rest_id = p[1]
    until = activate_subscription(rest_id, SUBSCRIPTION_DAYS)
    update_payment_status(pid, 'approved')
    r = get_restaurant_by_id(rest_id)
    await callback.message.edit_caption(
        caption=callback.message.caption + f"\n\n✅ <b>ПОДТВЕРЖДЕНО</b> до {until}"
    )
    if r and r[4]:
        try:
            await bot.send_message(
                r[4],
                f"🎉 <b>Оплата подтверждена!</b>\n"
                f"✅ Кабинет активирован до <b>{until}</b>\n\n"
                f"Введите /mycabinet для работы."
            )
        except:
            pass
    await callback.answer("Подтверждено!")

@router.callback_query(F.data.startswith("reject_pay_"))
async def reject_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    pid = int(callback.data.split("_")[2])
    p = get_payment_by_id(pid)
    if not p or p[5] != 'pending':
        await callback.answer("Уже обработан.", show_alert=True)
        return
    update_payment_status(pid, 'rejected')
    r = get_restaurant_by_id(p[1])
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ <b>ОТКЛОНЕНО</b>")
    if r and r[4]:
        try:
            await bot.send_message(r[4], "❌ Ваш чек отклонён. Проверьте оплату и отправьте заново.")
        except:
            pass
    await callback.answer("Отклонено.")

# === КАБИНЕТ ===
@router.message(Command("mycabinet"))
async def cmd_mycabinet(message: Message, state: FSMContext):
    await state.clear()
    r = get_restaurant_by_owner(message.from_user.id)
    if not r:
        await message.answer("У вас нет ресторана.")
        return
    if r[6] == 1:
        await message.answer("🚫 Ваш ресторан заблокирован.")
        return
    if not is_subscription_active(r):
        await message.answer(
            f"⚠️ <b>Подписка не активна!</b>\n\n"
            f"💰 Тарифы:\n"
            f"• Без дизайна — <b>{PRICE_BASIC} сомони/мес</b>\n"
            f"• С дизайном — <b>{PRICE_DESIGN} сомони/мес</b>\n\n"
            f"📱 Оплата: <code>{PAYMENT_PHONE}</code>\n\n"
            f"Отправьте <b>фото чека</b> в этот чат."
        )
        return
    has_design = r[8] and r[8] != 'none'
    design_label = DESIGNS.get(r[8], {}).get('name', '—') if has_design else '❌ нет'
    await message.answer(
        f"👋 Кабинет ресторана «{r[1]}»\n"
        f"📅 Подписка до: {r[7]}\n"
        f"🎨 Дизайн: {design_label}\n"
        f"💵 Тариф: {get_price(r)} сомони\n\n"
        f"Выбери действие:",
        reply_markup=cabinet_keyboard(has_design)
    )

@router.callback_query(F.data == "back_to_cabinet")
async def back_to_cabinet(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r:
        await callback.answer("Ресторан не найден", show_alert=True)
        return
    has_design = r[8] and r[8] != 'none'
    design_label = DESIGNS.get(r[8], {}).get('name', '—') if has_design else '❌ нет'
    await callback.message.edit_text(
        f"👋 Кабинет ресторана «{r[1]}»\n"
        f"📅 Подписка до: {r[7]}\n"
        f"🎨 Дизайн: {design_label}\n"
        f"💵 Тариф: {get_price(r)} сомони\n\n"
        f"Выбери действие:",
        reply_markup=cabinet_keyboard(has_design)
    )
    await callback.answer()

# === ВЫБОР ДИЗАЙНА ===
@router.callback_query(F.data == "choose_design")
async def choose_design(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r):
        await callback.answer("Сначала активируйте подписку!", show_alert=True)
        return
    text = ("🎨 <b>Выберите дизайн меню</b>\n\n"
            "Каждый дизайн меняет вид меню для клиентов.\n"
            "💵 С дизайном подписка: <b>60 сомони/мес</b>\n"
            "💵 Без дизайна: <b>50 сомони/мес</b>\n\n"
            "Выберите стиль:")
    await callback.message.edit_text(text, reply_markup=design_choice_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("set_design_"))
async def set_design_handler(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r):
        await callback.answer("Сначала активируйте подписку!", show_alert=True)
        return
    key = callback.data.replace("set_design_", "")
    if key not in DESIGNS:
        await callback.answer("Неверный дизайн", show_alert=True)
        return
    set_design(r[0], key)
    d = DESIGNS[key]
    await callback.message.edit_text(
        f"✅ Дизайн установлен: <b>{d['name']}</b>\n\n"
        f"Теперь меню для ваших клиентов будет выглядеть в этом стиле.\n\n"
        f"⚠️ Не забудьте оплатить <b>{PRICE_DESIGN} сомони</b> "
        f"(включая 10 сомони за дизайн).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")]
        ])
    )
    await callback.answer("Дизайн установлен!")

@router.callback_query(F.data == "remove_design")
async def remove_design_handler(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r:
        await callback.answer("Ресторан не найден", show_alert=True)
        return
    clear_design(r[0])
    await callback.message.edit_text(
        "✅ Дизайн убран. Теперь тариф: <b>50 сомони/мес</b>.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cabinet")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "pay_subscription")
async def pay_subscription(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    price = get_price(r)
    await callback.message.answer(
        f"💳 <b>Оплата подписки</b>\n\n"
        f"Сумма: <b>{price} сомони</b>\n"
        f"Номер: <code>{PAYMENT_PHONE}</code>\n\n"
        f"После оплаты отправьте <b>фото чека</b> в этот чат."
    )
    await callback.answer()

# === ЧЕК ===
@router.message(F.photo)
async def handle_receipt(message: Message, state: FSMContext):
    r = get_restaurant_by_owner(message.from_user.id)
    if not r:
        return
    if r[6] == 1:
        await message.answer("🚫 Ваш ресторан заблокирован.")
        return
    if is_subscription_active(r):
        await message.answer("✅ У вас уже активна подписка. Чек не нужен.")
        return
    price = get_price(r)
    file_id = message.photo[-1].file_id
    pid = add_payment(r[0], message.from_user.id, price, file_id)
    try:
        await bot.send_photo(
            ADMIN_ID,
            file_id,
            caption=f"💳 <b>Новый чек на оплату!</b>\n\n"
                    f"Ресторан: <b>{r[1]}</b>\n"
                    f"ID: {r[0]}\n"
                    f"Владелец: {message.from_user.full_name} (@{message.from_user.username or '—'})\n"
                    f"Сумма: <b>{price} сомони</b>\n"
                    f"Дизайн: {'есть' if r[8] and r[8] != 'none' else 'нет'}\n"
                    f"Номер: {PAYMENT_PHONE}\n\n"
                    f"Подтвердите оплату.",
            reply_markup=payment_confirm_keyboard(pid)
        )
        await message.answer("📨 Чек отправлен администратору. Ожидайте подтверждения.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# === ДОБАВЛЕНИЕ БЛЮД ===
class AddItem(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()

@router.callback_query(F.data == "add_item")
async def start_add_item(callback: CallbackQuery, state: FSMContext):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r):
        await callback.answer("Сначала активируйте подписку!", show_alert=True)
        return
    await callback.message.answer("Введи название блюда:")
    await state.set_state(AddItem.waiting_for_name)
    await callback.answer()

@router.message(AddItem.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Теперь описание (или '-', если нет):")
    await state.set_state(AddItem.waiting_for_description)

@router.message(AddItem.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Цена (число, например 45):")
    await state.set_state(AddItem.waiting_for_price)

@router.message(AddItem.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("Нужно число. Попробуй ещё раз.")
        return
    data = await state.get_data()
    r = get_restaurant_by_owner(message.from_user.id)
    if r and is_subscription_active(r):
        add_menu_item(r[0], data['name'], data['description'], price)
        await message.answer(f"✅ Блюдо «{data['name']}» добавлено!")
    else:
        await message.answer("Подписка не активна.")
    await state.clear()

@router.callback_query(F.data == "my_items")
async def show_my_items(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r):
        await callback.answer("Сначала активируйте подписку!", show_alert=True)
        return
    items = get_menu_items(r[0])
    if not items:
        await callback.message.answer("У вас пока нет блюд.")
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for item in items:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"❌ {item[2]} — {item[4]} сомони", callback_data=f"del_item_{item[0]}")
        ])
    await callback.message.answer("Ваши блюда:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("del_item_"))
async def delete_item(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r):
        await callback.answer("Сначала активируйте подписку!", show_alert=True)
        return
    item_id = int(callback.data.split("_")[2])
    delete_menu_item(item_id)
    await callback.message.answer("🗑 Блюдо удалено.")
    await callback.answer()

@router.callback_query(F.data == "my_orders")
async def show_orders(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r):
        await callback.answer("Сначала активируйте подписку!", show_alert=True)
        return
    orders = get_orders_by_restaurant(r[0], 'new')
    if not orders:
        await callback.message.answer("Новых заказов нет.")
        await callback.answer()
        return
    for order in orders:
        text = (f"🛒 <b>Заказ #{order[0]}</b>\n"
                f"Клиент: {order[2]}\n"
                f"Телефон: {order[3]}\n"
                f"Адрес: {order[4]}\n"
                f"Товары: {order[5]}\n"
                f"Сумма: {order[6]} сомони\n"
                f"Время: {order[8]}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_order_{order[0]}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_order_{order[0]}")]
        ])
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("accept_order_"))
async def accept_order(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r):
        await callback.answer("Подписка не активна", show_alert=True)
        return
    oid = int(callback.data.split("_")[2])
    update_order_status(oid, 'accepted')
    await callback.message.answer(f"✅ Заказ #{oid} принят.")
    await callback.answer()

@router.callback_query(F.data.startswith("reject_order_"))
async def reject_order(callback: CallbackQuery):
    r = get_restaurant_by_owner(callback.from_user.id)
    if not r or not is_subscription_active(r):
        await callback.answer("Подписка не активна", show_alert=True)
        return
    oid = int(callback.data.split("_")[2])
    update_order_status(oid, 'rejected')
    await callback.message.answer(f"❌ Заказ #{oid} отклонён.")
    await callback.answer()

# === КЛИЕНТСКАЯ ЧАСТЬ ===
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    r = get_restaurant_by_owner(message.from_user.id)
    if r:
        if is_subscription_active(r):
            await message.answer("👋 Здравствуйте! Ваш кабинет: /mycabinet")
        else:
            await message.answer(
                f"⚠️ Подписка не активна.\n"
                f"💰 Оплата: {get_price(r)} сомони на номер {PAYMENT_PHONE}\n"
                f"Отправьте чек для активации."
            )
        return
    restaurants = get_active_restaurants()
    if not restaurants:
        await message.answer("Пока нет доступных ресторанов.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for rr in restaurants:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=rr[1], callback_data=f"show_menu_{rr[0]}")
        ])
    await message.answer("🍽 Выбери ресторан:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("show_menu_"))
async def show_menu(callback: CallbackQuery):
    rest_id = int(callback.data.split("_")[2])
    r = get_restaurant_by_id(rest_id)
    if not r or not is_subscription_active(r):
        await callback.message.answer("Этот ресторан недоступен.")
        await callback.answer()
        return
    items = get_menu_items(rest_id)
    if not items:
        await callback.message.answer("Меню пока пусто.")
        await callback.answer()
        return
    # Применяем дизайн
    design_key = r[9] if r[9] and r[9] in DESIGNS else 'classic'
    d = DESIGNS[design_key]
    header = d['header']
    title = d['title']
    item_emoji = d['item']
    price_suffix = d['price']
    footer = d['footer']
    # Формируем красивое превью + список кнопок
    text = (f"{header}\n"
            f"🍴 <b>{r[1]}</b>\n"
            f"{title}\n"
            f"{footer}\n"
            f"Выберите блюдо:")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for item in items:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{item_emoji} {item[2]} — {item[4]} {price_suffix}",
                callback_data=f"order_item_{item[0]}"
            )
        ])
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

class OrderItem(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_address = State()

@router.callback_query(F.data.startswith("order_item_"))
async def start_order_item(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split("_")[2])
    await state.update_data(item_id=item_id)
    await callback.message.answer("Введите ваше имя:")
    await state.set_state(OrderItem.waiting_for_name)
    await callback.answer()

@router.message(OrderItem.waiting_for_name)
async def process_order_name(message: Message, state: FSMContext):
    await state.update_data(client_name=message.text)
    await message.answer("Теперь телефон:")
    await state.set_state(OrderItem.waiting_for_phone)

@router.message(OrderItem.waiting_for_phone)
async def process_order_phone(message: Message, state: FSMContext):
    await state.update_data(client_phone=message.text)
    await message.answer("Адрес доставки:")
    await state.set_state(OrderItem.waiting_for_address)

@router.message(OrderItem.waiting_for_address)
async def process_order_address(message: Message, state: FSMContext):
    data = await state.get_data()
    item_id = data['item_id']
    cursor.execute("SELECT * FROM menu WHERE id=%s", (item_id,))
    item = cursor.fetchone()
    if not item:
        await message.answer("Блюдо не найдено.")
        await state.clear()
        return
    rest_id = item[1]
    r = get_restaurant_by_id(rest_id)
    if not r or not is_subscription_active(r):
        await message.answer("Ресторан недоступен.")
        await state.clear()
        return
    items_text = f"{item[2]} (1 шт.)"
    total = item[4]
    order_id = add_order(rest_id, data['client_name'], data['client_phone'], message.text, items_text, total)
    # УВЕДОМЛЕНИЕ ВЛАДЕЛЬЦУ
    if r[4]:
        try:
            await bot.send_message(
                r[4],
                f"🔔 <b>НОВЫЙ ЗАКАЗ #{order_id}!</b>\n\n"
                f"👤 Клиент: {data['client_name']}\n"
                f"📞 Телефон: {data['client_phone']}\n"
                f"🏠 Адрес: {message.text}\n"
                f"🍽 Товары: {items_text}\n"
                f"💰 Сумма: <b>{total} сомони</b>\n\n"
                f"Откройте кабинет → Заказы для принятия."
            )
        except:
            pass
    await message.answer(
        f"✅ <b>Заказ #{order_id} отправлен!</b>\n"
        f"Ресторан свяжется с вами."
    )
    await state.clear()

# === ЗАПУСК ===
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
