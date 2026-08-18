import asyncio
import re
import time
import datetime
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand, BotCommandScopeDefault, ReplyKeyboardRemove
import pytz

# ==========================================
# ========== АНТИФЛУД =========
# ==========================================

try:
    from shieldgram import Shield
    shield = Shield()
    print("✅ Shieldgram (антифлуд) подключен!")
except ImportError:
    print("⚠️ Shieldgram не установлен. Установи: pip install shieldgram")
    shield = None

# ==========================================
# ========== КОНФИГУРАЦИЯ ==================
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "bookings.json"
YOUR_USER_ID = 1442416548

# Реквизиты для предоплаты
PAYMENT_DETAILS = "2204320394834453 Озон Банк"

# Хранилище вопросов-ответов
questions_storage = {}

# Хранилище броней, ожидающих подтверждения
pending_bookings = {}

studio_members = {
    1442416548: "Архив",
    8433779133: "Слендер",
    7134626698: "Прохор",
    6328109633: "Камарик",
    6942155383: "Продбайспин",
    6296483763: "Бор уз",
    1188400332: "Очкарик",
    6416588521: "Хардба",
    1141329171: "Лейзи",
    977716484: "Туторя",
    1155486938: "Кулер",
    5015081499: "Новый участник"
}
studio_members_ids = list(studio_members.keys())

# ==========================================
# ========== РАБОТА С ФАЙЛОМ ===============
# ==========================================

def load_bookings():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_bookings(bookings):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)

bookings = load_bookings()
print(f"📂 Загружено {len(bookings)} броней")

# ==========================================
# ========== СОСТОЯНИЯ FSM =================
# ==========================================

class BookingStates(StatesGroup):
    waiting_for_booking = State()
    waiting_for_booking_action = State()
    waiting_for_question = State()
    waiting_for_answer = State()
    waiting_for_screenshot = State()

# ==========================================
# ========== ИНИЦИАЛИЗАЦИЯ БОТА ============
# ==========================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# ========== ФУНКЦИИ ДЛЯ ДАННЫХ ============
# ==========================================

def get_all_bookings():
    result = []
    for booking_id, booking_data in bookings.items():
        parts = booking_data.split('|')
        data = parts[0] if parts else booking_data
        user_id = parts[1] if len(parts) > 1 else "0"
        result.append([booking_id, data, user_id])
    return result

def add_booking(booking_id: str, full_booking: str, user_id: int):
    bookings[booking_id] = full_booking + f"|{user_id}"
    save_bookings(bookings)

def delete_booking(booking_id: str) -> bool:
    if booking_id in bookings:
        del bookings[booking_id]
        save_bookings(bookings)
        return True
    return False

def get_user_bookings(user_id: int):
    result = []
    for booking_id, booking_data in bookings.items():
        if f"|{user_id}" in booking_data:
            data = booking_data.split('|')[0]
            result.append([booking_id, data])
    return result

def get_all_active_bookings():
    today = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d.%m")
    active = []
    for booking_id, booking_data in bookings.items():
        data = booking_data.split('|')[0]
        date_match = re.search(r'(\d{2}\.\d{2})', data)
        if date_match:
            try:
                b_day, b_month = map(int, date_match.group(1).split('.'))
                t_day, t_month = map(int, today.split('.'))
                if (b_month > t_month) or (b_month == t_month and b_day >= t_day):
                    user_id = booking_data.split('|')[1] if '|' in booking_data else "0"
                    active.append([booking_id, data, user_id])
            except:
                pass
    return active

def update_booking(booking_id: str, new_booking_text: str) -> bool:
    if booking_id in bookings:
        old_data = bookings[booking_id]
        user_id = old_data.split('|')[1] if '|' in old_data else "0"
        bookings[booking_id] = new_booking_text + f"|{user_id}"
        save_bookings(bookings)
        return True
    return False

def is_time_conflict(new_start: int, new_end: int, user_id: int, exclude_booking_id: str = None) -> bool:
    for booking_id, booking_data in bookings.items():
        if exclude_booking_id and booking_id == exclude_booking_id:
            continue
        
        data = booking_data.split('|')[0]
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', data)
        if time_match:
            other_start = int(time_match.group(1))
            other_end = int(time_match.group(2))
            
            if new_start < other_end and new_end > other_start:
                owner_id = int(booking_data.split('|')[1]) if '|' in booking_data else 0
                
                if user_id in studio_members_ids:
                    return True
                else:
                    if owner_id in studio_members_ids:
                        delete_booking(booking_id)
                        for member_id in studio_members_ids:
                            try:
                                bot.loop.create_task(
                                    bot.send_message(
                                        member_id,
                                        f"⚠️ КЛИЕНТ ЗАЛЕЗ НА ТВОЮ БРОНЬ!\n\n{data}"
                                    )
                                )
                            except:
                                pass
                        return False
                    else:
                        return True
    return False

# ==========================================
# ========== ФУНКЦИЯ ДЛЯ РАСЧЁТА ПРЕДОПЛАТЫ =
# ==========================================

