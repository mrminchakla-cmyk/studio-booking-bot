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
# ========== КОНФИГУРАЦИЯ ==================
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "bookings.json"
YOUR_USER_ID = 1442416548
PAYMENT_DETAILS = "2204320394834453 Озон Банк"

# Участники студии
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

# Хранилище
questions_storage = {}
pending_bookings = {}

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

# ==========================================
# ========== СОСТОЯНИЯ =====================
# ==========================================

class BookingStates(StatesGroup):
    waiting_for_booking = State()
    waiting_for_question = State()
    waiting_for_answer = State()
    waiting_for_screenshot = State()

# ==========================================
# ========== БОТ ===========================
# ==========================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# ========== ФУНКЦИИ =======================
# ==========================================

def get_user_bookings(user_id):
    result = []
    for booking_id, booking_data in bookings.items():
        if f"|{user_id}" in booking_data:
            data = booking_data.split('|')[0]
            result.append([booking_id, data])
    return result

def add_booking(booking_id, full_booking, user_id):
    bookings[booking_id] = full_booking + f"|{user_id}"
    save_bookings(bookings)

def delete_booking(booking_id):
    if booking_id in bookings:
        del bookings[booking_id]
        save_bookings(bookings)
        return True
    return False

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

def calculate_deposit(booking_text, selected_service):
    total_price = 0
    if "Запись" in selected_service:
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', booking_text)
        if time_match:
            start_hour = int(time_match.group(1))
            end_hour = int(time_match.group(2))
            duration = end_hour - start_hour
            if duration > 0:
                total_price = duration * 500
    elif "ночь" in selected_service.lower():
        total_price = 3000
    elif "mix & master" in selected_service:
        total_price = 1500
    elif "трек под ключ" in selected_service:
        total_price = 3000
    elif "Клип" in selected_service:
        total_price = 5500
    elif "Запись для участников" in selected_service:
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', booking_text)
        if time_match:
            start_hour = int(time_match.group(1))
            end_hour = int(time_match.group(2))
            duration = end_hour - start_hour
            if duration > 0:
                total_price = duration * 500
    return total_price, int(total_price * 0.5)

def is_time_conflict(new_start, new_end, exclude_booking_id=None):
    for booking_id, booking_data in bookings.items():
        if exclude_booking_id and booking_id == exclude_booking_id:
            continue
        data = booking_data.split('|')[0]
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', data)
        if time_match:
            other_start = int(time_match.group(1))
            other_end = int(time_match.group(2))
            if new_start < other_end and new_end > other_start:
                return True
    return False

def get_booking_datetime(booking_text):
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
    if month < now.month or (month == now.month and day < now.day):
        year += 1
    return datetime.datetime(year, month, day, start_hour, 0, 0, tzinfo=pytz.timezone('Europe/Moscow'))

# ==========================================
# ========== КЛАВИАТУРЫ ====================
# ==========================================

