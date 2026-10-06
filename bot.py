import asyncio
import logging
import math
import os
import random
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# ---------------- База данных ----------------
db = sqlite3.connect("toi.db")
db.row_factory = sqlite3.Row
db.executescript(
    """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT, lat REAL, lon REAL);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, name TEXT,
    price INTEGER, capacity INTEGER, lat REAL, lon REAL,
    address TEXT, info TEXT);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER,
    user_id INTEGER, user_name TEXT, rating INTEGER, text TEXT);
CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER, item_id INTEGER,
    PRIMARY KEY (user_id, item_id));
"""
)

# Демо-данные: замени на реальные залы, цены и координаты
if db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0:
    seed = [
        ("venue", "Зал «Алтын Орда»", 12000, 300, 43.2565, 76.9285, "ул. Примерная, 1", "Большая сцена, парковка, отдельная кухня"),
        ("venue", "Ресторан «Дастархан»", 9000, 150, 43.2380, 76.9450, "ул. Примерная, 2", "Уютный зал, живая музыка"),
        ("venue", "Банкет-холл «Шанырак»", 15000, 500, 43.2100, 76.8900, "ул. Примерная, 3", "VIP-зона, LED-экраны, свой декор"),
        ("venue", "Зал «Жеті Қазына»", 7000, 100, 43.2700, 76.9600, "ул. Примерная, 4", "Бюджетный вариант для небольших тоев"),
        ("host", "Арман Тамада", 150000, None, None, None, "", "Опыт 10 лет, казахский и русский, свой DJ"),
        ("host", "Айгерим Шоу", 200000, None, None, None, "", "Ведущая + конкурсы, шоу-программа"),
        ("host", "Ерлан Тои", 100000, None, None, None, "", "Классический тои, живой вокал"),
    ]
    db.executemany(
        "INSERT INTO items (kind,name,price,capacity,lat,lon,address,info) VALUES (?,?,?,?,?,?,?,?)",
        seed,
    )
    db.commit()

QUERY = """
SELECT i.*, ROUND(AVG(r.rating), 1) AS rating, COUNT(r.id) AS n
FROM items i LEFT JOIN reviews r ON r.item_id = i.id
{where} GROUP BY i.id
"""


# ---------------- Вспомогательные функции ----------------
def register(user):
    db.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (user.id, user.first_name))
    db.commit()


def dist_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def money(n):
    return f"{n:,}".replace(",", " ") + " ₸"


def query_items(where, params, uid):
    loc = db.execute("SELECT lat, lon FROM users WHERE id = ?", (uid,)).fetchone()
    items = []
    for r in db.execute(QUERY.format(where=where), params):
        d = dict(r)
        d["dist"] = None
        if loc and loc["lat"] is not None and d["lat"] is not None:
            d["dist"] = dist_km(loc["lat"], loc["lon"], d["lat"], d["lon"])
        items.append(d)
    return items


def sort_items(items, sort):
    if sort == "price":
        return sorted(items, key=lambda x: x["price"])
    if sort == "dist":
        return sorted(items, key=lambda x: (x["dist"] is None, x["dist"] or 0))
    return sorted(items, key=lambda x: -(x["rating"] or 0))


def card(d):
    venue = d["kind"] == "venue"
    lines = [f"{'🏛' if venue else '🎤'} {d['name']}"]
    lines.append(f"💰 {money(d['price'])} {'за гостя' if venue else 'за вечер'}")
    if venue:
        lines.append(f"👥 Вместимость: до {d['capacity']} гостей")
    lines.append(f"⭐ {d['rating']} ({d['n']} отз.)" if d["n"] else "⭐ Пока нет отзывов")
    if venue:
        if d["dist"] is not None:
            lines.append(f"📍 {d['dist']:.1f} км от тебя")
        else:
            lines.append("📍 Отправь геолокацию, чтобы увидеть расстояние")
        lines.append(f"🏠 {d['address']}")
    lines.append(f"📝 {d['info']}")
    return "\n".join(lines)