def calculate_deposit(booking_text: str, selected_service: str) -> tuple:
    total_price = 0
    deposit = 0
    
    if "Запись" in selected_service or "запись" in selected_service:
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', booking_text)
        if time_match:
            start_hour = int(time_match.group(1))
            end_hour = int(time_match.group(2))
            duration = end_hour - start_hour
            if duration > 0:
                total_price = duration * 500
                deposit = int(total_price * 0.5)
    
    elif "ночь на студии" in selected_service.lower():
        total_price = 3000
        deposit = 1500
    
    elif "mix & master" in selected_service:
        total_price = 1500
        deposit = 750
    
    elif "трек под ключ" in selected_service:
        total_price = 3000
        deposit = 1500
    
    elif "Клип" in selected_service:
        total_price = 5500
        deposit = 2750
    
    elif "Запись для участников" in selected_service:
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', booking_text)
        if time_match:
            start_hour = int(time_match.group(1))
            end_hour = int(time_match.group(2))
            duration = end_hour - start_hour
            if duration > 0:
                total_price = duration * 500
                deposit = int(total_price * 0.5)
    
    return total_price, deposit

def get_booking_datetime(booking_text: str) -> datetime.datetime:
    date_match = re.search(r'(\d{2}\.\d{2})', booking_text)
    if not date_match:
        return None
    
    time_match = re.search(r'(\d{1,2})-(\d{1,2})', booking_text)
    if not time_match:
        return None
    
    day, month = map(int, date_match.group(1).split('.'))
    start_hour = int(time_match.group(1))
    
    now = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
    year = now.year
    
    if month < now.month:
        year += 1
    elif month == now.month and day < now.day:
        year += 1
    
    booking_datetime = datetime.datetime(year, month, day, start_hour, 0, 0, tzinfo=pytz.timezone('Europe/Moscow'))
    return booking_datetime

def is_deposit_refundable(booking_text: str) -> bool:
    booking_dt = get_booking_datetime(booking_text)
    if not booking_dt:
        return True
    
    now = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
    hours_until_booking = (booking_dt - now).total_seconds() / 3600
    
    if hours_until_booking < 4:
        return False
    return True

# ==========================================
# ========== INLINE-КЛАВИАТУРЫ =============
# ==========================================

