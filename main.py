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
BOT_TOKEN = "8483668116:AAHIyckwZFk7kx5DOUTbB0zWCY5vvuw0f64"
ADMIN_ID = 6185367393

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# FSM States
class DuelStates(StatesGroup):
    waiting_for_opponent = State()
    in_duel = State()
    answering = State()
    training = State()

class RegistrationStates(StatesGroup):
    choosing_class = State()

class AdminStates(StatesGroup):
    broadcasting = State()

# Классы персонажей
CLASSES = {
    "ninja": {
        "name": "Ниндзя",
        "hp": 80,
        "damage": 25,
        "speed_bonus": 1.2,
        "emoji": "🥷",
        "description": "Быстрый как ветер"
    },
    "knight": {
        "name": "Рыцарь",
        "hp": 120,
        "damage": 20,
        "speed_bonus": 1.0,
        "emoji": "🛡",
        "description": "Несокрушимая защита"
    },
    "mage": {
        "name": "Маг",
        "hp": 90,
        "damage": 30,
        "speed_bonus": 0.9,
        "emoji": "🧙",
        "description": "Мастер критов"
    }
}

# Предметы
ITEMS = {
    "weapons": {
        "rusty_sword": {"name": "Ржавый меч", "damage": 0, "price": 0, "emoji": "🗡"},
        "iron_sword": {"name": "Железный меч", "damage": 10, "price": 200, "emoji": "⚔️"},
        "steel_sword": {"name": "Стальной меч", "damage": 25, "price": 500, "emoji": "🗡️"},
        "legendary_blade": {"name": "Легендарный клинок", "damage": 50, "price": 1500, "emoji": "⚡"}
    },
    "armor": {
        "leather_armor": {"name": "Кожаная броня", "hp": 20, "price": 150, "emoji": "🦺"},
        "iron_armor": {"name": "Железная броня", "hp": 40, "price": 400, "emoji": "🛡️"},
        "dragon_armor": {"name": "Драконья броня", "hp": 80, "price": 1200, "emoji": "🐉"}
    },
    "artifacts": {
        "smoke_bomb": {"name": "Дымовая завеса", "effect": "confuse", "price": 300, "emoji": "💨"},
        "health_potion": {"name": "Зелье здоровья", "effect": "heal", "price": 100, "emoji": "🧪"},
        "lucky_coin": {"name": "Счастливая монета", "effect": "luck", "price": 250, "emoji": "🪙"}
    }
}

# Достижения
ACHIEVEMENTS = {
    "first_blood": {"name": "Первая кровь", "desc": "Победи в первой дуэли", "reward": 50, "emoji": "🩸"},
    "speed_demon": {"name": "Скоростной демон", "desc": "Ответь за 2 секунды", "reward": 100, "emoji": "⚡"},
    "unstoppable": {"name": "Неудержимый", "desc": "Серия из 5 побед", "reward": 200, "emoji": "🔥"},
    "rich_warrior": {"name": "Богатый воин", "desc": "Накопи 1000 монет", "reward": 0, "emoji": "💰"},
    "veteran": {"name": "Ветеран", "desc": "Проведи 50 дуэлей", "reward": 300, "emoji": "🎖️"}
}

# База данных
users_db: Dict = {}
active_duels: Dict = {}
waiting_queue: List = []
duel_answers: Dict = {}

