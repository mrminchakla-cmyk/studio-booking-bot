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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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
                                        f"⚠️ ТУПЫЕ НИГЕРЫ КЛИЕНТ ЗАЛЕЗ НА ТВОЮ БРОНЬ!\n\n{data}"
                                    )
                                )
                            except:
                                pass
                        return False
                    else:
                        return True
    return False

# ==========================================
# ========== INLINE-КЛАВИАТУРЫ =============
# ==========================================

def get_main_menu(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔥 Цены", callback_data="prices")],
        [InlineKeyboardButton(text="📅 Забронировать", callback_data="book")],
        [InlineKeyboardButton(text="📋 Мои брони", callback_data="my_bookings")],
        [InlineKeyboardButton(text="✨ Информация", callback_data="info")],
        [InlineKeyboardButton(text="❓ Вопросы", callback_data="questions")]
    ]
    if user_id in studio_members_ids:
        buttons.append([InlineKeyboardButton(text="📋 Все записи", callback_data="all_bookings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_services_menu(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🎤 1 час записи - 500р", callback_data="service_1hour")],
        [InlineKeyboardButton(text="🌙 Ночь на студии - 3000р", callback_data="service_night")],
        [InlineKeyboardButton(text="🎧 Сведение + мастеринг - 1500р", callback_data="service_master")],
        [InlineKeyboardButton(text="🎵 Трек под ключ - 3000р", callback_data="service_track")],
        [InlineKeyboardButton(text="🎬 Съемка клипа + монтаж - 5500р", callback_data="service_clip")]
    ]
    if user_id in studio_members_ids:
        buttons.append([InlineKeyboardButton(text="🎙️ Запись для участников", callback_data="service_member")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_info_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🎯 О нас", callback_data="about")],
        [InlineKeyboardButton(text="🎛️ Наша аппаратура", callback_data="equipment")],
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

# ==========================================
# ========== КОМАНДА /START ================
# ==========================================

@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    await message.answer(
        f"🔥 Привет, {first_name}! ✨ Очень рады, что ты выбрал именно нас. Надеюсь, ты будешь читать про бывшую и таблетки 😄💫",
        reply_markup=get_main_menu(user_id)
    )

# ==========================================
# ========== ОБРАБОТЧИК INLINE-КНОПОК ======
# ==========================================

@dp.callback_query()
async def handle_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    data = callback.data
    
    if data == "main_menu":
        await callback.message.edit_text(
            "🔥 Главное меню: 💫",
            reply_markup=get_main_menu(user_id)
        )
        await callback.answer()
        return
    
    if data == "prices":
        await callback.message.edit_text(
            "🔥 НАШИ ЦЕНЫ 🔥\n\n"
            "🎤 1 час записи - 500р (неограниченное кол-во человек)\n"
            "🌙 Ночь на студии - 3000р (с 22:00 до 10:00)\n"
            "🎧 Сведение + мастеринг - 1500р\n"
            "🎵 Трек под ключ - 3000р (Бит + текст + сведение + мастеринг)\n"
            "🎬 Съемка клипа + монтаж - 5500р",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    if data == "book":
        await callback.message.edit_text(
            "💫 Выбери услугу для бронирования: 🎯",
            reply_markup=get_services_menu(user_id)
        )
        await callback.answer()
        return
    
    if data == "info":
        await callback.message.edit_text(
            "✨ Раздел информации: 📋",
            reply_markup=get_info_menu()
        )
        await callback.answer()
        return
    
    if data == "about":
        await callback.message.edit_text(
            "🎯 О СТУДИИ 'БЫВШАЯ И ТАБЛЕТКИ' 🎯\n\n"
            "✨ Современная студия звукозаписи.\n"
            "📍 Находимся по адресу: г. Йошкар-Ола, ул. Первомайская, д. 115ж.\n\n"
            "📩 TGK - @euphoria_session\n\n"
            "🔥 Ждём вас! 🎤",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    if data == "equipment":
        await callback.message.edit_text(
            "🎛️ АППАРАТУРА СТУДИИ 🎛️\n\n"
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
                "📭 У вас нет активных броней. 💫",
                reply_markup=get_back_menu()
            )
        else:
            text = "📋 ВАШИ БРОНИ: 🔥\n\n"
            buttons = []
            for booking_id, booking_data in user_bookings:
                date_match = re.search(r'(\d{2}\.\d{2})', booking_data)
                date_str = date_match.group(1) if date_match else "??.??"
                service_match = re.search(r',\s*(.+)$', booking_data)
                service_str = service_match.group(1).strip() if service_match else "Услуга"
                
                if "1 час записи" in service_str:
                    service_short = "🎤 Запись"
                elif "Ночь" in service_str:
                    service_short = "🌙 Ночь"
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
                "📭 Нет актуальных броней. 💫",
                reply_markup=get_back_menu()
            )
        else:
            result = "📋 АКТУАЛЬНЫЕ БРОНИ (сегодня и позже): 🔥\n\n"
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
            "📝 Напишите ваш вопрос. ✨ Администратор свяжется с вами в ближайшее время. 💫\n\n"
            "Для отмены нажмите кнопку '🔙 Назад'.",
            reply_markup=get_back_menu()
        )
        await callback.answer()
        return
    
    if data.startswith("service_"):
        service_map = {
            "service_1hour": "🎤 1 час записи - 500р",
            "service_night": "🌙 Ночь на студии - 3000р",
            "service_master": "🎧 Сведение + мастеринг - 1500р",
            "service_track": "🎵 Трек под ключ - 3000р",
            "service_clip": "🎬 Съемка клипа + монтаж - 5500р",
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
        
        if data in ["service_1hour", "service_member"]:
            await callback.message.edit_text(
                f"✅ Выбрана услуга: {selected_service} 🔥\n\n"
                "📝 Введите данные брони в формате:\n"
                "Имя, Дата (ДД.ММ), Время (ЧЧ-ЧЧ)\n\n"
                "Пример: Анна, 11.08, 15-18 💫",
                reply_markup=get_back_menu()
            )
        elif data == "service_night":
            await callback.message.edit_text(
                f"✅ Выбрана услуга: {selected_service} 🌙\n\n"
                "📝 Введите данные брони в формате:\n"
                "Имя, Дата начала-Дата окончания (ДД.ММ-ДД.ММ)\n\n"
                "Пример: Анна, 11.08-12.08 💫",
                reply_markup=get_back_menu()
            )
        else:
            await callback.message.edit_text(
                f"✅ Выбрана услуга: {selected_service} 🎯\n\n"
                "📩 Для оформления этой услуги свяжитесь с нашим администратором:\n"
                "@PAKAEM_BETM0 🔥\n\n"
                "✨ Он уточнит все детали, сроки и стоимость.\n"
                "Напишите ему, пожалуйста, прямо сейчас! 👆",
                reply_markup=get_back_menu()
            )
            await state.clear()
            await callback.answer()
            return
        
        await state.set_state(BookingStates.waiting_for_booking)
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
            f"📋 Выбрана бронь: 🔥\n{booking_data}\n\nВыберите действие: 💫",
            reply_markup=get_booking_action_menu(booking_id)
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
            f"✅ Бронь продлена на {minutes} минут! ⏳\n\n📋 Обновлённая бронь: 🔥\n{new_booking}",
            reply_markup=get_booking_action_menu(booking_id)
        )
        
        for member_id in studio_members_ids:
            try:
                await bot.send_message(
                    member_id,
                    f"⏳ ТУПЫЕ НИГЕРЫ ПРОДЛИЛИ БРОНЬ! 🔥\n\n{new_booking}\n👤 Продлил: @{username}"
                )
            except:
                pass
        
        await callback.answer()
        return
    
    if data.startswith("cancel_"):
        booking_id = data.replace("cancel_", "")
        await callback.message.edit_text(
            "❓ Вы уверены, что хотите отменить эту бронь? ⚠️",
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
        delete_booking(booking_id)
        
        await callback.message.edit_text(
            f"✅ Бронь успешно отменена! ❌\n\n{booking_data}",
            reply_markup=get_back_menu()
        )
        
        for member_id in studio_members_ids:
            try:
                await bot.send_message(
                    member_id,
                    f"❌ ТУПЫЕ НИГЕРЫ ОТМЕНИЛИ БРОНЬ! 🔥\n\n{booking_data}\n👤 Отменил: @{username}"
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
                f"📋 Выбрана бронь: 🔥\n{booking_data}\n\nВыберите действие: 💫",
                reply_markup=get_booking_action_menu(booking_id)
            )
        else:
            await callback.message.edit_text(
                "❌ Бронь не найдена. 💫",
                reply_markup=get_back_menu()
            )
        await callback.answer()
        return
    
    if data == "back":
        await state.clear()
        await callback.message.edit_text(
            "🔥 Главное меню: 💫",
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
    
    if current_state == BookingStates.waiting_for_question:
        question_text = text
        user_name = message.from_user.full_name or message.from_user.username or "Пользователь"
        user_id_sender = message.from_user.id
        username_sender = message.from_user.username or "нет_юзера"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="📩 Ответить в ЛС",
                    url=f"tg://user?id={user_id_sender}"
                )]
            ]
        )
        
        await bot.send_message(
            chat_id=YOUR_USER_ID,
            text=f"❓ НОВЫЙ ВОПРОС! 🔥\n\n"
                 f"👤 От: {user_name}\n"
                 f"🆔 ID: {user_id_sender}\n"
                 f"📌 @{username_sender}\n\n"
                 f"📝 Вопрос: ✨\n{question_text}",
            reply_markup=keyboard
        )
        
        await message.answer(
            "✅ Ваш вопрос отправлен администратору. 💫 Ожидайте ответа! 🔥",
            reply_markup=get_main_menu(user_id)
        )
        await state.clear()
        return
    
    if current_state == BookingStates.waiting_for_booking:
        await save_booking(message, state)
        return

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
        await message.answer("❌ Ошибка. Выберите услугу заново. 💫", reply_markup=get_main_menu(user_id))
        await state.clear()
        return

    if selected_service in ["🎤 1 час записи - 500р", "🎙️ Запись для участников"]:
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', booking_text)
        if not time_match:
            await message.answer("❌ Неверный формат. Пример: Анна, 11.08, 15-18 💫", reply_markup=get_back_menu())
            return
        
        start_hour = int(time_match.group(1))
        end_hour = int(time_match.group(2))
        duration = end_hour - start_hour
        
        if duration <= 0:
            await message.answer("❌ Время окончания должно быть позже времени начала. ⏰", reply_markup=get_back_menu())
            return
        
        if user_id in studio_members_ids and 12 <= start_hour < 22 and duration > 4:
            await message.answer(
                f"⏰ В дневное время (12:00-22:00) участники могут бронировать максимум 4 часа. 🔥\n"
                f"Вы выбрали {duration} ч. Пожалуйста, сократите время. 💫",
                reply_markup=get_back_menu()
            )
            return
        
        if is_time_conflict(start_hour, end_hour, user_id):
            if user_id not in studio_members_ids:
                pass
            else:
                await message.answer("❌ Это время уже занято другой бронью. ⚡", reply_markup=get_back_menu())
                return
    
    else:
        date_match = re.search(r'(\d{2}\.\d{2})-(\d{2}\.\d{2})', booking_text)
        if not date_match:
            await message.answer("❌ Неверный формат. Пример: Анна, 11.08-12.08 💫", reply_markup=get_back_menu())
            return

    full_booking = f"{booking_text}, {selected_service}"
    booking_id = str(int(time.time()))
    add_booking(booking_id, full_booking, user_id)

    await message.answer(
        "✅ Бронь сохранена! 🔥 Спасибо, что выбрали нас ❤️💫",
        reply_markup=get_main_menu(user_id)
    )
    await state.clear()

    if user_id in studio_members_ids:
        member_name = studio_members.get(user_id, "Участник")
        who_booked = f"Участник: {member_name} (@{username})"
    else:
        who_booked = f"Клиент: {message.from_user.first_name} (@{username})"

    for member_id in studio_members_ids:
        try:
            await bot.send_message(
                member_id,
                f"🔔 ТУПЫЕ НИГЕРЫ БРОНЯТ! 🔥\n\n{full_booking}\n\n👤 {who_booked}"
            )
        except:
            pass

# ==========================================
# ========== ЗАПУСК ========================
# ==========================================

async def main():
    print("🔥 Бот запущен! 🔥")
    print(f"📂 Загружено {len(bookings)} броней")
    
    if shield is not None:
        dp.message.middleware(shield)
        print("🛡️ Антифлуд включен! ⚡")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