def get_main_menu(user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    
    if user_id in studio_members_ids and user_id != YOUR_USER_ID:
        buttons.append([
            InlineKeyboardButton(text="🎙️ Забронировать", callback_data="book_member"),
            InlineKeyboardButton(text="📋 Мои брони", callback_data="my_bookings")
        ])
        buttons.append([
            InlineKeyboardButton(text="📊 Все записи", callback_data="all_bookings")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🎙️ Забронировать", callback_data="book"),
            InlineKeyboardButton(text="📋 Мои брони", callback_data="my_bookings")
        ])
        if user_id in studio_members_ids:
            buttons.append([
                InlineKeyboardButton(text="💰 Прайс", callback_data="prices"),
                InlineKeyboardButton(text="📊 Все записи", callback_data="all_bookings")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text="💰 Прайс", callback_data="prices")
            ])
        buttons.append([
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info"),
            InlineKeyboardButton(text="❓ Вопросы", callback_data="questions")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_services_menu(user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    
    # Для участников (кроме Архива) — ночь + запись для участников
    if user_id in studio_members_ids and user_id != YOUR_USER_ID:
        buttons = [
            [InlineKeyboardButton(text="🎤 Запись", callback_data="service_record")],
            [InlineKeyboardButton(text="🌙 ночь на студии", callback_data="service_night")],
            [InlineKeyboardButton(text="🎙️ Запись для участников", callback_data="service_member")]
        ]
    else:
        # Для клиентов и Архива — все услуги
        buttons = [
            [InlineKeyboardButton(text="🎤 Запись", callback_data="service_record")],
            [InlineKeyboardButton(text="🌙 ночь на студии", callback_data="service_night")],
            [InlineKeyboardButton(text="🎧 mix & master", callback_data="service_master")],
            [InlineKeyboardButton(text="🎵 трек под ключ", callback_data="service_track")],
            [InlineKeyboardButton(text="🎬 Клип", callback_data="service_clip")]
        ]
        if user_id in studio_members_ids:
            buttons.append([InlineKeyboardButton(text="🎙️ Запись для участников", callback_data="service_member")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_info_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🏠 О нас", callback_data="about")],
        [InlineKeyboardButton(text="🎛️ Аппаратура", callback_data="equipment")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_booking_action_menu(booking_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="⏳ +10 мин", callback_data=f"extend_{booking_id}_10")],
        [InlineKeyboardButton(text="⏳ +30 мин", callback_data=f"extend_{booking_id}_30")],
        [InlineKeyboardButton(text="⏳ +1 час", callback_data=f"extend_{booking_id}_60")],
        [InlineKeyboardButton(text="⏳ +2 часа", callback_data=f"extend_{booking_id}_120")],
        [InlineKeyboardButton(text="⏳ +3 часа", callback_data=f"extend_{booking_id}_180")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{booking_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="my_bookings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_menu(booking_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"confirm_cancel_{booking_id}")],
        [InlineKeyboardButton(text="❌ Нет, вернуться", callback_data=f"back_to_booking_{booking_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_keyboard(booking_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"pay_{booking_id}")],
        [InlineKeyboardButton(text="❌ Отменить бронь", callback_data=f"cancel_{booking_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==========================================
# ========== КОМАНДА /START ================
# ==========================================

@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    await message.answer(
        f"Привет, {first_name}! Очень рады, что ты выбрал именно нас. Надеюсь, ты будешь читать про бывшую и таблетки 😄",
        reply_markup=get_main_menu(user_id)
    )

# ==========================================
# ========== КОМАНДА /BOOKING ==============
# ==========================================

@dp.message(Command("booking"))
async def booking_command(message: types.Message):
    user_id = message.from_user.id
    user_bookings = get_user_bookings(user_id)
    
    if not user_bookings:
        await message.answer("📭 У вас нет активных броней.")
        return
    
    text = "📋 ВАШИ БРОНИ:\n\n"
    for booking_id, booking_data in user_bookings:
        text += f"• {booking_data}\n\n"
    
    await message.answer(text)

# ==========================================
# ========== КОМАНДА /QUESTION =============
# ==========================================

@dp.message(Command("question"))
async def question_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in questions_storage:
        await message.answer("📭 У вас нет вопросов.")
        return
    
    text = "📋 ВАШИ ВОПРОСЫ И ОТВЕТЫ:\n\n"
    for idx, (q, a) in enumerate(questions_storage[user_id].items(), 1):
        text += f"{idx}. ❓ {q}\n"
        if a:
            text += f"   ✅ Ответ: {a}\n\n"
        else:
            text += f"   ⏳ Ожидает ответа...\n\n"
    
    await message.answer(text)

# ==========================================
# ========== НАСТРОЙКА МЕНЮ КОМАНД =========
# ==========================================

async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="booking", description="Мои брони"),
        BotCommand(command="question", description="Мои вопросы и ответы")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

# ==========================================
# ========== ОБРАБОТЧИК INLINE-КНОПОК ======
# ==========================================

@dp.callback_query()
async def handle_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    data = callback.data
    
    # ===== ГЛАВНОЕ МЕНЮ =====
    if data == "main_menu":
        first_name = callback.from_user.first_name
        await callback.message.edit_text(
            f"Привет, {first_name}! Очень рады, что ты выбрал именно нас. Надеюсь, ты будешь читать про бывшую и таблетки 😄",
            reply_markup=get_main_menu(user_id)
        )
        await callback.answer()
        return
    
    if data == "book_member":
        await callback.message.edit_text(
            "Выбери услугу для бронирования:",
            reply_markup=get_services_menu(user_id)
        )
        await callback.answer()
        return
    
    if data == "prices":
        await callback.message.edit_text(
            "💰 ПРАЙС-ЛИСТ 💰\n\n"
            "🎤 Запись - 500р (неограниченное кол-во человек)\n"
            "🌙 ночь на студии - 3000р (с 22:00 до 10:00)\n"
            "🎧 mix & master - 1500р\n"
            "🎵 трек под ключ - 3000р\n"
            "🎬 Клип - 5500р",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    if data == "book":
        await callback.message.edit_text(
            "Выбери услугу для бронирования:",
            reply_markup=get_services_menu(user_id)
        )
        await callback.answer()
        return
    
    if data == "info":
        await callback.message.edit_text(
            "Информация:",
            reply_markup=get_info_menu()
        )
        await callback.answer()
        return
    
    if data == "about":
        await callback.message.edit_text(
            "Современная студия звукозаписи.\n"
            "Находимся по адресу: г. Йошкар-Ола, ул. Первомайская, д. 115ж.\n\n"
            "TGK - @euphoria_session\n\n"
            "Ждём вас! 🎤",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    if data == "equipment":
        await callback.message.edit_text(
            "🎛️ АППАРАТУРА СТУДИИ\n\n"
            "🎤 Микрофон:\n• Neumann TLM 103\n\n"
            "🎧 Наушники:\n• Beyerdynamic DT 900 Pro X (открытые)\n• Beyerdynamic DT 700 Pro X (закрытые)\n\n"
            "🔊 Мониторы:\n• KRK Rokit 5 G4\n\n"
            "🎚️ Звуковая карта:\n• Apollo Twin DUO USB\n\n"
            "💻 ПК:\n• AMD Ryzen 5 1600\n• 16 GB RAM\n• SSD 512 GB\n\n"
            "🧩 Плагины:\n• SoundToys\n• Waves\n• FabFilter\n• И другие\n\n"
            "📶 Быстрый Wi-Fi — если потребуется что-то докачать",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    if data == "my_bookings":
        user_bookings = get_user_bookings(user_id)
        if not user_bookings:
            await callback.message.edit_text(
                "📭 У вас нет активных броней.",
                reply_markup=get_back_menu()
            )
        else:
            text = "📋 ВАШИ БРОНИ:\n\n"
            buttons = []
            for booking_id, booking_data in user_bookings:
                date_match = re.search(r'(\d{2}\.\d{2})', booking_data)
                date_str = date_match.group(1) if date_match else "??.??"
                service_match = re.search(r',\s*(.+)$', booking_data)
                service_str = service_match.group(1).strip() if service_match else "Услуга"
                
                if "Запись" in service_str or "запись" in service_str:
                    service_short = "🎤 Запись"
                elif "ночь на студии" in service_str.lower():
                    service_short = "🌙 ночь на студии"
                elif "mix & master" in service_str:
                    service_short = "🎧 mix & master"
                elif "трек под ключ" in service_str:
                    service_short = "🎵 трек под ключ"
                elif "Клип" in service_str:
                    service_short = "🎬 Клип"
                elif "Запись для участников" in service_str:
                    service_short = "🎙️ Участник"
                else:
                    service_short = service_str[:15] + "..." if len(service_str) > 15 else service_str
                
                buttons.append([InlineKeyboardButton(
                    text=f"📅 {date_str} | {service_short}",
                    callback_data=f"booking_{booking_id}"
                )])
            
            buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
        await callback.answer()
        return
    
    if data == "all_bookings":
        if user_id not in studio_members_ids:
            await callback.answer("⛔ У вас нет доступа.")
            return
        all_bookings = get_all_active_bookings()
        if not all_bookings:
            await callback.message.edit_text(
                "📭 Нет актуальных броней.",
                reply_markup=get_back_menu()
            )
        else:
            result = "📊 АКТУАЛЬНЫЕ БРОНИ (сегодня и позже):\n\n"
            for i, row in enumerate(all_bookings[:10], 1):
                result += f"{i}. {row[1]}\n\n"
            await callback.message.edit_text(
                result,
                reply_markup=get_back_menu()
            )
        await callback.answer()
        return
    
    if data == "questions":
        await state.set_state(BookingStates.waiting_for_question)
        await callback.message.edit_text(
            "📝 Напишите ваш вопрос. Администратор свяжется с вами в ближайшее время.\n\n"
            "Для отмены нажмите кнопку 'Назад'.",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    if data.startswith("service_"):
        service_map = {
            "service_record": "🎤 Запись - 500р",
            "service_night": "🌙 ночь на студии - 3000р",
            "service_master": "🎧 mix & master - 1500р",
            "service_track": "🎵 трек под ключ - 3000р",
            "service_clip": "🎬 Клип - 5500р",
            "service_member": "🎙️ Запись для участников"
        }
        
        selected_service = service_map.get(data)
        if not selected_service:
            await callback.answer("❌ Услуга не найдена")
            return
        
        if data == "service_member" and user_id not in studio_members_ids:
            await callback.answer("⛔ Эта услуга только для участников студии.")
            return
        
        await state.update_data(selected_service=selected_service)
        
        if data in ["service_record", "service_member"]:
            await callback.message.edit_text(
                f"✅ Выбрана услуга: {selected_service}\n\n"
                "📝 Введите данные брони в формате:\n"
                "Имя, Дата (ДД.ММ), Время (ЧЧ-ЧЧ)\n\n"
                "Пример: Анна, 11.08, 15-18",
                reply_markup=get_back_menu()
            )
        elif data == "service_night":
            await callback.message.edit_text(
                f"✅ Выбрана услуга: {selected_service}\n\n"
                "📝 Введите данные брони в формате:\n"
                "Имя, Дата начала-Дата окончания (ДД.ММ-ДД.ММ)\n\n"
                "Пример: Анна, 11.08-12.08",
                reply_markup=get_back_menu()
            )
        else:
            await callback.message.edit_text(
                f"✅ Выбрана услуга: {selected_service}\n\n"
                "📩 Для оформления этой услуги свяжитесь с нашим администратором:\n"
                "@PAKAEM_BETM0\n\n"
                "Он уточнит все детали, сроки и стоимость.\n"
                "Напишите ему, пожалуйста, прямо сейчас! 👆",
                reply_markup=get_back_menu()
            )
            await state.clear()
            await callback.answer()
            return
        
        await state.set_state(BookingStates.waiting_for_booking)
        await callback.answer()
        return
    
    # === КЛИЕНТ ОТМЕНЯЕТ БРОНЬ ДО ОПЛАТЫ ===
    if data.startswith("cancel_") and user_id not in studio_members_ids:
        booking_id = data.replace("cancel_", "")
        
        if booking_id not in bookings:
            await callback.answer("❌ Бронь не найдена.")
            return
        
        if f"|{user_id}" not in bookings[booking_id]:
            await callback.answer("⛔ Это не ваша бронь.")
            return
        
        booking_data = bookings[booking_id].split('|')[0]
        delete_booking(booking_id)
        
        first_name = callback.from_user.first_name
        await callback.message.edit_text(
            f"❌ Бронь отменена!\n\n{booking_data}",
            reply_markup=get_main_menu(user_id)
        )
        
        for member_id in studio_members_ids:
            try:
                await bot.send_message(
                    member_id,
                    f"❌ КЛИЕНТ ОТМЕНИЛ БРОНЬ (до оплаты)!\n\n{booking_data}\n👤 Отменил: @{username}"
                )
            except:
                pass
        
        await callback.answer()
        return
    
    if data.startswith("booking_"):
        booking_id = data.replace("booking_", "")
        booking_data = None
        for bid, bdata in bookings.items():
            if bid == booking_id:
                booking_data = bdata.split('|')[0]
                break
        
        if not booking_data:
            await callback.answer("❌ Бронь не найдена.")
            return
        
        await state.update_data(selected_booking_id=booking_id)
        await callback.message.edit_text(
            f"📋 Выбрана бронь:\n{booking_data}\n\nВыберите действие:",
            reply_markup=get_booking_action_menu(booking_id)
        )
        await callback.answer()
        return
    
    # === КЛИЕНТ НАЖАЛ "Я ОПЛАТИЛ" ===
    if data.startswith("pay_"):
        booking_id = data.replace("pay_", "")
        
        if booking_id not in bookings:
            await callback.answer("❌ Бронь не найдена.")
            return
        
        if user_id in studio_members_ids:
            await callback.answer("⛔ Участникам не нужно подтверждать оплату.")
            return
        
        await state.update_data(pay_booking_id=booking_id)
        await state.set_state(BookingStates.waiting_for_screenshot)
        
        await callback.message.edit_text(
            "📸 Отправьте скриншот подтверждения оплаты.\n\n"
            "После проверки администратор подтвердит бронь.",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    # === АДМИН ПОДТВЕРЖДАЕТ ОПЛАТУ ===
    if data.startswith("confirm_yes_"):
        parts = data.split("_")
        booking_id = parts[2]
        client_id = int(parts[3])
        
        if booking_id in pending_bookings:
            del pending_bookings[booking_id]
        
        try:
            await bot.send_message(
                chat_id=client_id,
                text=f"✅ ВАША БРОНЬ ПОДТВЕРЖДЕНА!\n\n"
                     f"📝 Бронь: {bookings[booking_id].split('|')[0]}\n\n"
                     f"💰 Оплата получена. Ждём вас! 🎤"
            )
        except:
            pass
        
        await callback.message.edit_text(
            f"✅ Бронь подтверждена!\n\n{bookings[booking_id].split('|')[0]}",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    # === АДМИН ОТКЛОНЯЕТ ОПЛАТУ ===
    if data.startswith("confirm_no_"):
        parts = data.split("_")
        booking_id = parts[2]
        client_id = int(parts[3])
        
        booking_data = bookings[booking_id].split('|')[0] if booking_id in bookings else ""
        delete_booking(booking_id)
        
        if booking_id in pending_bookings:
            del pending_bookings[booking_id]
        
        try:
            await bot.send_message(
                chat_id=client_id,
                text=f"❌ БРОНЬ ОТМЕНЕНА!\n\n"
                     f"📝 Бронь: {booking_data}\n\n"
                     f"❗ Предоплата не прошла. Бронь отменена."
            )
        except:
            pass
        
        await callback.message.edit_text(
            f"❌ Бронь отклонена!\n\n{booking_data}",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    if data.startswith("extend_"):
        parts = data.split("_")
        booking_id = parts[1]
        minutes = int(parts[2])
        
        if booking_id not in bookings:
            await callback.answer("❌ Бронь не найдена.")
            return
        
        if f"|{user_id}" not in bookings[booking_id]:
            await callback.answer("⛔ Это не ваша бронь.")
            return
        
        old_booking = bookings[booking_id].split('|')[0]
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', old_booking)
        if not time_match:
            await callback.answer("❌ Не удалось определить время брони.")
            return
        
        start_hour = int(time_match.group(1))
        end_hour = int(time_match.group(2))
        new_end_hour = end_hour + (minutes / 60)
        
        if new_end_hour > 24:
            await callback.answer("❌ Нельзя продлить бронь за пределы суток.")
            return
        
        new_end_hour = int(new_end_hour)
        if new_end_hour >= 24:
            await callback.answer("❌ Нельзя продлить бронь за пределы суток.")
            return
        
        if is_time_conflict(start_hour, new_end_hour, user_id, booking_id):
            await callback.answer("❌ Это время уже занято другой бронью.")
            return
        
        new_booking = re.sub(r'\d{1,2}-\d{1,2}', f"{start_hour}-{new_end_hour}", old_booking)
        update_booking(booking_id, new_booking)
        
        await callback.message.edit_text(
            f"✅ Бронь продлена на {minutes} минут!\n\n📋 Обновлённая бронь:\n{new_booking}",
            reply_markup=get_booking_action_menu(booking_id)
        )
        
        for member_id in studio_members_ids:
            try:
                await bot.send_message(
                    member_id,
                    f"⏳ ПРОДЛИЛИ БРОНЬ!\n\n{new_booking}\n👤 Продлил: @{username}"
                )
            except:
                pass
        
        await callback.answer()
        return
    
    if data.startswith("cancel_") and user_id in studio_members_ids:
        booking_id = data.replace("cancel_", "")
        booking_data = bookings[booking_id].split('|')[0] if booking_id in bookings else ""
        
        refundable = is_deposit_refundable(booking_data)
        
        if not refundable:
            await callback.message.edit_text(
                f"❌ Предоплата НЕ ВОЗВРАЩАЕТСЯ!\n\n"
                f"До брони осталось меньше 4 часов.\n\n"
                f"{booking_data}\n\n"
                f"Вы уверены, что хотите отменить?",
                reply_markup=get_cancel_menu(booking_id)
            )
        else:
            await callback.message.edit_text(
                f"❓ Вы уверены, что хотите отменить эту бронь?\n\n"
                f"💳 Предоплата будет возвращена.",
                reply_markup=get_cancel_menu(booking_id)
            )
        await callback.answer()
        return
    
    if data.startswith("confirm_cancel_"):
        booking_id = data.replace("confirm_cancel_", "")
        
        if booking_id not in bookings:
            await callback.answer("❌ Бронь не найдена.")
            return
        
        if f"|{user_id}" not in bookings[booking_id]:
            await callback.answer("⛔ Это не ваша бронь.")
            return
        
        booking_data = bookings[booking_id].split('|')[0]
        refundable = is_deposit_refundable(booking_data)
        
        delete_booking(booking_id)
        
        if refundable:
            await callback.message.edit_text(
                f"✅ Бронь отменена! Предоплата будет возвращена.\n\n{booking_data}",
                reply_markup=get_back_menu()
            )
            cancel_text = f"❌ ОТМЕНИЛИ БРОНЬ (предоплата возвращена)!\n\n{booking_data}"
        else:
            await callback.message.edit_text(
                f"✅ Бронь отменена! Предоплата НЕ ВОЗВРАЩАЕТСЯ.\n\n{booking_data}",
                reply_markup=get_back_menu()
            )
            cancel_text = f"❌ ОТМЕНИЛИ БРОНЬ (предоплата НЕ возвращена)!\n\n{booking_data}"
        
        for member_id in studio_members_ids:
            try:
                await bot.send_message(
                    member_id,
                    f"{cancel_text}\n👤 Отменил: @{username}"
                )
            except:
                pass
        
        await callback.answer()
        return
    
    if data.startswith("back_to_booking_"):
        booking_id = data.replace("back_to_booking_", "")
        booking_data = None
        for bid, bdata in bookings.items():
            if bid == booking_id:
                booking_data = bdata.split('|')[0]
                break
        
        if booking_data:
            await callback.message.edit_text(
                f"📋 Выбрана бронь:\n{booking_data}\n\nВыберите действие:",
                reply_markup=get_booking_action_menu(booking_id)
            )
        else:
            await callback.message.edit_text(
                "❌ Бронь не найдена.",
                reply_markup=get_back_menu()
            )
        await callback.answer()
        return
    
    if data == "back":
        current_state = await state.get_state()
        if current_state == BookingStates.waiting_for_screenshot:
            data_state = await state.get_data()
            booking_id = data_state.get("pay_booking_id")
            
            if booking_id and booking_id in bookings:
                if f"|{user_id}" in bookings[booking_id]:
                    booking_data = bookings[booking_id].split('|')[0]
                    delete_booking(booking_id)
                    
                    first_name = callback.from_user.first_name
                    await callback.message.edit_text(
                        f"❌ Бронь отменена!\n\n{booking_data}",
                        reply_markup=get_main_menu(user_id)
                    )
                    
                    for member_id in studio_members_ids:
                        try:
                            await bot.send_message(
                                member_id,
                                f"❌ КЛИЕНТ ОТМЕНИЛ БРОНЬ (нажал 'Назад' при оплате)!\n\n{booking_data}\n👤 Отменил: @{username}"
                            )
                        except:
                            pass
                    
                    await state.clear()
                    await callback.answer()
                    return
        
        await state.clear()
        first_name = callback.from_user.first_name
        await callback.message.edit_text(
            f"Привет, {first_name}! Очень рады, что ты выбрал именно нас. Надеюсь, ты будешь читать про бывшую и таблетки 😄",
            reply_markup=get_main_menu(user_id)
        )
        await callback.answer()
        return

# ==========================================
# ========== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ =
# ==========================================

@dp.message()
async def handle_messages(message: types.Message, state: FSMContext):
    text = message.text
    user_id = message.from_user.id
    
    current_state = await state.get_state()
    
    # === ОБРАБОТКА СКРИНШОТА ===
    if current_state == BookingStates.waiting_for_screenshot:
        if not message.photo:
            await message.answer(
                "📸 Пожалуйста, отправьте скриншот (фото) подтверждения оплаты.",
                reply_markup=get_back_menu()
            )
            return
        
        data = await state.get_data()
        booking_id = data.get("pay_booking_id")
        
        if not booking_id or booking_id not in bookings:
            await message.answer("❌ Ошибка. Бронь не найдена.", reply_markup=get_main_menu(user_id))
            await state.clear()
            return
        
        booking_data = bookings[booking_id].split('|')[0]
        
        pending_bookings[booking_id] = {
            "user_id": user_id,
            "booking_data": booking_data,
            "photo_id": message.photo[-1].file_id
        }
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"confirm_yes_{booking_id}_{user_id}"
                )],
                [InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"confirm_no_{booking_id}_{user_id}"
                )]
            ]
        )
        
        await bot.send_photo(
            chat_id=YOUR_USER_ID,
            photo=message.photo[-1].file_id,
            caption=f"📸 НОВЫЙ СКРИНШОТ ОПЛАТЫ!\n\n"
                    f"👤 Клиент ID: {user_id}\n"
                    f"📝 Бронь: {booking_data}\n\n"
                    f"Подтвердите или отклоните оплату:",
            reply_markup=keyboard
        )
        
        await message.answer(
            "✅ Скриншот отправлен администратору на проверку.\n\n"
            "Ожидайте подтверждения брони!",
            reply_markup=get_main_menu(user_id)
        )
        await state.clear()
        return
    
    # === ОБРАБОТКА ВОПРОСА ===
    if current_state == BookingStates.waiting_for_question:
        question_text = text
        user_name = message.from_user.full_name or message.from_user.username or "Пользователь"
        user_id_sender = message.from_user.id
        username_sender = message.from_user.username or "нет_юзера"
        
        if user_id_sender not in questions_storage:
            questions_storage[user_id_sender] = {}
        questions_storage[user_id_sender][question_text] = None
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="📩 Ответить в ЛС",
                    url=f"tg://user?id={user_id_sender}"
                )],
                [InlineKeyboardButton(
                    text="✍️ Ответить в боте",
                    callback_data=f"answer_question_{user_id_sender}_{question_text}"
                )]
            ]
        )
        
        await bot.send_message(
            chat_id=YOUR_USER_ID,
            text=f"❓ НОВЫЙ ВОПРОС!\n\n"
                 f"👤 От: {user_name}\n"
                 f"🆔 ID: {user_id_sender}\n"
                 f"📌 @{username_sender}\n\n"
                 f"📝 Вопрос:\n{question_text}",
            reply_markup=keyboard
        )
        
        await message.answer(
            "✅ Ваш вопрос отправлен администратору. Ожидайте ответа!",
            reply_markup=get_main_menu(user_id)
        )
        await state.clear()
        return
    
    # === ОТВЕТ НА ВОПРОС (админ) ===
    if current_state == BookingStates.waiting_for_answer:
        if user_id != YOUR_USER_ID:
            await message.answer("⛔ У вас нет прав.")
            await state.clear()
            return
        
        data = await state.get_data()
        target_user_id = data.get("target_user_id")
        question_text = data.get("question_text")
        
        if not target_user_id or not question_text:
            await message.answer("❌ Ошибка. Попробуйте снова.")
            await state.clear()
            return
        
        if target_user_id in questions_storage and question_text in questions_storage[target_user_id]:
            questions_storage[target_user_id][question_text] = text
        
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"✅ Ответ на ваш вопрос:\n\n"
                     f"❓ Вопрос: {question_text}\n\n"
                     f"💬 Ответ: {text}"
            )
            await message.answer("✅ Ответ отправлен пользователю!")
        except:
            await message.answer("❌ Не удалось отправить ответ пользователю.")
        
        await state.clear()
        return
    
    # === ОБРАБОТКА БРОНИ ===
    if current_state == BookingStates.waiting_for_booking:
        await save_booking(message, state)
        return

# ==========================================
# ========== ОБРАБОТКА CALLBACK ДЛЯ ОТВЕТА =
# ==========================================

@dp.callback_query(lambda c: c.data.startswith("answer_question_"))
async def answer_question_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != YOUR_USER_ID:
        await callback.answer("⛔ У вас нет прав.")
        return
    
    parts = callback.data.split("_")
    target_user_id = int(parts[2])
    question_text = "_".join(parts[3:])
    
    await state.update_data(target_user_id=target_user_id, question_text=question_text)
    await state.set_state(BookingStates.waiting_for_answer)
    
    await callback.message.edit_text(
        f"✍️ Введите ваш ответ на вопрос:\n\n"
        f"❓ {question_text}\n\n"
        f"👤 Пользователь ID: {target_user_id}",
        reply_markup=get_back_menu()
    )
    await callback.answer()

# ==========================================
# ========== СОХРАНЕНИЕ БРОНИ ==============
# ==========================================

async def save_booking(message: types.Message, state: FSMContext):
    booking_text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    data = await state.get_data()
    selected_service = data.get("selected_service")

    if not selected_service:
        await message.answer("❌ Ошибка. Выберите услугу заново.", reply_markup=get_main_menu(user_id))
        await state.clear()
        return

    # ===== ПРОВЕРКА ФОРМАТА ДЛЯ ЗАПИСИ =====
    if "Запись" in selected_service or "запись" in selected_service:
        if ',' not in booking_text:
            await message.answer(
                "❌ НЕВЕРНЫЙ ФОРМАТ!\n\n"
                "Для ЗАПИСИ нужно писать строго:\n"
                "Имя, ДД.ММ, ЧЧ-ЧЧ\n\n"
                "Пример: Анна, 11.08, 15-18",
                reply_markup=get_back_menu()
            )
            return
        
        date_match = re.search(r'(\d{2}\.\d{2})', booking_text)
        if not date_match:
            await message.answer(
                "❌ НЕВЕРНЫЙ ФОРМАТ ДАТЫ!\n\n"
                "Дата должна быть в формате ДД.ММ\n"
                "Пример: 11.08",
                reply_markup=get_back_menu()
            )
            return
        
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', booking_text)
        if not time_match:
            await message.answer(
                "❌ НЕВЕРНЫЙ ФОРМАТ ВРЕМЕНИ!\n\n"
                "Время должно быть в формате ЧЧ-ЧЧ\n"
                "Пример: 15-18",
                reply_markup=get_back_menu()
            )
            return
        
        start_hour = int(time_match.group(1))
        end_hour = int(time_match.group(2))
        duration = end_hour - start_hour
        
        if start_hour < 0 or start_hour > 24 or end_hour < 0 or end_hour > 24:
            await message.answer(
                "❌ НЕВЕРНОЕ ВРЕМЯ!\n\n"
                "Часы должны быть от 0 до 24.\n"
                "Пример: 15-18",
                reply_markup=get_back_menu()
            )
            return
        
        if duration <= 0:
            await message.answer(
                "❌ ВРЕМЯ ОКОНЧАНИЯ ДОЛЖНО БЫТЬ ПОЗЖЕ ВРЕМЕНИ НАЧАЛА!\n\n"
                "Пример: 15-18",
                reply_markup=get_back_menu()
            )
            return
        
        if user_id in studio_members_ids and 12 <= start_hour < 22 and duration > 4:
            await message.answer(
                f"⏰ В дневное время (12:00-22:00) участники могут бронировать максимум 4 часа.\n"
                f"Вы выбрали {duration} ч. Пожалуйста, сократите время.",
                reply_markup=get_back_menu()
            )
            return
        
        if is_time_conflict(start_hour, end_hour, user_id):
            await message.answer("❌ Это время уже занято другой бронью.", reply_markup=get_back_menu())
            return
    
    # ===== ПРОВЕРКА ФОРМАТА ДЛЯ НОЧИ =====
    elif "ночь" in selected_service.lower():
        if ',' not in booking_text:
            await message.answer(
                "❌ НЕВЕРНЫЙ ФОРМАТ!\n\n"
                "Для НОЧИ нужно писать строго:\n"
                "Имя, ДД.ММ-ДД.ММ\n\n"
                "Пример: Анна, 11.08-12.08",
                reply_markup=get_back_menu()
            )
            return
        
        date_match = re.search(r'(\d{2}\.\d{2})-(\d{2}\.\d{2})', booking_text)
        if not date_match:
            await message.answer(
                "❌ НЕВЕРНЫЙ ФОРМАТ ДАТ!\n\n"
                "Даты должны быть в формате ДД.ММ-ДД.ММ\n"
                "Пример: 11.08-12.08",
                reply_markup=get_back_menu()
            )
            return
    
    # ===== ДЛЯ ДРУГИХ УСЛУГ =====
    else:
        await message.answer(
            "📩 Для этой услуги свяжитесь с администратором:\n"
            "@PAKAEM_BETM0\n\n"
            "Он уточнит все детали.",
            reply_markup=get_back_menu()
        )
        await state.clear()
        return

    # ===== СОХРАНЕНИЕ БРОНИ =====
    full_booking = f"{booking_text}, {selected_service}"
    booking_id = str(int(time.time()))
    add_booking(booking_id, full_booking, user_id)

    # ===== ДЛЯ УЧАСТНИКОВ — СОХРАНЯЕМ БЕЗ ПРЕДОПЛАТЫ =====
    if user_id in studio_members_ids:
        await message.answer(
            "✅ Бронь сохранена!",
            reply_markup=get_main_menu(user_id)
        )
        await state.clear()

        for member_id in studio_members_ids:
            try:
                await bot.send_message(
                    member_id,
                    f"🔔 НОВАЯ БРОНЬ (УЧАСТНИК)!\n\n{full_booking}\n👤 {studio_members.get(user_id, 'Участник')} (@{username})"
                )
            except:
                pass
        return

    # ===== ДЛЯ КЛИЕНТОВ — ПРЕДОПЛАТА =====
    total_price, deposit = calculate_deposit(booking_text, selected_service)
    booking_dt = get_booking_datetime(booking_text)
    
    deposit_text = f"💳 ДЛЯ ПОДТВЕРЖДЕНИЯ БРОНИ НЕОБХОДИМА ПРЕДОПЛАТА 50%\n\n"
    deposit_text += f"📝 Бронь: {full_booking}\n"
    if total_price > 0:
        deposit_text += f"💰 Полная стоимость: {total_price}р\n"
        deposit_text += f"💳 Предоплата (50%): {deposit}р\n\n"
    deposit_text += f"💳 Реквизиты для оплаты:\n{PAYMENT_DETAILS}\n\n"
    
    if booking_dt:
        hours_until = (booking_dt - datetime.datetime.now(pytz.timezone('Europe/Moscow'))).total_seconds() / 3600
        if hours_until < 4:
            deposit_text += f"⚠️ ВНИМАНИЕ! До брони осталось менее 4 часов.\n❌ При отмене предоплата НЕ ВОЗВРАЩАЕТСЯ!"
        else:
            deposit_text += f"⚠️ Предоплата НЕ ВОЗВРАЩАЕТСЯ при отмене менее чем за 4 часа до брони."
    else:
        deposit_text += f"⚠️ Предоплата НЕ ВОЗВРАЩАЕТСЯ при отмене менее чем за 4 часа до брони."

    await message.answer(
        deposit_text,
        reply_markup=get_payment_keyboard(booking_id)
    )

    await message.answer(
        "✅ Бронь сохранена! После оплаты нажмите 'Я оплатил' и отправьте скриншот.",
        reply_markup=get_main_menu(user_id)
    )
    await state.clear()

    for member_id in studio_members_ids:
        try:
            await bot.send_message(
                member_id,
                f"🔔 НОВАЯ БРОНЬ (ожидает оплаты)!\n\n{full_booking}\n👤 Клиент: {message.from_user.first_name} (@{username})"
            )
        except:
            pass

# ==========================================
# ========== ЗАПУСК ========================
# ==========================================

async def main():
    print("🤖 Бот запущен!")
    print(f"📂 Загружено {len(bookings)} броней")
    
    await set_bot_commands()
    print("✅ Меню команд настроено!")
    
    if shield is not None:
        dp.message.middleware(shield)
        print("🛡️ Антифлуд включен!")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