# Сохранение/загрузка данных
def save_data():
    try:
        with open("database.json", "w", encoding="utf-8") as f:
            json.dump(users_db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

def load_data():
    global users_db
    try:
        if os.path.exists("database.json"):
            with open("database.json", "r", encoding="utf-8") as f:
                users_db = json.load(f)
                logger.info(f"Загружено {len(users_db)} пользователей")
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        users_db = {}

# Инициализация игрока
def create_user(user_id: int, username: str, class_type: str):
    class_data = CLASSES[class_type]
    users_db[str(user_id)] = {
        "username": username,
        "class": class_type,
        "level": 1,
        "xp": 0,
        "hp": class_data["hp"],
        "max_hp": class_data["hp"],
        "damage": class_data["damage"],
        "coins": 100,
        "wins": 0,
        "losses": 0,
        "win_streak": 0,
        "best_streak": 0,
        "total_duels": 0,
        "energy": 5,
        "last_energy_regen": datetime.now().isoformat(),
        "inventory": {
            "weapon": "rusty_sword",
            "armor": None,
            "artifact": None
        },
        "achievements": [],
        "registration_date": datetime.now().isoformat(),
        "last_daily": None,
        "combo": 0,
        "total_damage": 0,
        "fastest_answer": 999.0,
        "total_answer_time": 0,
        "total_answers": 0,
        "perfect_answers": 0,
        "items_owned": ["rusty_sword"]
    }
    save_data()
    return users_db[str(user_id)]

# Генерация заданий для дуэли
def generate_challenge():
    challenges = [
        {
            "type": "reverse",
            "questions": [
                ("Напиши слово ЭКСКАЛИБУР наоборот:", "РУБИЛАКСЭ"),
                ("Напиши слово ПОБЕДА наоборот:", "АДЕБОП"),
                ("Напиши слово ДУЭЛЬ наоборот:", "ЛЬЭУД"),
                ("Напиши слово ЛЕГЕНДА наоборот:", "АДНЕГЕЛ")
            ],
            "difficulty": 2
        },
        {
            "type": "math",
            "generator": lambda: (
                f"Реши быстро: {(a:=random.randint(10,50))} + {(b:=random.randint(10,50))} - {(c:=random.randint(5,20))} =",
                str(a + b - c)
            ),
            "difficulty": 1
        },
        {
            "type": "emoji",
            "questions": [
                ("Найди лишний эмодзи:\n🍎🍎🍎🍊🍎🍎🍎", "🍊"),
                ("Найди лишний эмодзи:\n⭐⭐⭐💫⭐⭐⭐", "💫"),
                ("Найди лишний эмодзи:\n🔥🔥🔥💧🔥🔥🔥", "💧"),
                ("Найди лишний эмодзи:\n👑👑👑🎩👑👑👑", "🎩")
            ],
            "difficulty": 1
        },
        {
            "type": "word_search",
            "questions": [
                ("В какой позиции слово 'КОТ' в: ДКОТПМКОТ", "2"),
                ("В какой позиции слово 'ДОМ' в: АЗДДОМКСДОМ", "4"),
                ("В какой позиции слово 'ЛЕС' в: ФГЛЕСПСЛЕС", "3")
            ],
            "difficulty": 2
        },
        {
            "type": "count",
            "generator": lambda: (
                f"Сколько раз встречается '💎' в:\n💎🔸💎🔹💎🔸💎🔹💎",
                "5"
            ),
            "difficulty": 1
        },
        {
            "type": "caps",
            "questions": [
                ("Напиши ЗАГЛАВНЫМИ: быстрый", "БЫСТРЫЙ"),
                ("Напиши ЗАГЛАВНЫМИ: воин", "ВОИН"),
                ("Напиши ЗАГЛАВНЫМИ: победа", "ПОБЕДА")
            ],
            "difficulty": 1
        }
    ]
    
    challenge_template = random.choice(challenges)
    
    if "generator" in challenge_template:
        question, answer = challenge_template["generator"]()
    else:
        question, answer = random.choice(challenge_template["questions"])
    
    return {
        "question": question,
        "answer": answer.upper(),
        "difficulty": challenge_template["difficulty"],
        "start_time": time.time(),
        "type": challenge_template["type"]
    }

# Обновление энергии
def update_energy(user_id: str):
    user = users_db.get(user_id)
    if not user:
        return
    
    last_regen = datetime.fromisoformat(user["last_energy_regen"])
    hours_passed = (datetime.now() - last_regen).total_seconds() / 3600
    
    if hours_passed >= 1:
        energy_to_add = int(hours_passed)
        user["energy"] = min(5, user["energy"] + energy_to_add)
        user["last_energy_regen"] = datetime.now().isoformat()
        save_data()

# Проверка достижений
def check_achievements(user_id: str):
    user = users_db[user_id]
    new_achievements = []
    
    # Первая кровь
    if "first_blood" not in user["achievements"] and user["wins"] == 1:
        user["achievements"].append("first_blood")
        new_achievements.append(ACHIEVEMENTS["first_blood"])
        user["coins"] += ACHIEVEMENTS["first_blood"]["reward"]
    
    # Скоростной демон
    if "speed_demon" not in user["achievements"] and user["fastest_answer"] <= 2.0:
        user["achievements"].append("speed_demon")
        new_achievements.append(ACHIEVEMENTS["speed_demon"])
        user["coins"] += ACHIEVEMENTS["speed_demon"]["reward"]
    
    # Неудержимый
    if "unstoppable" not in user["achievements"] and user["win_streak"] >= 5:
        user["achievements"].append("unstoppable")
        new_achievements.append(ACHIEVEMENTS["unstoppable"])
        user["coins"] += ACHIEVEMENTS["unstoppable"]["reward"]
    
    # Богатый воин
    if "rich_warrior" not in user["achievements"] and user["coins"] >= 1000:
        user["achievements"].append("rich_warrior")
        new_achievements.append(ACHIEVEMENTS["rich_warrior"])
    
    # Ветеран
    if "veteran" not in user["achievements"] and user["total_duels"] >= 50:
        user["achievements"].append("veteran")
        new_achievements.append(ACHIEVEMENTS["veteran"])
        user["coins"] += ACHIEVEMENTS["veteran"]["reward"]
    
    if new_achievements:
        save_data()
    
    return new_achievements

# Добавление опыта и проверка уровня
def add_xp(user_id: str, xp_amount: int):
    user = users_db[user_id]
    user["xp"] += xp_amount
    
    xp_needed = user["level"] * 100
    
    if user["xp"] >= xp_needed:
        user["level"] += 1
        user["xp"] = 0
        user["max_hp"] += 10
        user["hp"] = user["max_hp"]
        user["damage"] += 5
        save_data()
        return True
    
    save_data()
    return False

# Клавиатуры
def main_menu_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Мой Герой", callback_data="profile")],
        [InlineKeyboardButton(text="⚔️ Быстрая Дуэль", callback_data="quick_duel")],
        [InlineKeyboardButton(text="🏪 Магазин", callback_data="shop"),
         InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="top"),
         InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🎁 Ежедневка", callback_data="daily"),
         InlineKeyboardButton(text="🏅 Достижения", callback_data="achievements")]
    ])
    return kb

def class_selection_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{CLASSES['ninja']['emoji']} Ниндзя - {CLASSES['ninja']['description']}", callback_data="class_ninja")],
        [InlineKeyboardButton(text=f"{CLASSES['knight']['emoji']} Рыцарь - {CLASSES['knight']['description']}", callback_data="class_knight")],
        [InlineKeyboardButton(text=f"{CLASSES['mage']['emoji']} Маг - {CLASSES['mage']['description']}", callback_data="class_mage")]
    ])
    return kb

def admin_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👥 Топ игроков", callback_data="admin_top_users")],
        [InlineKeyboardButton(text="🔄 Сброс энергии всем", callback_data="admin_reset_energy")],
        [InlineKeyboardButton(text="💰 Выдать монеты", callback_data="admin_give_coins")]
    ])
    return kb

def back_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return kb

def shop_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Оружие", callback_data="shop_weapons")],
        [InlineKeyboardButton(text="🛡️ Броня", callback_data="shop_armor")],
        [InlineKeyboardButton(text="✨ Артефакты", callback_data="shop_artifacts")],
        [InlineKeyboardButton(text="⚡ Энергия (50💰)", callback_data="buy_energy")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return kb

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id not in users_db:
        welcome_text = (
            "🏛️ ДОБРО ПОЖАЛОВАТЬ В SHADOW DUEL ARENA!\n\n"
            "Ты вступаешь в мир кибер-дуэлей, где скорость решает всё.\n"
            "Выбери свой класс и начни путь к славе!\n\n"
            f"🥷 НИНДЗЯ - {CLASSES['ninja']['description']}\n"
            f"HP: {CLASSES['ninja']['hp']} | Урон: {CLASSES['ninja']['damage']}\n\n"
            f"🛡 РЫЦАРЬ - {CLASSES['knight']['description']}\n"
            f"HP: {CLASSES['knight']['hp']} | Урон: {CLASSES['knight']['damage']}\n\n"
            f"🧙 МАГ - {CLASSES['mage']['description']}\n"
            f"HP: {CLASSES['mage']['hp']} | Урон: {CLASSES['mage']['damage']}\n\n"
            "Выбирай с умом, воин!"
        )
        await message.answer(welcome_text, reply_markup=class_selection_kb())
        await state.set_state(RegistrationStates.choosing_class)
    else:
        user = users_db[user_id]
        update_energy(user_id)
        
        greeting = (
            f"С возвращением, {CLASSES[user['class']]['emoji']} {user['username']}!\n\n"
            f"🎚 Уровень: {user['level']}\n"
            f"⚡️ Энергия: {user['energy']}/5\n"
            f"🏆 Побед: {user['wins']} | 💀 Поражений: {user['losses']}\n"
            f"💰 Монеты: {user['coins']}\n\n"
            f"Выбери действие:"
        )
        await message.answer(greeting, reply_markup=main_menu_kb())

# Выбор класса
@dp.callback_query(F.data.startswith("class_"))
async def process_class_selection(callback: CallbackQuery, state: FSMContext):
    class_type = callback.data.replace("class_", "")
    user_id = str(callback.from_user.id)
    username = callback.from_user.username or callback.from_user.first_name
    
    create_user(user_id, username, class_type)
    
    class_info = CLASSES[class_type]
    welcome = (
        f"⚔️ Отличный выбор, {class_info['emoji']} {class_info['name']}!\n\n"
        f"Стартовое снаряжение:\n"
        f"🗡 Ржавый меч\n"
        f"💰 100 монет\n"
        f"❤️ {class_info['hp']} HP\n"
        f"⚡️ {class_info['damage']} Урон\n\n"
        f"🎯 Готов к тренировке против Манекена?"
    )
    
    training_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Начать тренировку", callback_data="training_start")]
    ])
    
    await callback.message.edit_text(welcome, reply_markup=training_kb)
    await state.clear()