def list_view(kind, sort, uid):
    items = sort_items(query_items("WHERE i.kind = ?", (kind,), uid), sort)
    title = "🏛 Залы" if kind == "venue" else "🎤 Тамада"
    names = {"rating": "по рейтингу", "price": "по цене", "dist": "по расстоянию"}
    text = f"{title} — сортировка {names[sort]}:"
    rows = []
    sorts = [("⭐", "rating"), ("💰", "price")] + ([("📍", "dist")] if kind == "venue" else [])
    rows.append([InlineKeyboardButton(text=("• " if s == sort else "") + e, callback_data=f"list:{kind}:{s}") for e, s in sorts])
    for d in items:
        label = f"{d['name']} · {money(d['price'])}" + (f" · ⭐{d['rating']}" if d["n"] else "")
        if d["dist"] is not None:
            label += f" · {d['dist']:.1f} км"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"item:{d['id']}")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def items_keyboard(items):
    rows = []
    for d in items:
        label = f"{d['name']} · {money(d['price'])}" + (f" · ⭐{d['rating']}" if d["n"] else "")
        if d["dist"] is not None:
            label += f" · {d['dist']:.1f} км"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"item:{d['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_items(text, uid):
    q = text.strip().casefold()
    found = [
        d for d in query_items("", (), uid)
        if q in d["name"].casefold() or q in (d["info"] or "").casefold()
    ]
    return sort_items(found, "rating")


def is_fav(uid, item_id):
    row = db.execute(
        "SELECT 1 FROM favorites WHERE user_id = ? AND item_id = ?", (uid, item_id)
    ).fetchone()
    return row is not None


def item_kb(item_id, back, uid):
    fav_text = "💔 Убрать из избранного" if is_fav(uid, item_id) else "⭐ В избранное"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Отзывы", callback_data=f"revs:{item_id}"),
                InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data=f"addrev:{item_id}"),
            ],
            [InlineKeyboardButton(text=fav_text, callback_data=f"fav:{item_id}")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data=f"list:{back}:rating")],
        ]
    )


# ---------------- Меню ----------------
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏛 Залы"), KeyboardButton(text="🎤 Тамада")],
        [KeyboardButton(text="💰 Подбор по бюджету"), KeyboardButton(text="⭐ Избранное")],
        [KeyboardButton(text="📍 Моё местоположение", request_location=True), KeyboardButton(text="📍 Рядом")],
        [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="💬 Мои отзывы")],
        [KeyboardButton(text="ℹ️ О боте")],
    ],
    resize_keyboard=True,
)


class Budget(StatesGroup):
    guests = State()
    money = State()


class Review(StatesGroup):
    text = State()


class Search(StatesGroup):
    query = State()


# ---------------- Хендлеры ----------------
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    register(message.from_user)
    await message.answer(
        f"Привет, {message.from_user.first_name}! 🎉\n"
        "Я помогу выбрать, где устроить тои: залы, тамада, цены, отзывы и расстояние.\n\n"
        "Нажми «📍 Моё местоположение», чтобы я показал расстояние до залов.",
        reply_markup=main_kb,
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "/start — меню\n/halls — залы\n/hosts — тамада\n"
        "/budget — подбор по бюджету\n/favorites — избранное\n/top — топ залов\n"
        "/stats — статистика\n/random — случайный зал\n/about — о боте\n"
        "/search — поиск по названию\n/nearby — ближайшие залы\n/myreviews — мои отзывы"
    )


@dp.message(F.location)
async def got_location(message: Message):
    register(message.from_user)
    db.execute(
        "UPDATE users SET lat = ?, lon = ? WHERE id = ?",
        (message.location.latitude, message.location.longitude, message.from_user.id),
    )
    db.commit()
    await message.answer("📍 Геолокация сохранена. Теперь в списке залов видно расстояние.")


@dp.message(Command("halls"))
@dp.message(F.text == "🏛 Залы")
async def halls(message: Message, state: FSMContext):
    await state.clear()
    register(message.from_user)
    text, kb = list_view("venue", "rating", message.from_user.id)
    await message.answer(text, reply_markup=kb)


@dp.message(Command("hosts"))
@dp.message(F.text == "🎤 Тамада")
async def hosts(message: Message, state: FSMContext):
    await state.clear()
    register(message.from_user)
    text, kb = list_view("host", "rating", message.from_user.id)
    await message.answer(text, reply_markup=kb)


async def send_search(message: Message, text):
    found = search_items(text, message.from_user.id)
    if not found:
        await message.answer(f"По запросу «{text}» ничего не нашлось 🤷 Попробуй другое слово.")
        return
    header = f"🔍 Найдено: {len(found)}" + (" (показаны первые 10)" if len(found) > 10 else "")
    await message.answer(header, reply_markup=items_keyboard(found[:10]))


@dp.message(Command("search"))
@dp.message(F.text == "🔍 Поиск")
async def search_start(message: Message, state: FSMContext, command: CommandObject = None):
    await state.clear()
    register(message.from_user)
    text = (command.args or "").strip() if command else ""
    if text:
        await send_search(message, text)
        return
    await state.set_state(Search.query)
    await message.answer("Что ищем? Напиши название или слово из описания, например: шанырак")


