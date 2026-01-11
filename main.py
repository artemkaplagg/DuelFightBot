import asyncio
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import json
import os

# Конфигурация

BOT_TOKEN = “8483668116:AAHIyckwZFk7kx5DOUTbB0zWCY5vvuw0f64”
ADMIN_ID = 6185367393

# Настройка логирования

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(**name**)

# Инициализация бота

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# FSM States

class DuelStates(StatesGroup):
waiting_for_opponent = State()
in_duel = State()
answering = State()

class RegistrationStates(StatesGroup):
choosing_class = State()

# Классы персонажей

CLASSES = {
“ninja”: {“name”: “Ниндзя”, “hp”: 80, “damage”: 25, “speed_bonus”: 1.2, “emoji”: “🥷”},
“knight”: {“name”: “Рыцарь”, “hp”: 120, “damage”: 20, “speed_bonus”: 1.0, “emoji”: “🛡”},
“mage”: {“name”: “Маг”, “hp”: 90, “damage”: 30, “speed_bonus”: 0.9, “emoji”: “🧙”}
}

# База данных (в реальном проекте используй SQLite/PostgreSQL)

users_db: Dict = {}
active_duels: Dict = {}
waiting_queue: List = []

# Сохранение/загрузка данных

def save_data():
with open(“database.json”, “w”, encoding=“utf-8”) as f:
json.dump(users_db, f, ensure_ascii=False, indent=2)

def load_data():
global users_db
if os.path.exists(“database.json”):
with open(“database.json”, “r”, encoding=“utf-8”) as f:
users_db = json.load(f)

# Инициализация игрока

def create_user(user_id: int, username: str, class_type: str):
class_data = CLASSES[class_type]
users_db[str(user_id)] = {
“username”: username,
“class”: class_type,
“level”: 1,
“xp”: 0,
“hp”: class_data[“hp”],
“max_hp”: class_data[“hp”],
“damage”: class_data[“damage”],
“coins”: 100,
“wins”: 0,
“losses”: 0,
“win_streak”: 0,
“best_streak”: 0,
“total_duels”: 0,
“energy”: 5,
“last_energy_regen”: datetime.now().isoformat(),
“inventory”: {“weapon”: “rusty_sword”, “armor”: None, “artifact”: None},
“achievements”: [],
“registration_date”: datetime.now().isoformat(),
“last_daily”: None,
“combo”: 0,
“total_damage”: 0,
“fastest_answer”: 999
}
save_data()

# Генерация заданий для дуэли

def generate_challenge():
challenge_types = [
{
“type”: “reverse”,
“question”: “Напиши слово ЭКСКАЛИБУР наоборот:”,
“answer”: “РУБИЛАКСЭ”,
“difficulty”: 2
},
{
“type”: “math”,
“question”: lambda: f”Реши быстро: {(a:=random.randint(10,50))} + {(b:=random.randint(10,50))} - {(c:=random.randint(5,20))} =”,
“answer”: lambda q: str(eval(q.split(”:”)[1].replace(”=”, “”))),
“difficulty”: 1
},
{
“type”: “emoji”,
“question”: “Найди лишний эмодзи:\n🍎🍎🍎🍊🍎🍎🍎”,
“answer”: “🍊”,
“difficulty”: 1
},
{
“type”: “word_search”,
“question”: lambda: f”Найди слово ‘{(word:=random.choice([‘КОТ’, ‘ПЕС’, ‘ДОМ’, ‘ЛЕС’]))}’ в:\nКМОТПФЕДСОЛМЕКСОТ”,
“answer”: lambda q: q.split(”’”)[1],
“difficulty”: 2
}
]

```
challenge = random.choice(challenge_types)
if callable(challenge["question"]):
    question = challenge["question"]()
else:
    question = challenge["question"]

if callable(challenge.get("answer")):
    answer = challenge["answer"](question)
else:
    answer = challenge["answer"]

return {
    "question": question,
    "answer": answer,
    "difficulty": challenge["difficulty"],
    "start_time": time.time()
}
```

# Обновление энергии

def update_energy(user_id: str):
user = users_db[user_id]
last_regen = datetime.fromisoformat(user[“last_energy_regen”])
hours_passed = (datetime.now() - last_regen).total_seconds() / 3600