# Тренировочный бой
@dp.callback_query(F.data == "training_start")
async def training_duel(callback: CallbackQuery, state: FSMContext):
    challenge = generate_challenge()
    
    await callback.message.edit_text(
        f"🎯 ТРЕНИРОВКА\n\n"
        f"Задание: {challenge['question']}\n\n"
        f"Напиши ответ в чат!"
    )
    
    await state.update_data(training_challenge=challenge, is_training=True)
    await state.set_state(DuelStates.training)

# Обработка ответа в тренировке
@dp.message(DuelStates.training)
async def process_training_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    challenge = data.get("training_challenge")
    
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
        
        # Обновляем статистику
        users_db[user_id]["total_answer_time"] += response_time
        users_db[user_id]["total_answers"] += 1
        
        if response_time < users_db[user_id]["fastest_answer"]:
            users_db[user_id]["fastest_answer"] = response_time
        
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

# Профиль игрока
@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    update_energy(user_id)
    
    class_info = CLASSES[user["class"]]
    win_rate = (user["wins"] / user["total_duels"] * 100) if user["total_duels"] > 0 else 0
    avg_time = (user["total_answer_time"] / user["total_answers"]) if user["total_answers"] > 0 else 0
    
    # Бонус от экипировки
    weapon_bonus = ITEMS["weapons"].get(user["inventory"]["weapon"], {}).get("damage", 0)
    armor = user["inventory"].get("armor")
    armor_bonus = ITEMS["armor"].get(armor, {}).get("hp", 0) if armor else 0
    
    profile_text = (
        f"{class_info['emoji']} {user['username'].upper()}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎚 Уровень: {user['level']} | XP: {user['xp']}/100\n"
        f"❤️ HP: {user['hp']}/{user['max_hp']} (+{armor_bonus})\n"
        f"⚔️ Урон: {user['damage']} (+{weapon_bonus})\n"
        f"⚡️ Энергия: {user['energy']}/5\n"
        f"💰 Монеты: {user['coins']}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 СТАТИСТИКА:\n"
        f"🏆 Побед: {user['wins']}\n"
        f"💀 Поражений: {user['losses']}\n"
        f"📈 Винрейт: {win_rate:.1f}%\n"
        f"🔥 Серия побед: {user['win_streak']}\n"
        f"⭐️ Лучшая серия: {user['best_streak']}\n"
        f"⚡️ Лучшее время: {user['fastest_answer']:.2f}с\n"
        f"📊 Среднее время: {avg_time:.2f}с\n"
        f"🎯 Всего дуэлей: {user['total_duels']}"
    )
    
    await callback.message.edit_text(profile_text, reply_markup=back_kb())