@dp.message(Command("nearby"))
@dp.message(F.text == "📍 Рядом")
async def nearby(message: Message, state: FSMContext):
    await state.clear()
    register(message.from_user)
    venues = query_items("WHERE i.kind = 'venue'", (), message.from_user.id)
    venues = [d for d in venues if d["dist"] is not None]
    if not venues:
        await message.answer("Я пока не знаю, где ты 🤷 Нажми «📍 Моё местоположение», и я покажу ближайшие залы.")
        return
    nearest = sort_items(venues, "dist")[:3]
    await message.answer("📍 Ближайшие к тебе залы:", reply_markup=items_keyboard(nearest))


@dp.message(Command("myreviews"))
@dp.message(F.text == "💬 Мои отзывы")
async def my_reviews(message: Message, state: FSMContext):
    await state.clear()
    register(message.from_user)
    rows = db.execute(
        "SELECT i.name, r.rating, r.text FROM reviews r JOIN items i ON i.id = r.item_id "
        "WHERE r.user_id = ? ORDER BY r.id DESC LIMIT 10",
        (message.from_user.id,),
    ).fetchall()
    if not rows:
        await message.answer("Ты пока не оставлял отзывов. Открой зал или тамаду и нажми «✍️ Оставить отзыв».")
        return
    blocks = []
    for r in rows:
        block = f"{'⭐' * r['rating']} {r['name']}"
        if r["text"]:
            block += f"\n{r['text'][:300]}"
        blocks.append(block)
    await message.answer("💬 Твои отзывы:\n\n" + "\n\n".join(blocks))


@dp.callback_query(F.data.startswith("list:"))
async def on_list(call: CallbackQuery):
    _, kind, sort = call.data.split(":")
    text, kb = list_view(kind, sort, call.from_user.id)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass
    await call.answer()


@dp.callback_query(F.data.startswith("item:"))
async def on_item(call: CallbackQuery):
    item_id = int(call.data.split(":")[1])
    d = query_items("WHERE i.id = ?", (item_id,), call.from_user.id)[0]
    back = "venue" if d["kind"] == "venue" else "host"
    kb = item_kb(item_id, back, call.from_user.id)
    await call.message.edit_text(card(d), reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data.startswith("fav:"))
async def on_fav(call: CallbackQuery):
    item_id = int(call.data.split(":")[1])
    uid = call.from_user.id
    if is_fav(uid, item_id):
        db.execute("DELETE FROM favorites WHERE user_id = ? AND item_id = ?", (uid, item_id))
        msg = "Убрано из избранного"
    else:
        db.execute("INSERT INTO favorites (user_id, item_id) VALUES (?, ?)", (uid, item_id))
        msg = "Добавлено в избранное ⭐"
    db.commit()
    d = query_items("WHERE i.id = ?", (item_id,), uid)[0]
    back = "venue" if d["kind"] == "venue" else "host"
    try:
        await call.message.edit_reply_markup(reply_markup=item_kb(item_id, back, uid))
    except TelegramBadRequest:
        pass
    await call.answer(msg)


@dp.callback_query(F.data.startswith("revs:"))
async def on_reviews(call: CallbackQuery):
    item_id = int(call.data.split(":")[1])
    rows = db.execute(
        "SELECT user_name, rating, text FROM reviews WHERE item_id = ? ORDER BY id DESC LIMIT 5",
        (item_id,),
    ).fetchall()
    if not rows:
        await call.answer("Отзывов пока нет. Будь первым!", show_alert=True)
        return
    text = "💬 Последние отзывы:\n\n" + "\n\n".join(
        f"{'⭐' * r['rating']} {r['user_name']}\n{r['text']}" for r in rows
    )
    await call.message.answer(text)
    await call.answer()


@dp.callback_query(F.data.startswith("addrev:"))
async def on_add_review(call: CallbackQuery):
    item_id = int(call.data.split(":")[1])
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{n}⭐", callback_data=f"rate:{item_id}:{n}") for n in range(1, 6)]
        ]
    )
    await call.message.answer("Поставь оценку:", reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data.startswith("rate:"))
async def on_rate(call: CallbackQuery, state: FSMContext):
    _, item_id, rating = call.data.split(":")
    await state.set_state(Review.text)
    await state.update_data(item_id=int(item_id), rating=int(rating))
    await call.message.answer("Напиши короткий отзыв (или «-», чтобы оставить только оценку):")
    await call.answer()


@dp.message(Review.text)
async def save_review(message: Message, state: FSMContext):
    data = await state.get_data()
    text = "" if message.text.strip() == "-" else message.text.strip()
    db.execute(
        "INSERT INTO reviews (item_id, user_id, user_name, rating, text) VALUES (?,?,?,?,?)",
        (data["item_id"], message.from_user.id, message.from_user.first_name, data["rating"], text),
    )
    db.commit()
    await state.clear()
    await message.answer("Спасибо за отзыв! ✅")