```
if hours_passed >= 1:
    energy_to_add = int(hours_passed)
    user["energy"] = min(5, user["energy"] + energy_to_add)
    user["last_energy_regen"] = datetime.now().isoformat()
    save_data()
```

# Клавиатуры

def main_menu_kb():
kb = InlineKeyboardMarkup(inline_keyboard=[
[InlineKeyboardButton(text=“👤 Мой Герой”, callback_data=“profile”)],
[InlineKeyboardButton(text=“⚔️ Быстрая Дуэль”, callback_data=“quick_duel”)],
[InlineKeyboardButton(text=“🏪 Магазин”, callback_data=“shop”),
InlineKeyboardButton(text=“🎒 Инвентарь”, callback_data=“inventory”)],
[InlineKeyboardButton(text=“🏆 Рейтинг”, callback_data=“top”),
InlineKeyboardButton(text=“📊 Статистика”, callback_data=“stats”)],
[InlineKeyboardButton(text=“🎁 Ежедневка”, callback_data=“daily”),
InlineKeyboardButton(text=“🎯 Квесты”, callback_data=“quests”)]
])
return kb

def class_selection_kb():
kb = InlineKeyboardMarkup(inline_keyboard=[
[InlineKeyboardButton(text=f”{CLASSES[‘ninja’][‘emoji’]} Ниндзя (Скорость)”, callback_data=“class_ninja”)],
[InlineKeyboardButton(text=f”{CLASSES[‘knight’][‘emoji’]} Рыцарь (Здоровье)”, callback_data=“class_knight”)],
[InlineKeyboardButton(text=f”{CLASSES[‘mage’][‘emoji’]} Маг (Урон)”, callback_data=“class_mage”)]
])
return kb

def admin_kb():
kb = InlineKeyboardMarkup(inline_keyboard=[
[InlineKeyboardButton(text=“📊 Статистика бота”, callback_data=“admin_stats”)],
[InlineKeyboardButton(text=“📢 Рассылка”, callback_data=“admin_broadcast”)],
[InlineKeyboardButton(text=“👥 Топ игроков”, callback_data=“admin_top”)],
[InlineKeyboardButton(text=“🔄 Сброс энергии всем”, callback_data=“admin_reset_energy”)]
])
return kb

# Команда /start

@dp.message(Command(“start”))
async def cmd_start(message: types.Message, state: FSMContext):
user_id = str(message.from_user.id)

```
if user_id not in users_db:
    welcome_text = (
        "🏛️ Добро пожаловать в SHADOW DUEL ARENA!\n\n"
        "Ты вступаешь в мир кибер-дуэлей, где скорость решает всё.\n"
        "Выбери свой класс и начни путь к славе!\n\n"
        "🥷 НИНДЗЯ - Быстрее отвечает на задания\n"
        "🛡 РЫЦАРЬ - Больше HP, выносливее в бою\n"
        "🧙 МАГ - Наносит критический урон\n\n"
        "Выбирай с умом, воин!"
    )
    await message.answer(welcome_text, reply_markup=class_selection_kb())
    await state.set_state(RegistrationStates.choosing_class)
else:
    user = users_db[user_id]
    greeting = (
        f"С возвращением, {CLASSES[user['class']]['emoji']} {user['username']}!\n\n"
        f"🎚 Уровень: {user['level']}\n"
        f"⚡️ Энергия: {user['energy']}/5\n"
        f"🏆 Побед: {user['wins']} | Поражений: {user['losses']}\n"
        f"💰 Монеты: {user['coins']}\n\n"
        f"Выбери действие:"
    )
    await message.answer(greeting, reply_markup=main_menu_kb())
```

# Выбор класса

@dp.callback_query(F.data.startswith(“class_”))
async def process_class_selection(callback: CallbackQuery, state: FSMContext):
class_type = callback.data.replace(“class_”, “”)
user_id = str(callback.from_user.id)
username = callback.from_user.username or callback.from_user.first_name