def main_menu(user_id):
    buttons = []
    if user_id in studio_members_ids and user_id != YOUR_USER_ID:
        buttons = [
            [InlineKeyboardButton("🎙️ Забронировать", callback_data="book_member")],
            [InlineKeyboardButton("📋 Мои брони", callback_data="my_bookings")],
            [InlineKeyboardButton("📊 Все записи", callback_data="all_bookings")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("🎙️ Забронировать", callback_data="book")],
            [InlineKeyboardButton("📋 Мои брони", callback_data="my_bookings")],
            [InlineKeyboardButton("💰 Прайс", callback_data="prices")],
            [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
            [InlineKeyboardButton("❓ Вопросы", callback_data="questions")]
        ]
        if user_id in studio_members_ids:
            buttons.append([InlineKeyboardButton("📊 Все записи", callback_data="all_bookings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def services_menu(user_id):
    buttons = []
    if user_id in studio_members_ids and user_id != YOUR_USER_ID:
        buttons = [
            [InlineKeyboardButton("🎤 Запись", callback_data="service_record")],
            [InlineKeyboardButton("🌙 ночь на студии", callback_data="service_night")],
            [InlineKeyboardButton("🎙️ Запись для участников", callback_data="service_member")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("🎤 Запись", callback_data="service_record")],
            [InlineKeyboardButton("🌙 ночь на студии", callback_data="service_night")],
            [InlineKeyboardButton("🎧 mix & master", callback_data="service_master")],
            [InlineKeyboardButton("🎵 трек под ключ", callback_data="service_track")],
            [InlineKeyboardButton("🎬 Клип", callback_data="service_clip")]
        ]
        if user_id in studio_members_ids:
            buttons.append([InlineKeyboardButton("🎙️ Запись для участников", callback_data="service_member")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def info_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🏠 О нас", callback_data="about")],
        [InlineKeyboardButton("🎛️ Аппаратура", callback_data="equipment")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ])

def booking_actions(booking_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("⏳ +10 мин", callback_data=f"extend_{booking_id}_10")],
        [InlineKeyboardButton("⏳ +30 мин", callback_data=f"extend_{booking_id}_30")],
        [InlineKeyboardButton("⏳ +1 час", callback_data=f"extend_{booking_id}_60")],
        [InlineKeyboardButton("⏳ +2 часа", callback_data=f"extend_{booking_id}_120")],
        [InlineKeyboardButton("⏳ +3 часа", callback_data=f"extend_{booking_id}_180")],
        [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{booking_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ])

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ])

def payment_keyboard(booking_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f"pay_{booking_id}")],
        [InlineKeyboardButton("❌ Отменить бронь", callback_data=f"cancel_{booking_id}")]
    ])

def confirm_cancel(booking_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✅ Да, отменить", callback_data=f"confirm_cancel_{booking_id}")],
        [InlineKeyboardButton("❌ Нет, вернуться", callback_data=f"back_to_booking_{booking_id}")]
    ])

# ==========================================
# ========== /START ========================
# ==========================================

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    await message.answer(
        f"Привет, {name}! Очень рады, что ты выбрал именно нас. Надеюсь, ты будешь читать про бывшую и таблетки 😄",
        reply_markup=main_menu(user_id)
    )

# ==========================================
# ========== КНОПКИ ========================
# ==========================================