@dp.message(Command("budget"))
@dp.message(F.text == "💰 Подбор по бюджету")
async def budget_start(message: Message, state: FSMContext):
    await state.set_state(Budget.guests)
    await message.answer("Сколько будет гостей?")


@dp.message(Budget.guests)
async def budget_guests(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Напиши число, например 120")
        return
    await state.update_data(guests=int(message.text))
    await state.set_state(Budget.money)
    await message.answer("Какой бюджет на зал, в ₸? Например 1500000")


@dp.message(Budget.money)
async def budget_money(message: Message, state: FSMContext):
    digits = message.text.replace(" ", "")
    if not digits.isdigit():
        await message.answer("Напиши сумму числом, например 1500000")
        return
    guests = (await state.get_data())["guests"]
    budget = int(digits)
    await state.clear()
    items = query_items("WHERE i.kind = 'venue'", (), message.from_user.id)
    fits = [d for d in items if d["capacity"] >= guests and d["price"] * guests <= budget]
    if not fits:
        await message.answer("😕 Под такие условия залов нет. Попробуй увеличить бюджет или уменьшить число гостей.")
        return
    lines = [f"Подходящие залы для {guests} гостей:\n"]
    for d in sorted(fits, key=lambda x: x["price"]):
        lines.append(f"🏛 {d['name']}\n   Итого: {money(d['price'] * guests)} ({money(d['price'])}/гость)"
                     + (f" · ⭐{d['rating']}" if d["n"] else ""))
    await message.answer("\n".join(lines))


@dp.message(Command("about"))
@dp.message(F.text == "ℹ️ О боте")
async def about(message: Message):
    await message.answer("toi — помощник по выбору места и тамады для тоя.\nАвтор: Рауан.")


@dp.message(Command("favorites"))
@dp.message(F.text == "⭐ Избранное")
async def favorites(message: Message, state: FSMContext):
    await state.clear()
    register(message.from_user)
    uid = message.from_user.id
    items = query_items(
        "WHERE i.id IN (SELECT item_id FROM favorites WHERE user_id = ?)", (uid,), uid
    )
    if not items:
        await message.answer("В избранном пока пусто. Открой зал или тамаду и нажми «⭐ В избранное».")
        return
    rows = []
    for d in sort_items(items, "rating"):
        label = f"{d['name']} · {money(d['price'])}" + (f" · ⭐{d['rating']}" if d["n"] else "")
        rows.append([InlineKeyboardButton(text=label, callback_data=f"item:{d['id']}")])
    await message.answer("⭐ Твоё избранное:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.message(Command("top"))
async def top(message: Message):
    items = query_items("WHERE i.kind = 'venue'", (), message.from_user.id)
    lines = ["🏆 Топ-3 зала по рейтингу:\n"]
    for i, d in enumerate(sort_items(items, "rating")[:3], 1):
        lines.append(f"{i}. {d['name']} — {money(d['price'])}" + (f" · ⭐{d['rating']}" if d["n"] else ""))
    await message.answer("\n".join(lines))


@dp.message(Command("stats"))
async def stats(message: Message):
    venues = db.execute("SELECT COUNT(*) FROM items WHERE kind = 'venue'").fetchone()[0]
    hosts = db.execute("SELECT COUNT(*) FROM items WHERE kind = 'host'").fetchone()[0]
    reviews = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    await message.answer(f"📊 Залов: {venues}\n🎤 Тамада: {hosts}\n💬 Отзывов: {reviews}")


@dp.message(Command("random"))
async def random_venue(message: Message):
    items = query_items("WHERE i.kind = 'venue'", (), message.from_user.id)
    await message.answer(card(random.choice(items)))


@dp.message(Search.query, F.text)
async def search_query(message: Message, state: FSMContext):
    await state.clear()
    await send_search(message, message.text)


@dp.message(F.text)
async def fallback(message: Message):
    await message.answer("Не понял 🤔 Выбери кнопку в меню или напиши /help")


# ---------------- Запуск ----------------
async def main():
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Меню"),
            BotCommand(command="halls", description="Залы"),
            BotCommand(command="hosts", description="Тамада"),
            BotCommand(command="budget", description="Подбор по бюджету"),
            BotCommand(command="favorites", description="Избранное"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="about", description="О боте"),
            BotCommand(command="random", description="Случайный зал"),
            BotCommand(command="stats", description="Статистика"),
            BotCommand(command="top", description="Топ залов"),
            BotCommand(command="search", description="Поиск"),
            BotCommand(command="nearby", description="Ближайшие залы"),
            BotCommand(command="myreviews", description="Мои отзывы"),
        ]
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())