# Быстрая дуэль
@dp.callback_query(F.data == "quick_duel")
async def quick_duel(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйся!")
        return
    
    update_energy(user_id)
    
    if user["energy"] <= 0:
        next_regen = datetime.fromisoformat(user["last_energy_regen"]) + timedelta(hours=1)
        time_left = next_regen - datetime.now()
        minutes_left = int(time_left.total_seconds() / 60)
        await callback.answer(f"⚡️ Нет энергии! Восстановится через {minutes_left} мин или купи в магазине", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 Ищем достойного соперника...\n\n"
        "⏳ Подождите немного"
    )
    
    await asyncio.sleep(2)
    
    # Поиск реального соперника в очереди
    opponent_id = None
    for waiting_id in waiting_queue:
        if waiting_id != user_id:
            opponent_id = waiting_id
            waiting_queue.remove(opponent_id)
            break
    
    if not opponent_id:
        # Создаем бота-соперника
        bot_level = max(1, user["level"] + random.randint(-1, 1))
        bot_class = random.choice(list(CLASSES.keys()))
        bot_id = f"bot_{random.randint(1000, 9999)}"
        
        bot_names = ["Теневой Убийца", "Железный Кулак", "Быстрый Клинок", "Мастер Дуэлей", "Легенда Арены"]
        bot_name = random.choice(bot_names)
        
        class_data = CLASSES[bot_class]
        users_db[bot_id] = {
            "username": bot_name,
            "class": bot_class,
            "level": bot_level,
            "hp": class_data["hp"] + (bot_level - 1) * 10,
            "max_hp": class_data["hp"] + (bot_level - 1) * 10,
            "damage": class_data["damage"] + (bot_level - 1) * 5,
            "is_bot": True
        }
        opponent_id = bot_id
    
    # Начинаем дуэль
    await start_duel(callback.message, user_id, opponent_id, state)

async def start_duel(message, player1_id, player2_id, state: FSMContext):
    duel_id = f"{player1_id}_{player2_id}_{int(time.time())}"
    
    p1 = users_db[player1_id]
    p2 = users_db[player2_id]
    
    active_duels[duel_id] = {
        "player1": player1_id,
        "player2": player2_id,
        "round": 1,
        "max_rounds": 3,
        "scores": {player1_id: 0, player2_id: 0},
        "hp": {
            player1_id: p1["max_hp"],
            player2_id: p2["max_hp"]
        },
        "combo": {player1_id: 0, player2_id: 0},
        "message_id": message.message_id,
        "chat_id": message.chat.id
    }
    
    p1_class = CLASSES[p1["class"]]
    p2_class = CLASSES[p2["class"]]
    
    await message.edit_text(
        f"⚔️ ДУЭЛЬ НАЧИНАЕТСЯ!\n\n"
        f"{p1_class['emoji']} {p1['username']} (Ур.{p1['level']})\n"
        f"VS\n"
        f"{p2_class['emoji']} {p2['username']} (Ур.{p2['level']})\n\n"
        f"Дуэль из 3 раундов!\n"
        f"Первым отвечай на задания!\n\n"
        f"⚡️ 3... 2... 1... БОЙ! 💥"
    )
    
    # Снимаем энергию
    if not p1.get("is_bot"):
        users_db[player1_id]["energy"] -= 1
        save_data()
    
    await asyncio.sleep(3)
    await duel_round(message, duel_id, state)

async def duel_round(message, duel_id, state: FSMContext):
    duel = active_duels.get(duel_id)
    
    if not duel:
        return
    
    challenge = generate_challenge()
    duel["current_challenge"] = challenge
    duel_answers[duel_id] = {}
    
    p1 = users_db[duel["player1"]]
    p2 = users_db[duel["player2"]]
    
    p1_class = CLASSES[p1["class"]]
    p2_class = CLASSES[p2["class"]]
    
    round_text = (
        f"⚔️ РАУНД {duel['round']}/{duel['max_rounds']}\n\n"
        f"{p1_class['emoji']} {p1['username']}: ❤️ {duel['hp'][duel['player1']]}\n"
        f"{p2_class['emoji']} {p2['username']}: ❤️ {duel['hp'][duel['player2']]}\n\n"
        f"📝 {challenge['question']}\n\n"
        f"⚡️ Первый правильный ответ = удар!"
    )
    
    await message.edit_text(round_text)
    
    # Если противник - бот, даем ему время ответить
    if p2.get("is_bot"):
        bot_answer_time = random.uniform(3, 7) / CLASSES[p2["class"]]["speed_bonus"]
        await asyncio.sleep(bot_answer_time)
        
        # Бот иногда ошибается
        bot_correct = random.random() > 0.3
        
        if bot_correct:
            await process_duel_answer(duel["player2"], duel_id, challenge["answer"], message, state)
    
    await state.update_data(current_duel=duel_id)
    await state.set_state(DuelStates.in_duel)

# Обработка ответов в дуэли
@dp.message(DuelStates.in_duel)
async def handle_duel_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    duel_id = data.get("current_duel")
    user_id = str(message.from_user.id)
    
    if not duel_id or duel_id not in active_duels:
        return
    
    duel = active_duels[duel_id]
    
    # Проверяем, что это участник дуэли
    if user_id not in [duel["player1"], duel["player2"]]:
        return
    
    # Проверяем, что игрок еще не ответил
    if user_id in duel_answers.get(duel_id, {}):
        await message.answer("Ты уже ответил! Жди результата...")
        return
    
    user_answer = message.text.strip().upper()
    
    # Получаем оригинальное сообщение дуэли
    try:
        duel_message = await message.bot.get_chat(duel["chat_id"])
        duel_msg = types.Message(message_id=duel["message_id"], chat=duel_message)
    except:
        duel_msg = message
    
    await process_duel_answer(user_id, duel_id, user_answer, duel_msg, state)

async def process_duel_answer(player_id, duel_id, answer, message, state: FSMContext):
    duel = active_duels.get(duel_id)
    if not duel:
        return
    
    challenge = duel.get("current_challenge")
    if not challenge:
        return
    
    # Записываем ответ
    if duel_id not in duel_answers:
        duel_answers[duel_id] = {}
    
    if player_id in duel_answers[duel_id]:
        return
    
    response_time = time.time() - challenge["start_time"]
    is_correct = answer.upper() == challenge["answer"].upper()
    
    duel_answers[duel_id][player_id] = {
        "answer": answer,
        "time": response_time,
        "correct": is_correct
    }
    
    # Ждем ответа второго игрока (или таймаут)
    opponent_id = duel["player2"] if player_id == duel["player1"] else duel["player1"]
    
    # Если оба ответили или прошло время
    if len(duel_answers[duel_id]) >= 2 or response_time > 15:
        await evaluate_round(duel_id, message, state)

async def evaluate_round(duel_id, message, state: FSMContext):
    duel = active_duels.get(duel_id)
    if not duel:
        return
    
    answers = duel_answers.get(duel_id, {})
    
    p1_id = duel["player1"]
    p2_id = duel["player2"]
    
    p1_answer = answers.get(p1_id)
    p2_answer = answers.get(p2_id)
    
    p1 = users_db[p1_id]
    p2 = users_db[p2_id]
    
    winner = None
    result_text = ""
    
    # Определяем победителя раунда
    if p1_answer and p1_answer["correct"] and (not p2_answer or not p2_answer["correct"]):
        winner = p1_id
    elif p2_answer and p2_answer["correct"] and (not p1_answer or not p1_answer["correct"]):
        winner = p2_id
    elif p1_answer and p2_answer and p1_answer["correct"] and p2_answer["correct"]:
        # Оба правильно - побеждает быстрейший
        winner = p1_id if p1_answer["time"] < p2_answer["time"] else p2_id
    
    if winner:
        attacker = users_db[winner]
        defender_id = p2_id if winner == p1_id else p1_id
        
        # Рассчитываем урон
        base_damage = attacker["damage"]
        weapon = attacker["inventory"]["weapon"]
        weapon_bonus = ITEMS["weapons"].get(weapon, {}).get("damage", 0)
        
        # Комбо множитель
        duel["combo"][winner] += 1
        combo_multiplier = 1 + (duel["combo"][winner] - 1) * 0.3
        
        # Крит
        is_crit = random.random() < 0.2
        crit_multiplier = 2.0 if is_crit else 1.0
        
        total_damage = int((base_damage + weapon_bonus) * combo_multiplier * crit_multiplier)
        
        duel["hp"][defender_id] -= total_damage
        duel["scores"][winner] += 1
        
        # Сброс комбо противника
        duel["combo"][defender_id] = 0
        
        attacker_class = CLASSES[attacker["class"]]
        
        result_text = (
            f"💥 {attacker_class['emoji']} {attacker['username']} АТАКУЕТ!\n\n"
        )
        
        if is_crit:
            result_text += f"⚡️ КРИТИЧЕСКИЙ УДАР! ⚡️\n"
        
        if duel["combo"][winner] > 1:
            result_text += f"🔥 КОМБО x{duel['combo'][winner]}! 🔥\n"
        
        result_text += (
            f"⚔️ Урон: {total_damage}\n"
            f"⏱ Время ответа: {answers[winner]['time']:.2f}с\n\n"
        )
        
        # Обновляем статистику атакующего
        if not attacker.get("is_bot"):
            users_db[winner]["total_damage"] += total_damage
            users_db[winner]["total_answer_time"] += answers[winner]["time"]
            users_db[winner]["total_answers"] += 1
            
            if answers[winner]["time"] < users_db[winner]["fastest_answer"]:
                users_db[winner]["fastest_answer"] = answers[winner]["time"]
            
            if answers[winner]["time"] <= 2.0:
                users_db[winner]["perfect_answers"] += 1
    else:
        result_text = "🤷 Никто не ответил правильно!\n\n"
    
    # Показываем HP
    result_text += (
        f"❤️ HP:\n"
        f"{CLASSES[p1['class']]['emoji']} {p1['username']}: {max(0, duel['hp'][p1_id])}\n"
        f"{CLASSES[p2['class']]['emoji']} {p2['username']}: {max(0, duel['hp'][p2_id])}\n"
    )
    
    await message.edit_text(result_text)
    await asyncio.sleep(3)
    
    # Проверяем условия окончания дуэли
    if duel["hp"][p1_id] <= 0 or duel["hp"][p2_id] <= 0 or duel["round"] >= duel["max_rounds"]:
        await end_duel(duel_id, message, state)
    else:
        duel["round"] += 1
        del duel_answers[duel_id]
        await duel_round(message, duel_id, state)

async def end_duel(duel_id, message, state: FSMContext):
    duel = active_duels.get(duel_id)
    if not duel:
        return
    
    p1_id = duel["player1"]
    p2_id = duel["player2"]
    
    p1 = users_db[p1_id]
    p2 = users_db[p2_id]
    
    # Определяем победителя
    if duel["hp"][p1_id] > duel["hp"][p2_id]:
        winner_id = p1_id
        loser_id = p2_id
    elif duel["hp"][p2_id] > duel["hp"][p1_id]:
        winner_id = p2_id
        loser_id = p1_id
    else:
        # Ничья - победитель по очкам
        if duel["scores"][p1_id] > duel["scores"][p2_id]:
            winner_id = p1_id
            loser_id = p2_id
        else:
            winner_id = p2_id
            loser_id = p1_id
    
    winner = users_db[winner_id]
    loser = users_db[loser_id]
    
    # Награды
    coins_reward = random.randint(30, 70)
    xp_reward = 100
    
    # Обновляем статистику победителя
    if not winner.get("is_bot"):
        users_db[winner_id]["wins"] += 1
        users_db[winner_id]["win_streak"] += 1
        users_db[winner_id]["total_duels"] += 1
        users_db[winner_id]["coins"] += coins_reward
        
        if users_db[winner_id]["win_streak"] > users_db[winner_id]["best_streak"]:
            users_db[winner_id]["best_streak"] = users_db[winner_id]["win_streak"]
        
        leveled_up = add_xp(winner_id, xp_reward)
        
        # Проверяем достижения
        new_achievements = check_achievements(winner_id)
    else:
        leveled_up = False
        new_achievements = []
    
    # Обновляем статистику проигравшего
    if not loser.get("is_bot"):
        users_db[loser_id]["losses"] += 1
        users_db[loser_id]["win_streak"] = 0
        users_db[loser_id]["total_duels"] += 1
        save_data()
    
    # Фразы для "просмажування"
    roasts = [
        "Твой меч такой же тупой, как и твоя реакция! 🗡",
        "Слишком медленный для этой арены! ⚡",
        "Возвращайся когда научишься сражаться! 💪",
        "Легкая победа! Даже не вспотел! 😎",
        "Тренируйся еще, боец! 🎯"
    ]
    
    winner_class = CLASSES[winner["class"]]
    loser_class = CLASSES[loser["class"]]
    
    result_text = (
        f"🏆 ПОБЕДА: {winner_class['emoji']} {winner['username']}!\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 РЕЗУЛЬТАТЫ:\n"
        f"Раунды: {duel['scores'][winner_id]} - {duel['scores'][loser_id]}\n"
        f"HP: {duel['hp'][winner_id]} - {max(0, duel['hp'][loser_id])}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
    )
    
    if not winner.get("is_bot"):
        result_text += (
            f"🎁 НАГРАДЫ:\n"
            f"💰 +{coins_reward} монет\n"
            f"✨ +{xp_reward} XP\n"
        )
        
        if leveled_up:
            result_text += f"\n🎊 УРОВЕНЬ ПОВЫШЕН! Теперь {users_db[winner_id]['level']} уровень!\n"
        
        if new_achievements:
            result_text += "\n🏅 НОВЫЕ ДОСТИЖЕНИЯ:\n"
            for ach in new_achievements:
                result_text += f"{ach['emoji']} {ach['name']}\n"
                if ach['reward'] > 0:
                    result_text += f"   💰 +{ach['reward']} монет\n"
    
    result_text += f"\n💬 {random.choice(roasts)}"
    
    await message.edit_text(result_text, reply_markup=main_menu_kb())
    
    # Удаляем дуэль
    del active_duels[duel_id]
    if duel_id in duel_answers:
        del duel_answers[duel_id]
    
    await state.clear()
    save_data()

# Магазин
@dp.callback_query(F.data == "shop")
async def show_shop(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйся!")
        return
    
    shop_text = (
        f"🏪 МАГАЗИН АРЕНЫ\n\n"
        f"💰 Твои монеты: {user['coins']}\n\n"
        f"Выбери категорию:"
    )
    
    await callback.message.edit_text(shop_text, reply_markup=shop_kb())

@dp.callback_query(F.data == "shop_weapons")
async def show_weapons(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    weapons_text = f"⚔️ ОРУЖИЕ\n\n💰 Твои монеты: {user['coins']}\n\n"
    
    buttons = []
    for weapon_id, weapon in ITEMS["weapons"].items():
        if weapon_id == "rusty_sword":
            continue
        
        owned = weapon_id in user.get("items_owned", [])
        status = "✅ Куплено" if owned else f"{weapon['price']}💰"
        
        weapons_text += f"{weapon['emoji']} {weapon['name']}\n"
        weapons_text += f"   Урон: +{weapon['damage']} | {status}\n\n"
        
        if not owned:
            buttons.append([InlineKeyboardButton(
                text=f"{weapon['emoji']} Купить {weapon['name']} ({weapon['price']}💰)",
                callback_data=f"buy_weapon_{weapon_id}"
            )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="shop")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(weapons_text, reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_weapon_"))
async def buy_weapon(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    weapon_id = callback.data.replace("buy_weapon_", "")
    
    weapon = ITEMS["weapons"].get(weapon_id)
    if not weapon:
        await callback.answer("Ошибка!")
        return
    
    if weapon_id in user.get("items_owned", []):
        await callback.answer("Ты уже купил это оружие!")
        return
    
    if user["coins"] < weapon["price"]:
        await callback.answer(f"Недостаточно монет! Нужно {weapon['price']}💰", show_alert=True)
        return
    
    user["coins"] -= weapon["price"]
    user["items_owned"].append(weapon_id)
    save_data()
    
    await callback.answer(f"✅ Куплено: {weapon['name']}!", show_alert=True)
    await show_weapons(callback)

@dp.callback_query(F.data == "shop_armor")
async def show_armor(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    armor_text = f"🛡️ БРОНЯ\n\n💰 Твои монеты: {user['coins']}\n\n"
    
    buttons = []
    for armor_id, armor in ITEMS["armor"].items():
        owned = armor_id in user.get("items_owned", [])
        status = "✅ Куплено" if owned else f"{armor['price']}💰"
        
        armor_text += f"{armor['emoji']} {armor['name']}\n"
        armor_text += f"   HP: +{armor['hp']} | {status}\n\n"
        
        if not owned:
            buttons.append([InlineKeyboardButton(
                text=f"{armor['emoji']} Купить {armor['name']} ({armor['price']}💰)",
                callback_data=f"buy_armor_{armor_id}"
            )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="shop")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(armor_text, reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_armor_"))
async def buy_armor(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    armor_id = callback.data.replace("buy_armor_", "")
    
    armor = ITEMS["armor"].get(armor_id)
    if not armor:
        await callback.answer("Ошибка!")
        return
    
    if armor_id in user.get("items_owned", []):
        await callback.answer("Ты уже купил эту броню!")
        return
    
    if user["coins"] < armor["price"]:
        await callback.answer(f"Недостаточно монет! Нужно {armor['price']}💰", show_alert=True)
        return
    
    user["coins"] -= armor["price"]
    user["items_owned"].append(armor_id)
    save_data()
    
    await callback.answer(f"✅ Куплено: {armor['name']}!", show_alert=True)
    await show_armor(callback)

@dp.callback_query(F.data == "buy_energy")
async def buy_energy(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    if user["energy"] >= 5:
        await callback.answer("У тебя полная энергия!", show_alert=True)
        return
    
    if user["coins"] < 50:
        await callback.answer("Недостаточно монет! Нужно 50💰", show_alert=True)
        return
    
    user["coins"] -= 50
    user["energy"] = 5
    save_data()
    
    await callback.answer("⚡️ Энергия восстановлена!", show_alert=True)
    await show_shop(callback)

# Инвентарь
@dp.callback_query(F.data == "inventory")
async def show_inventory(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйся!")
        return
    
    current_weapon = user["inventory"]["weapon"]
    current_armor = user["inventory"].get("armor")
    
    inv_text = (
        f"🎒 ИНВЕНТАРЬ\n\n"
        f"⚔️ Оружие: {ITEMS['weapons'][current_weapon]['emoji']} {ITEMS['weapons'][current_weapon]['name']}\n"
    )
    
    if current_armor:
        inv_text += f"🛡️ Броня: {ITEMS['armor'][current_armor]['emoji']} {ITEMS['armor'][current_armor]['name']}\n"
    else:
        inv_text += f"🛡️ Броня: Не экипировано\n"
    
    inv_text += "\n📦 ДОСТУПНЫЕ ПРЕДМЕТЫ:\n\n"
    
    buttons = []
    
    # Оружие
    for weapon_id in user.get("items_owned", []):
        if weapon_id in ITEMS["weapons"] and weapon_id != current_weapon:
            weapon = ITEMS["weapons"][weapon_id]
            buttons.append([InlineKeyboardButton(
                text=f"⚔️ Экипировать {weapon['name']}",
                callback_data=f"equip_weapon_{weapon_id}"
            )])
    
    # Броня
    for armor_id in user.get("items_owned", []):
        if armor_id in ITEMS["armor"] and armor_id != current_armor:
            armor = ITEMS["armor"][armor_id]
            buttons.append([InlineKeyboardButton(
                text=f"🛡️ Экипировать {armor['name']}",
                callback_data=f"equip_armor_{armor_id}"
            )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(inv_text, reply_markup=kb)

@dp.callback_query(F.data.startswith("equip_weapon_"))
async def equip_weapon(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    weapon_id = callback.data.replace("equip_weapon_", "")
    
    if weapon_id not in user.get("items_owned", []):
        await callback.answer("У тебя нет этого оружия!")
        return
    
    user["inventory"]["weapon"] = weapon_id
    weapon = ITEMS["weapons"][weapon_id]
    save_data()
    
    await callback.answer(f"✅ Экипировано: {weapon['name']}!", show_alert=True)
    await show_inventory(callback)

@dp.callback_query(F.data.startswith("equip_armor_"))
async def equip_armor(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    armor_id = callback.data.replace("equip_armor_", "")
    
    if armor_id not in user.get("items_owned", []):
        await callback.answer("У тебя нет этой брони!")
        return
    
    user["inventory"]["armor"] = armor_id
    armor = ITEMS["armor"][armor_id]
    save_data()
    
    await callback.answer(f"✅ Экипировано: {armor['name']}!", show_alert=True)
    await show_inventory(callback)

# Рейтинг
@dp.callback_query(F.data == "top")
async def show_top(callback: CallbackQuery):
    # Фильтруем ботов
    real_users = {k: v for k, v in users_db.items() if not v.get("is_bot")}
    
    # Сортируем по винрейту и количеству побед
    sorted_users = sorted(
        real_users.items(),
        key=lambda x: (x[1]["wins"], x[1]["wins"] / max(x[1]["total_duels"], 1)),
        reverse=True
    )[:10]
    
    top_text = "🏆 ТОП-10 ДУЭЛЯНТОВ\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for idx, (user_id, user) in enumerate(sorted_users):
        medal = medals[idx] if idx < 3 else f"{idx + 1}."
        win_rate = (user["wins"] / user["total_duels"] * 100) if user["total_duels"] > 0 else 0
        
        top_text += (
            f"{medal} {CLASSES[user['class']]['emoji']} {user['username']}\n"
            f"   🏆 {user['wins']} побед | 📈 {win_rate:.0f}% винрейт\n\n"
        )
    
    await callback.message.edit_text(top_text, reply_markup=back_kb())

# Достижения
@dp.callback_query(F.data == "achievements")
async def show_achievements(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйся!")
        return
    
    ach_text = f"🏅 ДОСТИЖЕНИЯ\n\n"
    
    for ach_id, ach in ACHIEVEMENTS.items():
        unlocked = ach_id in user["achievements"]
        status = "✅" if unlocked else "🔒"
        
        ach_text += f"{status} {ach['emoji']} {ach['name']}\n"
        ach_text += f"   {ach['desc']}\n"
        if ach["reward"] > 0:
            ach_text += f"   💰 Награда: {ach['reward']} монет\n"
        ach_text += "\n"
    
    unlocked_count = len(user["achievements"])
    total_count = len(ACHIEVEMENTS)
    ach_text += f"📊 Разблокировано: {unlocked_count}/{total_count}"
    
    await callback.message.edit_text(ach_text, reply_markup=back_kb())

# Ежедневная награда
@dp.callback_query(F.data == "daily")
async def daily_reward(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйся!")
        return
    
    last_daily = user.get("last_daily")
    now = datetime.now()
    
    if last_daily:
        last_daily_date = datetime.fromisoformat(last_daily)
        if (now - last_daily_date).total_seconds() < 86400:
            time_left = 86400 - (now - last_daily_date).total_seconds()
            hours_left = int(time_left / 3600)
            await callback.answer(f"⏰ Следующая награда через {hours_left}ч", show_alert=True)
            return
    
    # Выдаем награду
    coins_reward = random.randint(50, 150)
    energy_reward = 1
    
    user["coins"] += coins_reward
    user["energy"] = min(5, user["energy"] + energy_reward)
    user["last_daily"] = now.isoformat()
    save_data()
    
    reward_text = (
        f"🎁 ЕЖЕДНЕВНАЯ НАГРАДА\n\n"
        f"💰 +{coins_reward} монет\n"
        f"⚡️ +{energy_reward} энергии\n\n"
        f"Возвращайся завтра за новой наградой!"
    )
    
    await callback.message.edit_text(reward_text, reply_markup=back_kb())

# Статистика
@dp.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйся!")
        return
    
    win_rate = (user["wins"] / user["total_duels"] * 100) if user["total_duels"] > 0 else 0
    avg_time = (user["total_answer_time"] / user["total_answers"]) if user["total_answers"] > 0 else 0
    avg_damage = (user["total_damage"] / user["total_duels"]) if user["total_duels"] > 0 else 0
    
    stats_text = (
        f"📊 ДЕТАЛЬНАЯ СТАТИСТИКА\n\n"
        f"{CLASSES[user['class']]['emoji']} {user['username']}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"⚔️ БОЕВАЯ СТАТИСТИКА:\n"
        f"🏆 Побед: {user['wins']}\n"
        f"💀 Поражений: {user['losses']}\n"
        f"📈 Винрейт: {win_rate:.1f}%\n"
        f"🔥 Текущая серия: {user['win_streak']}\n"
        f"⭐️ Лучшая серия: {user['best_streak']}\n"
        f"🎯 Всего дуэлей: {user['total_duels']}\n\n"
        f"⚡️ СКОРОСТЬ:\n"
        f"🏃 Лучшее время: {user['fastest_answer']:.2f}с\n"
        f"📊 Среднее время: {avg_time:.2f}с\n"
        f"🎯 Идеальных ответов: {user['perfect_answers']}\n\n"
        f"💥 УРОН:\n"
        f"⚔️ Всего урона: {user['total_damage']}\n"
        f"📊 Средний урон/дуэль: {avg_damage:.0f}\n\n"
        f"💰 ЭКОНОМИКА:\n"
        f"🪙 Монет: {user['coins']}\n"
        f"📦 Предметов: {len(user.get('items_owned', []))}\n"
        f"🏅 Достижений: {len(user['achievements'])}/{len(ACHIEVEMENTS)}"
    )
    
    await callback.message.edit_text(stats_text, reply_markup=back_kb())

# Возврат в главное меню
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users_db.get(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйся через /start")
        return
    
    update_energy(user_id)
    
    greeting = (
        f"🏛️ SHADOW DUEL ARENA\n\n"
        f"{CLASSES[user['class']]['emoji']} {user['username']}\n"
        f"🎚 Уровень: {user['level']}\n"
        f"⚡️ Энергия: {user['energy']}/5\n"
        f"💰 Монеты: {user['coins']}\n\n"
        f"Выбери действие:"
    )
    
    await callback.message.edit_text(greeting, reply_markup=main_menu_kb())

# ========== АДМИН ПАНЕЛЬ ==========

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У тебя нет доступа к админ-панели")
        return
    
    total_users = len([u for u in users_db.values() if not u.get("is_bot")])
    total_bots = len([u for u in users_db.values() if u.get("is_bot")])
    
    admin_text = (
        f"👑 АДМИН ПАНЕЛЬ\n\n"
        f"Управление ботом Shadow Duel Arena\n\n"
        f"👥 Игроков: {total_users}\n"
        f"🤖 Ботов: {total_bots}\n"
        f"⚔️ Активных дуэлей: {len(active_duels)}"
    )
    
    await message.answer(admin_text, reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    real_users = {k: v for k, v in users_db.items() if not v.get("is_bot")}
    
    total_users = len(real_users)
    total_duels = sum(u["total_duels"] for u in real_users.values())
    total_coins = sum(u["coins"] for u in real_users.values())
    total_wins = sum(u["wins"] for u in real_users.values())
    
    # Средний уровень
    avg_level = sum(u["level"] for u in real_users.values()) / total_users if total_users > 0 else 0
    
    # Самый активный игрок
    most_active = max(real_users.items(), key=lambda x: x[1]["total_duels"]) if real_users else None
    
    stats_text = (
        f"📊 СТАТИСТИКА БОТА\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"👥 Всего игроков: {total_users}\n"
        f"⚔️ Проведено дуэлей: {total_duels}\n"
        f"💰 Монет в обороте: {total_coins}\n"
        f"🏆 Всего побед: {total_wins}\n"
        f"🎚 Средний уровень: {avg_level:.1f}\n"
        f"🎮 Активных дуэлей: {len(active_duels)}\n\n"
    )
    
    if most_active:
        stats_text += (
            f"🔥 САМЫЙ АКТИВНЫЙ:\n"
            f"{CLASSES[most_active[1]['class']]['emoji']} {most_active[1]['username']}\n"
            f"Дуэлей: {most_active[1]['total_duels']}\n"
        )
    
    await callback.message.edit_text(stats_text, reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_top_users")
async def admin_top_users(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    real_users = {k: v for k, v in users_db.items() if not v.get("is_bot")}
    
    sorted_users = sorted(
        real_users.items(),
        key=lambda x: x[1]["coins"],
        reverse=True
    )[:15]
    
    top_text = "👑 ТОП-15 ПО МОНЕТАМ\n\n"
    
    for idx, (user_id, user) in enumerate(sorted_users, 1):
        top_text += (
            f"{idx}. {CLASSES[user['class']]['emoji']} {user['username']}\n"
            f"   💰 {user['coins']} | Ур.{user['level']} | 🏆 {user['wins']}\n\n"
        )
    
    await callback.message.edit_text(top_text, reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_reset_energy")
async def admin_reset_energy(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    count = 0
    for user_id, user in users_db.items():
        if not user.get("is_bot"):
            user["energy"] = 5
            user["last_energy_regen"] = datetime.now().isoformat()
            count += 1
    
    save_data()
    
    await callback.answer(f"✅ Энергия сброшена для {count} игроков!", show_alert=True)
    await admin_stats(callback)

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    await callback.message.edit_text(
        "📢 РАССЫЛКА\n\n"
        "Напиши сообщение, которое хочешь отправить всем игрокам.\n"
        "Отправь /cancel для отмены."
    )
    
    await state.set_state(AdminStates.broadcasting)

@dp.message(AdminStates.broadcasting)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ Рассылка отменена")
        await state.clear()
        return
    
    broadcast_text = message.text
    sent = 0
    failed = 0
    
    status_msg = await message.answer("📤 Отправка...")
    
    for user_id, user in users_db.items():
        if not user.get("is_bot"):
            try:
                await bot.send_message(
                    int(user_id),
                    f"📢 ОБЪЯВЛЕНИЕ ОТ АДМИНИСТРАЦИИ\n\n{broadcast_text}"
                )
                sent += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                failed += 1
                logger.error(f"Failed to send to {user_id}: {e}")
    
    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )
    
    await state.clear()

@dp.callback_query(F.data == "admin_give_coins")
async def admin_give_coins_menu(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    await callback.message.edit_text(
        "💰 ВЫДАТЬ МОНЕТЫ\n\n"
        "Формат: /give_coins [user_id] [amount]\n"
        "Пример: /give_coins 123456789 500\n\n"
        "Или выдай всем:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Выдать 100 монет всем", callback_data="admin_give_all_100")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
    )

@dp.callback_query(F.data == "admin_give_all_100")
async def admin_give_all_coins(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    count = 0
    for user_id, user in users_db.items():
        if not user.get("is_bot"):
            user["coins"] += 100
            count += 1
    
    save_data()
    
    await callback.answer(f"✅ Выдано 100 монет {count} игрокам!", show_alert=True)
    await callback.message.edit_text(
        f"💰 МОНЕТЫ ВЫДАНЫ\n\n"
        f"Получили награду: {count} игроков\n"
        f"Сумма: 100 монет каждому",
        reply_markup=admin_kb()
    )

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    await callback.message.edit_text(
        "👑 АДМИН ПАНЕЛЬ\n\n"
        "Управление ботом",
        reply_markup=admin_kb()
    )

@dp.message(Command("give_coins"))
async def cmd_give_coins(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Формат: /give_coins [user_id] [amount]")
            return
        
        target_user_id = parts[1]
        amount = int(parts[2])
        
        if target_user_id not in users_db:
            await message.answer("❌ Пользователь не найден")
            return
        
        users_db[target_user_id]["coins"] += amount
        save_data()
        
        await message.answer(
            f"✅ Выдано {amount} монет игроку {users_db[target_user_id]['username']}"
        )
        
        # Уведомляем игрока
        try:
            await bot.send_message(
                int(target_user_id),
                f"🎁 Тебе выдано {amount} монет от администрации!"
            )
        except:
            pass
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ========== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ==========

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "📖 СПРАВКА ПО БОТУ\n\n"
        "🎮 ОСНОВНЫЕ КОМАНДЫ:\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n\n"
        "⚔️ КАК ИГРАТЬ:\n"
        "1. Выбери класс персонажа\n"
        "2. Пройди тренировку\n"
        "3. Вызови на дуэль или найди соперника\n"
        "4. Отвечай на задания быстрее противника\n"
        "5. Побеждай и зарабатывай монеты!\n\n"
        "💡 СОВЕТЫ:\n"
        "- Отвечай быстро для критов и комбо\n"
        "- Покупай оружие и броню в магазине\n"
        "- Собирай ежедневные награды\n"
        "- Разблокируй достижения за бонусы\n\n"
        "🎯 Стань легендой арены!"
    )
    
    await message.answer(help_text, reply_markup=main_menu_kb())

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user_id = str(message.from_user.id)
    user = users_db.get(user_id)
    
    if not user:
        await message.answer("Сначала зарегистрируйся через /start")
        return
    
    update_energy(user_id)
    
    class_info = CLASSES[user["class"]]
    win_rate = (user["wins"] / user["total_duels"] * 100) if user["total_duels"] > 0 else 0
    
    profile_text = (
        f"{class_info['emoji']} {user['username'].upper()}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎚 Уровень: {user['level']}\n"
        f"❤️ HP: {user['hp']}/{user['max_hp']}\n"
        f"⚔️ Урон: {user['damage']}\n"
        f"💰 Монеты: {user['coins']}\n"
        f"⚡️ Энергия: {user['energy']}/5\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏆 Побед: {user['wins']}\n"
        f"📈 Винрейт: {win_rate:.1f}%\n"
        f"🔥 Серия: {user['win_streak']}"
    )
    
    await message.answer(profile_text, reply_markup=main_menu_kb())

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    real_users = {k: v for k, v in users_db.items() if not v.get("is_bot")}
    
    sorted_users = sorted(
        real_users.items(),
        key=lambda x: (x[1]["wins"], x[1]["wins"] / max(x[1]["total_duels"], 1)),
        reverse=True
    )[:10]
    
    top_text = "🏆 ТОП-10 ДУЭЛЯНТОВ\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for idx, (user_id, user) in enumerate(sorted_users):
        medal = medals[idx] if idx < 3 else f"{idx + 1}."
        win_rate = (user["wins"] / user["total_duels"] * 100) if user["total_duels"] > 0 else 0
        
        top_text += (
            f"{medal} {CLASSES[user['class']]['emoji']} {user['username']}\n"
            f"   🏆 {user['wins']} | 📈 {win_rate:.0f}%\n\n"
        )
    
    if not sorted_users:
        top_text += "Пока нет игроков в рейтинге!"
    
    await message.answer(top_text)

# ========== ЗАПУСК БОТА ==========

async def on_startup():
    load_data()
    logger.info("🚀 Shadow Duel Arena запущен!")
    logger.info(f"📊 Загружено пользователей: {len(users_db)}")

async def on_shutdown():
    save_data()
    logger.info("💾 Данные сохранены")
    logger.info("👋 Бот остановлен")

async def main():
    await on_startup()
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен вручную")