@dp.callback_query()
async def buttons(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = callback.data
    username = callback.from_user.username or callback.from_user.first_name

    # ===== ГЛАВНОЕ МЕНЮ =====
    if data == "main_menu":
        await callback.message.edit_text(
            f"Привет, {callback.from_user.first_name}! Очень рады, что ты выбрал именно нас. Надеюсь, ты будешь читать про бывшую и таблетки 😄",
            reply_markup=main_menu(user_id)
        )
        await callback.answer()
        return

    # ===== ЗАБРОНИРОВАТЬ =====
    if data == "book" or data == "book_member":
        await callback.message.edit_text(
            "Выбери услугу:",
            reply_markup=services_menu(user_id)
        )
        await callback.answer()
        return

    # ===== ПРАЙС =====
    if data == "prices":
        await callback.message.edit_text(
            "💰 ПРАЙС-ЛИСТ 💰\n\n"
            "🎤 Запись - 500р/час\n"
            "🌙 ночь на студии - 3000р\n"
            "🎧 mix & master - 1500р\n"
            "🎵 трек под ключ - 3000р\n"
            "🎬 Клип - 5500р",
            reply_markup=back_button()
        )
        await callback.answer()
        return

    # ===== ИНФОРМАЦИЯ =====
    if data == "info":
        await callback.message.edit_text(
            "Информация:",
            reply_markup=info_menu()
        )
        await callback.answer()
        return

    if data == "about":
        await callback.message.edit_text(
            "Современная студия звукозаписи.\n"
            "Находимся по адресу: г. Йошкар-Ола, ул. Первомайская, д. 115ж.\n\n"
            "TGK - @euphoria_session",
            reply_markup=back_button()
        )
        await callback.answer()
        return

    if data == "equipment":
        await callback.message.edit_text(
            "🎛️ АППАРАТУРА\n\n"
            "🎤 Микрофон: Neumann TLM 103\n"
            "🎧 Наушники: Beyerdynamic DT 900/700 Pro X\n"
            "🔊 Мониторы: KRK Rokit 5 G4\n"
            "🎚️ Звуковая карта: Apollo Twin DUO USB\n"
            "💻 ПК: Ryzen 5 1600, 16GB, SSD 512GB\n"
            "🧩 Плагины: SoundToys, Waves, FabFilter",
            reply_markup=back_button()
        )
        await callback.answer()
        return

    # ===== МОИ БРОНИ =====
    if data == "my_bookings":
        user_bookings = get_user_bookings(user_id)
        if not user_bookings:
            await callback.message.edit_text(
                "У вас нет активных броней.",
                reply_markup=back_button()
            )
        else:
            text = "📋 ВАШИ БРОНИ:\n\n"
            btns = []
            for booking_id, booking_data in user_bookings:
                date_match = re.search(r'(\d{2}\.\d{2})', booking_data)
                date_str = date_match.group(1) if date_match else "??.??"
                service_match = re.search(r',\s*(.+)$', booking_data)
                service_str = service_match.group(1).strip() if service_match else "Услуга"
                
                if "Запись" in service_str:
                    service_short = "🎤 Запись"
                elif "ночь" in service_str.lower():
                    service_short = "🌙 Ночь"
                elif "mix & master" in service_str:
                    service_short = "🎧 mix & master"
                elif "трек под ключ" in service_str:
                    service_short = "🎵 трек под ключ"
                elif "Клип" in service_str:
                    service_short = "🎬 Клип"
                elif "Запись для участников" in service_str:
                    service_short = "🎙️ Участник"
                else:
                    service_short = service_str[:15]
                
                btns.append([InlineKeyboardButton(
                    f"📅 {date_str} | {service_short}",
                    callback_data=f"booking_{booking_id}"
                )])
            btns.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
            )
        await callback.answer()
        return

    # ===== ВСЕ ЗАПИСИ =====
    if data == "all_bookings":
        if user_id not in studio_members_ids:
            await callback.answer("⛔ Нет доступа")
            return
        all_bookings = get_all_active_bookings()
        if not all_bookings:
            await callback.message.edit_text(
                "Нет актуальных броней.",
                reply_markup=back_button()
            )
        else:
            result = "📊 АКТУАЛЬНЫЕ БРОНИ:\n\n"
            for i, row in enumerate(all_bookings[:10], 1):
                result += f"{i}. {row[1]}\n\n"
            await callback.message.edit_text(
                result,
                reply_markup=back_button()
            )
        await callback.answer()
        return

    # ===== ВОПРОСЫ =====
    if data == "questions":
        await state.set_state(BookingStates.waiting_for_question)
        await callback.message.edit_text(
            "📝 Напишите ваш вопрос.",
            reply_markup=back_button()
        )
        await callback.answer()
        return

    # ===== ВЫБОР УСЛУГИ =====
    if data.startswith("service_"):
        services = {
            "service_record": "🎤 Запись - 500р",
            "service_night": "🌙 ночь на студии - 3000р",
            "service_master": "🎧 mix & master - 1500р",
            "service_track": "🎵 трек под ключ - 3000р",
            "service_clip": "🎬 Клип - 5500р",
            "service_member": "🎙️ Запись для участников"
        }
        selected = services.get(data)
        if not selected:
            await callback.answer("❌ Услуга не найдена")
            return
        if data == "service_member" and user_id not in studio_members_ids:
            await callback.answer("⛔ Только для участников")
            return
        
        await state.update_data(selected_service=selected)
        
        if data in ["service_record", "service_member"]:
            await callback.message.edit_text(
                f"✅ {selected}\n\nВведите: Имя, ДД.ММ, ЧЧ-ЧЧ\nПример: Анна, 11.08, 15-18",
                reply_markup=back_button()
            )
        elif data == "service_night":
            await callback.message.edit_text(
                f"✅ {selected}\n\nВведите: Имя, ДД.ММ-ДД.ММ\nПример: Анна, 11.08-12.08",
                reply_markup=back_button()
            )
        else:
            await callback.message.edit_text(
                f"✅ {selected}\n\n📩 Свяжитесь с @PAKAEM_BETM0",
                reply_markup=back_button()
            )
            await state.clear()
            await callback.answer()
            return
        
        await state.set_state(BookingStates.waiting_for_booking)
        await callback.answer()
        return

    # ===== БРОНЬ (управление) =====
    if data.startswith("booking_"):
        booking_id = data.replace("booking_", "")
        booking_data = None
        for bid, bdata in bookings.items():
            if bid == booking_id:
                booking_data = bdata.split('|')[0]
                break
        if not booking_data:
            await callback.answer("❌ Бронь не найдена")
            return
        await state.update_data(selected_booking_id=booking_id)
        await callback.message.edit_text(
            f"📋 {booking_data}\n\nВыберите действие:",
            reply_markup=booking_actions(booking_id)
        )
        await callback.answer()
        return

    # ===== ПРОДЛЕНИЕ =====
    if data.startswith("extend_"):
        parts = data.split("_")
        booking_id = parts[1]
        minutes = int(parts[2])
        if booking_id not in bookings:
            await callback.answer("❌ Бронь не найдена")
            return
        if f"|{user_id}" not in bookings[booking_id]:
            await callback.answer("⛔ Не ваша бронь")
            return
        
        old = bookings[booking_id].split('|')[0]
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', old)
        if not time_match:
            await callback.answer("❌ Ошибка времени")
            return
        start_hour = int(time_match.group(1))
        end_hour = int(time_match.group(2))
        new_end = end_hour + (minutes / 60)
        if new_end > 24:
            await callback.answer("❌ Нельзя продлить за сутки")
            return
        new_end = int(new_end)
        if new_end >= 24:
            await callback.answer("❌ Нельзя продлить за сутки")
            return
        if is_time_conflict(start_hour, new_end, booking_id):
            await callback.answer("❌ Время занято")
            return
        
        new_booking = re.sub(r'\d{1,2}-\d{1,2}', f"{start_hour}-{new_end}", old)
        bookings[booking_id] = new_booking + f"|{user_id}"
        save_bookings(bookings)
        
        await callback.message.edit_text(
            f"✅ Продлено на {minutes} мин!\n\n📋 {new_booking}",
            reply_markup=booking_actions(booking_id)
        )
        for member_id in studio_members_ids:
            try:
                await bot.send_message(member_id, f"⏳ ПРОДЛИЛИ БРОНЬ!\n\n{new_booking}\n👤 @{username}")
            except:
                pass
        await callback.answer()
        return

    # ===== ОТМЕНА =====
    if data.startswith("cancel_"):
        booking_id = data.replace("cancel_", "")
        await callback.message.edit_text(
            "❓ Отменить бронь?",
            reply_markup=confirm_cancel(booking_id)
        )
        await callback.answer()
        return

    if data.startswith("confirm_cancel_"):
        booking_id = data.replace("confirm_cancel_", "")
        if booking_id not in bookings:
            await callback.answer("❌ Бронь не найдена")
            return
        if f"|{user_id}" not in bookings[booking_id]:
            await callback.answer("⛔ Не ваша бронь")
            return
        booking_data = bookings[booking_id].split('|')[0]
        delete_booking(booking_id)
        await callback.message.edit_text(
            f"✅ Бронь отменена!\n\n{booking_data}",
            reply_markup=back_button()
        )
        for member_id in studio_members_ids:
            try:
                await bot.send_message(member_id, f"❌ ОТМЕНИЛИ БРОНЬ!\n\n{booking_data}\n👤 @{username}")
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
                f"📋 {booking_data}\n\nВыберите действие:",
                reply_markup=booking_actions(booking_id)
            )
        else:
            await callback.message.edit_text(
                "❌ Бронь не найдена",
                reply_markup=back_button()
            )
        await callback.answer()
        return

    # ===== ОПЛАТА =====
    if data.startswith("pay_"):
        booking_id = data.replace("pay_", "")
        if booking_id not in bookings:
            await callback.answer("❌ Бронь не найдена")
            return
        if user_id in studio_members_ids:
            await callback.answer("⛔ Участникам не нужно")
            return
        await state.update_data(pay_booking_id=booking_id)
        await state.set_state(BookingStates.waiting_for_screenshot)
        await callback.message.edit_text(
            "📸 Отправьте скриншот оплаты.",
            reply_markup=back_button()
        )
        await callback.answer()
        return

    # ===== НАЗАД =====
    if data == "back":
        await state.clear()
        await callback.message.edit_text(
            f"Привет, {callback.from_user.first_name}! Очень рады, что ты выбрал именно нас. Надеюсь, ты будешь читать про бывшую и таблетки 😄",
            reply_markup=main_menu(user_id)
        )
        await callback.answer()
        return

