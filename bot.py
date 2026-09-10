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

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# === БАЗА ДАННЫХ (PostgreSQL) ===
DATABASE_URL = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS rest (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    owner_id INTEGER,
    subscribed INTEGER DEFAULT 0,
    blocked INTEGER DEFAULT 0,
    subscribe_until TEXT
)
''')

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

# === КЛАВИАТУРЫ ===
def cabinet_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Добавить блюдо", callback_data="add_item")],
        [InlineKeyboardButton(text="🍽 Мои блюда", callback_data="my_items")],
        [InlineKeyboardButton(text="🛒 Заказы", callback_data="my_orders")],
    ])

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
    text = "Список ресторанов:\n\n"
    for r in restaurants:
        status = "✅" if r[5] == 1 else "❌"
        block = "🚫" if r[6] == 1 else "🟢"
        text += f"ID: {r[0]}\nНазвание: {r[1]}\nВладелец ID: {r[4]}\nПодписка: {status}\nБлок: {block}\n\n"
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
    await message.answer("Теперь перешли сообщение от владельца ресторана (или введи его Telegram ID):")
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
            await message.answer("Некорректный ID. Попробуй ещё раз.")
            return
    data = await state.get_data()
    cursor.execute("INSERT INTO rest (name, address, phone, owner_id, subscribed, blocked) VALUES (%s,%s,%s,%s,%s,%s)",
                   (data['name'], data['address'], data['phone'], owner_id, 1, 0))
    conn.commit()
    await message.answer(f"Ресторан добавлен! Владелец ID: {owner_id}")
    await state.clear()

@router.message(Command("block"))
async def cmd_block(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажи ID ресторана: /block ID")
        return
    rest_id = int(args[1])
    cursor.execute("UPDATE rest SET blocked=1 WHERE id=%s", (rest_id,))
    conn.commit()
    await message.answer(f"Ресторан {rest_id} заблокирован.")

@router.message(Command("unblock"))
async def cmd_unblock(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажи ID ресторана: /unblock ID")
        return
    rest_id = int(args[1])
    cursor.execute("UPDATE rest SET blocked=0 WHERE id=%s", (rest_id,))
    conn.commit()
    await message.answer(f"Ресторан {rest_id} разблокирован.")

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
    until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("UPDATE rest SET subscribed=1, subscribe_until=%s WHERE id=%s", (until, rest_id))
    conn.commit()
    await message.answer(f"Подписка ресторана {rest_id} продлена до {until}")

# === КАБИНЕТ РЕСТОРАНА ===
@router.message(Command("mycabinet"))
async def cmd_mycabinet(message: Message):
    restaurant = get_restaurant_by_owner(message.from_user.id)
    if not restaurant:
        await message.answer("У тебя нет зарегистрированного ресторана. Обратись к администратору.")
        return
    await message.answer(f"Кабинет ресторана «{restaurant[1]}»\nВыбери действие:", reply_markup=cabinet_keyboard())

class AddItem(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()

@router.callback_query(F.data == "add_item")
async def start_add_item(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введи название блюда:")
    await state.set_state(AddItem.waiting_for_name)
    await callback.answer()

@router.message(AddItem.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Теперь описание (или отправь '-', если нет):")
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
    restaurant = get_restaurant_by_owner(message.from_user.id)
    if restaurant:
        add_menu_item(restaurant[0], data['name'], data['description'], price)
        await message.answer(f"Блюдо «{data['name']}» добавлено!")
    else:
        await message.answer("Ошибка: ресторан не найден.")
    await state.clear()

@router.callback_query(F.data == "my_items")
async def show_my_items(callback: CallbackQuery):
    restaurant = get_restaurant_by_owner(callback.from_user.id)
    if not restaurant:
        await callback.message.answer("Ресторан не найден.")
        await callback.answer()
        return
    items = get_menu_items(restaurant[0])
    if not items:
        await callback.message.answer("У тебя пока нет блюд. Добавь через кнопку «Добавить блюдо».")
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for item in items:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"❌ {item[2]} — {item[4]} сомони", callback_data=f"del_item_{item[0]}")
        ])
    await callback.message.answer("Твои блюда (нажми, чтобы удалить):", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("del_item_"))
async def delete_item(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[2])
    delete_menu_item(item_id)
    await callback.message.answer("Блюдо удалено.")
    await callback.answer()

@router.callback_query(F.data == "my_orders")
async def show_orders(callback: CallbackQuery):
    restaurant = get_restaurant_by_owner(callback.from_user.id)
    if not restaurant:
        await callback.message.answer("Ресторан не найден.")
        await callback.answer()
        return
    orders = get_orders_by_restaurant(restaurant[0], 'new')
    if not orders:
        await callback.message.answer("Новых заказов нет.")
        await callback.answer()
        return
    for order in orders:
        text = (f"Заказ #{order[0]}\n"
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
    order_id = int(callback.data.split("_")[2])
    update_order_status(order_id, 'accepted')
    await callback.message.answer(f"Заказ #{order_id} принят.")
    await callback.answer()

@router.callback_query(F.data.startswith("reject_order_"))
async def reject_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    update_order_status(order_id, 'rejected')
    await callback.message.answer(f"Заказ #{order_id} отклонён.")
    await callback.answer()

# === КЛИЕНТ ===
@router.message(Command("start"))
async def cmd_start(message: Message):
    restaurants = get_active_restaurants()
    if not restaurants:
        await message.answer("Пока нет доступных ресторанов.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for r in restaurants:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=r[1], callback_data=f"show_menu_{r[0]}")
        ])
    await message.answer("Выбери ресторан:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("show_menu_"))
async def show_menu(callback: CallbackQuery):
    rest_id = int(callback.data.split("_")[2])
    restaurant = get_restaurant_by_id(rest_id)
    if not restaurant:
        await callback.message.answer("Ресторан не найден.")
        await callback.answer()
        return
    items = get_menu_items(rest_id)
    if not items:
        await callback.message.answer("Меню пока пусто.")
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for item in items:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"{item[2]} — {item[4]} сомони", callback_data=f"order_item_{item[0]}")
        ])
    await callback.message.answer(f"Меню ресторана «{restaurant[1]}»:", reply_markup=keyboard)
    await callback.answer()

class OrderItem(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_address = State()

@router.callback_query(F.data.startswith("order_item_"))
async def start_order_item(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split("_")[2])
    await state.update_data(item_id=item_id)
    await callback.message.answer("Введи своё имя:")
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
    items_text = f"{item[2]} (1 шт.)"
    total = item[4]
    order_id = add_order(rest_id, data['client_name'], data['client_phone'], message.text, items_text, total)
    restaurant = get_restaurant_by_id(rest_id)
    if restaurant and restaurant[4]:
        try:
            await bot.send_message(
                restaurant[4],
                f"🆕 Новый заказ!\n"
                f"Клиент: {data['client_name']}\n"
                f"Телефон: {data['client_phone']}\n"
                f"Адрес: {message.text}\n"
                f"Товары: {items_text}\n"
                f"Сумма: {total} сомони"
            )
        except:
            pass
    await message.answer(f"Заказ #{order_id} отправлен! Ресторан свяжется с тобой.")
    await state.clear()

# === ЗАПУСК (WEBHOOK через aiohttp) ===
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