```
create_user(user_id, username, class_type)

class_info = CLASSES[class_type]
welcome = (
    f"⚔️ Отличный выбор, {class_info['emoji']} {class_info['name']}!\n\n"
    f"Стартовое снаряжение:\n"
    f"🗡 Ржавый меч\n"
    f"💰 100 монет\n"
    f"❤️ {class_info['hp']} HP\n"
    f"⚡️ {class_info['damage']} Урон\n\n"
    f"🎯 Пройди тренировку против Манекена!"
)

training_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎯 Начать тренировку", callback_data="training_start")]
])

await callback.message.edit_text(welcome, reply_markup=training_kb)
await state.clear()
```

# Тренировочный бой

@dp.callback_query(F.data == “training_start”)
async def training_duel(callback: CallbackQuery, state: FSMContext):
challenge = generate_challenge()

```
await callback.message.edit_text(
    f"🎯 ТРЕНИРОВКА\n\n"
    f"Задание: {challenge['question']}\n\n"
    f"Напиши ответ в чат!"
)

await state.update_data(training_challenge=challenge)
await state.set_state(DuelStates.answering)
```

# Обработка ответа в тренировке

@dp.message(DuelStates.answering)
async def process_training_answer(message: types.Message, state: FSMContext):
data = await state.get_data()
challenge = data.get(“training_challenge”)

```
if not challenge:
    return

response_time = time.time() - challenge["start_time"]
user_answer = message.text.strip().upper()
correct_answer = challenge["answer"].upper()

if user_answer == correct_answer:
    xp_reward = 50
    coins_reward = 25
    
    user_id = str(message.from_user.id)
    users_db[user_id]["xp"] += xp_reward
    users_db[user_id]["coins"] += coins_reward
    save_data()
    
    result = (
        f"✅ ПРАВИЛЬНО!\n\n"
        f"⏱ Время ответа: {response_time:.2f}с\n"
        f"✨ +{xp_reward} XP\n"
        f"💰 +{coins_reward} монет\n\n"
        f"🎊 Тренировка завершена! Ты готов к настоящим дуэлям!"
    )
    
    await message.answer(result, reply_markup=main_menu_kb())
    await state.clear()
else:
    await message.answer(
        f"❌ Неверно! Правильный ответ: {challenge['answer']}\n"
        f"Попробуй еще раз!"
    )
```

# Профиль игрока

@dp.callback_query(F.data == “profile”)
async def show_profile(callback: CallbackQuery):
user_id = str(callback.from_user.id)
user = users_db.get(user_id)

```
if not user:
    await callback.answer("Сначала зарегистрируйся через /start")
    return

update_energy(user_id)

class_info = CLASSES[user["class"]]
win_rate = (user["wins"] / user["total_duels"] * 100) if user["total_duels"] > 0 else 0

profile_text = (
    f"{class_info['emoji']} {user['username'].upper()}\n"
    f"━━━━━━━━━━━━━━━━\n"
    f"🎚 Уровень: {user['level']} | XP: {user['xp']}/100\n"
    f"❤️ HP: {user['hp']}/{user['max_hp']}\n"
    f"⚔️ Урон: {user['damage']}\n"
    f"⚡️ Энергия: {user['energy']}/5\n"
    f"💰 Монеты: {user['coins']}\n"
    f"━━━━━━━━━━━━━━━━\n"
    f"📊 СТАТИСТИКА:\n"
    f"🏆 Побед: {user['wins']}\n"
    f"💀 Поражений: {user['losses']}\n"
    f"📈 Винрейт: {win_rate:.1f}%\n"
    f"🔥 Серия побед: {user['win_streak']}\n"
    f"⭐️ Лучшая серия: {user['best_streak']}\n"
    f"⚡️ Лучшее время: {user['fastest_answer']:.2f}с"
)

back_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
])

await callback.message.edit_text(profile_text, reply_markup=back_kb)
```

# Быстрая дуэль

@dp.callback_query(F.data == “quick_duel”)
async def quick_duel(callback: CallbackQuery):
user_id = str(callback.from_user.id)
user = users_db.get(user_id)