# ==========================================
# ========== ТЕКСТ =========================
# ==========================================

@dp.message()
async def text_messages(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text
    state_now = await state.get_state()

    # ===== ВОПРОС =====
    if state_now == BookingStates.waiting_for_question:
        question = text
        user_name = message.from_user.full_name or message.from_user.username or "Пользователь"
        user_id_sender = message.from_user.id
        username_sender = message.from_user.username or "нет_юзера"
        
        if user_id_sender not in questions_storage:
            questions_storage[user_id_sender] = {}
        questions_storage[user_id_sender][question] = None
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("📩 Ответить в ЛС", url=f"tg://user?id={user_id_sender}")],
            [InlineKeyboardButton("✍️ Ответить в боте", callback_data=f"answer_question_{user_id_sender}_{question}")]
        ])
        
        await bot.send_message(
            chat_id=YOUR_USER_ID,
            text=f"❓ НОВЫЙ ВОПРОС!\n\n👤 {user_name}\n🆔 {user_id_sender}\n📌 @{username_sender}\n\n📝 {question}",
            reply_markup=keyboard
        )
        await message.answer(
            "✅ Вопрос отправлен!",
            reply_markup=main_menu(user_id)
        )
        await state.clear()
        return

    # ===== ОТВЕТ АДМИНА =====
    if state_now == BookingStates.waiting_for_answer:
        if user_id != YOUR_USER_ID:
            await message.answer("⛔ Нет прав")
            await state.clear()
            return
        data = await state.get_data()
        target_user_id = data.get("target_user_id")
        question_text = data.get("question_text")
        if not target_user_id or not question_text:
            await message.answer("❌ Ошибка")
            await state.clear()
            return
        if target_user_id in questions_storage and question_text in questions_storage[target_user_id]:
            questions_storage[target_user_id][question_text] = text
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"✅ Ответ на вопрос:\n\n❓ {question_text}\n\n💬 {text}"
            )
            await message.answer("✅ Ответ отправлен!")
        except:
            await message.answer("❌ Не удалось отправить")
        await state.clear()
        return

    # ===== СКРИНШОТ =====
    if state_now == BookingStates.waiting_for_screenshot:
        if not message.photo:
            await message.answer("📸 Отправьте фото", reply_markup=back_button())
            return
        data = await state.get_data()
        booking_id = data.get("pay_booking_id")
        if not booking_id or booking_id not in bookings:
            await message.answer("❌ Бронь не найдена", reply_markup=main_menu(user_id))
            await state.clear()
            return
        booking_data = bookings[booking_id].split('|')[0]
        pending_bookings[booking_id] = {
            "user_id": user_id,
            "booking_data": booking_data,
            "photo_id": message.photo[-1].file_id
        }
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_yes_{booking_id}_{user_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"confirm_no_{booking_id}_{user_id}")]
        ])
        await bot.send_photo(
            chat_id=YOUR_USER_ID,
            photo=message.photo[-1].file_id,
            caption=f"📸 ОПЛАТА!\n\n👤 {user_id}\n📝 {booking_data}",
            reply_markup=keyboard
        )
        await message.answer(
            "✅ Скриншот отправлен!",
            reply_markup=main_menu(user_id)
        )
        await state.clear()
        return

    # ===== БРОНЬ =====
    if state_now == BookingStates.waiting_for_booking:
        data = await state.get_data()
        selected_service = data.get("selected_service")
        if not selected_service:
            await message.answer("❌ Ошибка", reply_markup=main_menu(user_id))
            await state.clear()
            return

        # Проверка формата
        if "Запись" in selected_service:
            if ',' not in text:
                await message.answer("❌ Формат: Имя, ДД.ММ, ЧЧ-ЧЧ", reply_markup=back_button())
                return
            time_match = re.search(r'(\d{1,2})-(\d{1,2})', text)
            if not time_match:
                await message.answer("❌ Формат времени: ЧЧ-ЧЧ", reply_markup=back_button())
                return
            start_hour = int(time_match.group(1))
            end_hour = int(time_match.group(2))
            duration = end_hour - start_hour
            if duration <= 0:
                await message.answer("❌ Время окончания позже", reply_markup=back_button())
                return
            if user_id in studio_members_ids and 12 <= start_hour < 22 and duration > 4:
                await message.answer("⏰ Максимум 4 часа днём", reply_markup=back_button())
                return
            if is_time_conflict(start_hour, end_hour):
                await message.answer("❌ Время занято", reply_markup=back_button())
                return
        elif "ночь" in selected_service.lower():
            if ',' not in text:
                await message.answer("❌ Формат: Имя, ДД.ММ-ДД.ММ", reply_markup=back_button())
                return
            date_match = re.search(r'(\d{2}\.\d{2})-(\d{2}\.\d{2})', text)
            if not date_match:
                await message.answer("❌ Формат дат: ДД.ММ-ДД.ММ", reply_markup=back_button())
                return
        else:
            await message.answer("📩 Свяжитесь с @PAKAEM_BETM0", reply_markup=main_menu(user_id))
            await state.clear()
            return

        # Сохраняем бронь
        full_booking = f"{text}, {selected_service}"
        booking_id = str(int(time.time()))
        add_booking(booking_id, full_booking, user_id)

        # Для участников
        if user_id in studio_members_ids:
            await message.answer(
                "✅ Бронь сохранена!",
                reply_markup=main_menu(user_id)
            )
            for member_id in studio_members_ids:
                try:
                    await bot.send_message(member_id, f"🔔 НОВАЯ БРОНЬ (УЧАСТНИК)!\n\n{full_booking}\n👤 @{username}")
                except:
                    pass
            await state.clear()
            return

        # Для клиентов - предоплата
        total_price, deposit = calculate_deposit(text, selected_service)
        booking_dt = get_booking_datetime(text)
        
        msg = f"💳 ПРЕДОПЛАТА 50%\n\n📝 {full_booking}\n"
        if total_price > 0:
            msg += f"💰 Полная стоимость: {total_price}р\n"
            msg += f"💳 Предоплата: {deposit}р\n\n"
        msg += f"💳 Реквизиты:\n{PAYMENT_DETAILS}\n\n"
        
        if booking_dt:
            hours_until = (booking_dt - datetime.datetime.now(pytz.timezone('Europe/Moscow'))).total_seconds() / 3600
            if hours_until < 4:
                msg += "⚠️ До брони <4 часов! При отмене предоплата НЕ возвращается!"
            else:
                msg += "⚠️ При отмене <4 часов предоплата НЕ возвращается"
        else:
            msg += "⚠️ При отмене <4 часов предоплата НЕ возвращается"

        await message.answer(
            msg,
            reply_markup=payment_keyboard(booking_id)
        )
        await message.answer(
            "✅ Бронь сохранена! После оплаты нажмите 'Я оплатил'.",
            reply_markup=main_menu(user_id)
        )
        for member_id in studio_members_ids:
            try:
                await bot.send_message(member_id, f"🔔 НОВАЯ БРОНЬ (ожидает оплаты)!\n\n{full_booking}\n👤 @{username}")
            except:
                pass
        await state.clear()
        return

# ==========================================
# ========== ПОДТВЕРЖДЕНИЕ ОПЛАТЫ =========
# ==========================================

@dp.callback_query(lambda c: c.data.startswith("confirm_yes_"))
async def confirm_pay(callback: CallbackQuery):
    parts = callback.data.split("_")
    booking_id = parts[2]
    client_id = int(parts[3])
    if booking_id in pending_bookings:
        del pending_bookings[booking_id]
    try:
        await bot.send_message(
            client_id,
            f"✅ БРОНЬ ПОДТВЕРЖДЕНА!\n\n📝 {bookings[booking_id].split('|')[0]}"
        )
    except:
        pass
    await callback.message.edit_text(
        f"✅ Подтверждено!\n\n{bookings[booking_id].split('|')[0]}",
        reply_markup=back_button()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("confirm_no_"))
async def decline_pay(callback: CallbackQuery):
    parts = callback.data.split("_")
    booking_id = parts[2]
    client_id = int(parts[3])
    booking_data = bookings[booking_id].split('|')[0] if booking_id in bookings else ""
    delete_booking(booking_id)
    if booking_id in pending_bookings:
        del pending_bookings[booking_id]
    try:
        await bot.send_message(
            client_id,
            f"❌ БРОНЬ ОТМЕНЕНА!\n\n📝 {booking_data}"
        )
    except:
        pass
    await callback.message.edit_text(
        f"❌ Отклонено!\n\n{booking_data}",
        reply_markup=back_button()
    )
    await callback.answer()