```
if not user:
    await callback.answer("Сначала зарегистрируйся!")
    return

update_energy(user_id)

if user["energy"] <= 0:
    await callback.answer("⚡️ Нет энергии! Подожди или купи в магазине", show_alert=True)
    return

await callback.message.edit_text(
    "🔍 Ищем достойного соперника...\n\n"
    "⏳ Подождите немного"
)

await asyncio.sleep(2)

# Поиск реального соперника или создание бота
opponent_id = None
for uid in users_db:
    if uid != user_id and users_db[uid]["energy"] > 0:
        opponent_id = uid
        break

if not opponent_id:
    # Создаем бота-соперника
    bot_classes = list(CLASSES.keys())
    bot_class = random.choice(bot_classes)
    opponent_id = f"bot_{random.randint(1000, 9999)}"
    create_user(int(opponent_id.replace("bot_", "")), "Bot", bot_class)

# Начинаем дуэль
await start_duel(callback.message, user_id, opponent_id)
```

async def start_duel(message, player1_id, player2_id):
duel_id = f”{player1_id}*{player2_id}*{int(time.time())}”

```
active_duels[duel_id] = {
    "player1": player1_id,
    "player2": player2_id,
    "round": 1,
    "max_rounds": 3,
    "scores": {player1_id: 0, player2_id: 0},
    "hp": {
        player1_id: users_db[player1_id]["max_hp"],
        player2_id: users_db[player2_id]["max_hp"]
    }
}

p1_name = users_db[player1_id]["username"]
p2_name = users_db[player2_id]["username"]

await message.edit_text(
    f"⚔️ ДУЭЛЬ НАЧИНАЕТСЯ!\n\n"
    f"{p1_name} VS {p2_name}\n\n"
    f"Дуэль из 3 раундов!\n"
    f"Первым отвечай на задания!\n\n"
    f"3... 2... 1... БОЙ! 💥"
)

await asyncio.sleep(3)
await duel_round(message, duel_id)
```

async def duel_round(message, duel_id):
duel = active_duels[duel_id]
challenge = generate_challenge()

```
duel["current_challenge"] = challenge

round_text = (
    f"⚔️ РАУНД {duel['round']}/{duel['max_rounds']}\n\n"
    f"❤️ HP: {duel['hp'][duel['player1']]} | {duel['hp'][duel['player2']]}\n\n"
    f"📝 {challenge['question']}\n\n"
    f"⚡️ Первый правильный ответ = удар!"
)

await message.edit_text(round_text)
```

# Админ панель

@dp.message(Command(“admin”))
async def admin_panel(message: types.Message):
if message.from_user.id != ADMIN_ID:
await message.answer(“❌ У тебя нет доступа к админ-панели”)
return

```
await message.answer(
    "👑 АДМИН ПАНЕЛЬ\n\n"
    "Управление ботом Shadow Duel Arena",
    reply_markup=admin_kb()
)
```

@dp.callback_query(F.data == “admin_stats”)
async def admin_stats(callback: CallbackQuery):
if callback.from_user.id != ADMIN_ID:
return

```
total_users = len(users_db)
total_duels = sum(u["total_duels"] for u in users_db.values())
total_coins = sum(u["coins"] for u in users_db.values())

stats_text = (
    f"📊 СТАТИСТИКА БОТА\n"
    f"━━━━━━━━━━━━━━━━\n"
    f"👥 Всего игроков: {total_users}\n"
    f"⚔️ Проведено дуэлей: {total_duels}\n"
    f"💰 Монет в обороте: {total_coins}\n"
    f"🎮 Активных дуэлей: {len(active_duels)}"
)

await callback.message.edit_text(stats_text, reply_markup=admin_kb())
```

# Возврат в главное меню

@dp.callback_query(F.data == “back_to_menu”)
async def back_to_menu(callback: CallbackQuery):
user_id = str(callback.from_user.id)
user = users_db[user_id]

```
greeting = (
    f"🏛️ SHADOW DUEL ARENA\n\n"
    f"{CLASSES[user['class']]['emoji']} {user['username']}\n"
    f"⚡️ Энергия: {user['energy']}/5\n"
    f"💰 Монеты: {user['coins']}"
)

await callback.message.edit_text(greeting, reply_markup=main_menu_kb())
```

# Запуск бота

async def main():
load_data()
logger.info(“🚀 Shadow Duel Arena запущен!”)
await dp.start_polling(bot)

if **name** == “**main**”:
asyncio.run(main())