# ==========================================
# ========== ОТВЕТ НА ВОПРОС ==============
# ==========================================

@dp.callback_query(lambda c: c.data.startswith("answer_question_"))
async def answer_question(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != YOUR_USER_ID:
        await callback.answer("⛔ Нет прав")
        return
    parts = callback.data.split("_")
    target_user_id = int(parts[2])
    question_text = "_".join(parts[3:])
    await state.update_data(target_user_id=target_user_id, question_text=question_text)
    await state.set_state(BookingStates.waiting_for_answer)
    await callback.message.edit_text(
        f"✍️ Введите ответ на вопрос:\n\n❓ {question_text}",
        reply_markup=back_button()
    )
    await callback.answer()

# ==========================================
# ========== КОМАНДЫ =======================
# ==========================================

@dp.message(Command("booking"))
async def cmd_booking(message: types.Message):
    user_id = message.from_user.id
    user_bookings = get_user_bookings(user_id)
    if not user_bookings:
        await message.answer("📭 Нет броней")
        return
    text = "📋 ВАШИ БРОНИ:\n\n"
    for booking_id, booking_data in user_bookings:
        text += f"• {booking_data}\n\n"
    await message.answer(text)

@dp.message(Command("question"))
async def cmd_question(message: types.Message):
    user_id = message.from_user.id
    if user_id not in questions_storage:
        await message.answer("📭 Нет вопросов")
        return
    text = "📋 ВАШИ ВОПРОСЫ:\n\n"
    for q, a in questions_storage[user_id].items():
        text += f"❓ {q}\n"
        text += f"✅ {a}\n\n" if a else "⏳ Ожидает ответа...\n\n"
    await message.answer(text)

# ==========================================
# ========== МЕНЮ КОМАНД ===================
# ==========================================

async def set_commands():
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Главное меню"),
        types.BotCommand(command="booking", description="Мои брони"),
        types.BotCommand(command="question", description="Мои вопросы")
    ])

# ==========================================
# ========== ЗАПУСК ========================
# ==========================================

async def main():
    print("🤖 Бот запущен!")
    await set_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
