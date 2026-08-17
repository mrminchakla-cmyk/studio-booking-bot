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
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import pytz

# ==========================================
# ========== КОНФИГУРАЦИЯ ==================
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "-1004374514040"          # ID общего чата студии
YOUR_USER_ID = 1442416548           # Твой Telegram ID (Архив)
DATA_FILE = "bookings.json"         # Файл для хранения броней

# Список участников студии (ID + имена)
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
    """Загружает брони из файла при запуске бота"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_bookings(bookings):
    """Сохраняет брони в файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)

# Загружаем брони при старте
bookings = load_bookings()
print(f"📂 Загружено {len(bookings)} броней из файла")

# ==========================================
# ========== СОСТОЯНИЯ FSM =================
# ==========================================

class BookingStates(StatesGroup):
    waiting_for_booking = State()
    waiting_for_extend = State()

# ==========================================
# ========== ИНИЦИАЛИЗАЦИЯ БОТА ============
# ==========================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ===
# ==========================================

def get_all_bookings():
    """Возвращает все брони в виде списка для отображения"""
    result = []
    for booking_id, booking_data in bookings.items():
        # Формат: "Имя, Дата, Время, Услуга|user_id"
        parts = booking_data.split('|')
        data = parts[0] if parts else booking_data
        user_id = parts[1] if len(parts) > 1 else "0"
        
        name_match = re.search(r'^([^,]+)', data)
        client_name = name_match.group(1).strip() if name_match else "Не указан"
        
        service_match = re.search(r',\s*(.+)$', data)
        service = service_match.group(1).strip() if service_match else "Не указана"
        
        now = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%Y-%m-%d %H:%M")
        result.append([booking_id, now, client_name, service, data, user_id])
    return result

def add_booking(booking_id: str, full_booking: str, user_id: int):
    """Добавляет бронь в словарь и сохраняет в файл"""
    bookings[booking_id] = full_booking + f"|{user_id}"
    save_bookings(bookings)

def delete_booking(booking_id: str) -> bool:
    """Удаляет бронь"""
    if booking_id in bookings:
        del bookings[booking_id]
        save_bookings(bookings)
        return True
    return False

def get_user_bookings(user_id: int):
    """Возвращает брони пользователя"""
    result = []
    for booking_id, booking_data in bookings.items():
        if f"|{user_id}" in booking_data:
            data = booking_data.split('|')[0]
            result.append([booking_id, "", "", "", data, str(user_id)])
    return result

def get_all_active_bookings():
    """Возвращает актуальные брони (сегодня и позже)"""
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
                    active.append([booking_id, "", "", "", data, user_id])
            except:
                pass
    return active

def update_booking(booking_id: str, new_booking_text: str) -> bool:
    """Обновляет бронь"""
    if booking_id in bookings:
        old_data = bookings[booking_id]
        user_id = old_data.split('|')[1] if '|' in old_data else "0"
        bookings[booking_id] = new_booking_text + f"|{user_id}"
        save_bookings(bookings)
        return True
    return False

def is_time_conflict(new_start: int, new_end: int, exclude_booking_id: str = None) -> bool:
    """Проверяет пересечение времени с другими бронями"""
    for booking_id, booking_data in bookings.items():
        if exclude_booking_id and booking_id == exclude_booking_id:
            continue
        data = booking_data.split('|')[0]
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', data)
        if time_match:
            other_start = int(time_match.group(1))
            other_end = int(time_match.group(2))
            if not (new_end <= other_start or new_start >= other_end):
                return True
    return False

# ==========================================
# ========== КЛАВИАТУРЫ ====================
# ==========================================

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="💰 Цены")],
        [KeyboardButton(text="📅 Забронировать")],
        [KeyboardButton(text="📋 Мои брони")],
        [KeyboardButton(text="ℹ️ Информация")]
    ]
    if user_id in studio_members_ids:
        keyboard.append([KeyboardButton(text="📋 Все записи")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_services_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🎤 1 час записи - 500р")],
        [KeyboardButton(text="🌙 Ночь на студии - 3000р")],
        [KeyboardButton(text="🎧 Сведение + мастеринг - 1500р")],
        [KeyboardButton(text="🎵 Трек под ключ - 3000р")],
        [KeyboardButton(text="🎬 Съемка клипа + монтаж - 5500р")],
        [KeyboardButton(text="🔙 Назад в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_info_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📖 О нас")],
        [KeyboardButton(text="🎛️ Наша аппаратура")],
        [KeyboardButton(text="🔙 Назад в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_booking_actions(booking_id: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=f"⏳ Продлить {booking_id}")],
        [KeyboardButton(text=f"❌ Отменить {booking_id}")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ==========================================
# ========== КОМАНДА /START ================
# ==========================================

@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    await message.answer(
        f"Привет, {first_name}! Очень рады, что ты выбрал именно нас, чтобы читать про бывшую и таблетки 😄",
        reply_markup=get_main_keyboard(user_id)
    )

# ==========================================
# ========== ОБРАБОТЧИК КНОПОК =============
# ==========================================

@dp.message(lambda message: message.text and not message.text.startswith('/'))
async def handle_messages(message: types.Message, state: FSMContext):
    text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    if text == "💰 Цены":
        await message.answer(
            "💲 Наши цены 💲\n\n"
            "• 1 час записи - 500р (неограниченное кол-во человек)\n"
            "• Ночь на студии - 3000р (с 22:00 до 10:00)\n"
            "• Сведение + мастеринг - 1500р\n"
            "• Трек под ключ - 3000р (Бит + текст + сведение + мастеринг)\n"
            "• Съемка клипа + монтаж - 5500р\n\n"
            "Для бронирования нажми кнопку '📅 Забронировать'"
        )

    elif text == "📅 Забронировать":
        await message.answer(
            "💲 Выбери услугу для бронирования 💲\n\nНажми на кнопку с нужной услугой:",
            reply_markup=get_services_keyboard()
        )

    elif text in ["🎤 1 час записи - 500р", "🌙 Ночь на студии - 3000р"]:
        await state.update_data(selected_service=text)
        if text == "🎤 1 час записи - 500р":
            await message.answer(
                f"✅ Выбрана услуга: {text}\n\n"
                "Введите данные брони в формате:\n"
                "Имя, Дата (ДД.ММ), Время (ЧЧ-ЧЧ)\n\n"
                "Пример: Анна, 31.12, 15-18"
            )
        else:
            await message.answer(
                f"✅ Выбрана услуга: {text}\n\n"
                "Введите данные брони в формате:\n"
                "Имя, Дата начала-Дата окончания (ДД.ММ-ДД.ММ)\n\n"
                "Пример: Анна, 31.12-01.01"
            )
        await state.set_state(BookingStates.waiting_for_booking)

    elif text in ["🎧 Сведение + мастеринг - 1500р", "🎵 Трек под ключ - 3000р", "🎬 Съемка клипа + монтаж - 5500р"]:
        await message.answer(
            f"✅ Выбрана услуга: {text}\n\n"
            "📞 Для оформления этой услуги свяжитесь с нашим администратором:\n"
            "@PAKAEM_BETM0\n\n"
            "Он уточнит все детали, сроки и стоимость.\n"
            "Напишите ему, пожалуйста, прямо сейчас! 👆"
        )
        await message.answer("Главное меню:", reply_markup=get_main_keyboard(user_id))

    elif text == "📋 Мои брони":
        user_bookings = get_user_bookings(user_id)
        if not user_bookings:
            await message.answer("📭 У вас нет активных броней.")
        else:
            for row in user_bookings:
                booking_id = row[0]
                booking_data = row[4]
                await message.answer(
                    f"📋 Ваша бронь:\n{booking_data}",
                    reply_markup=get_booking_actions(booking_id)
                )

    elif text == "ℹ️ Информация":
        await message.answer(
            "📋 Раздел информации:\n\nВыберите, что вас интересует:",
            reply_markup=get_info_keyboard()
        )

    elif text == "📖 О нас":
        await message.answer(
            "🎵 О студии 'Бывшая и таблетки'\n\n"
            "Современная студия звукозаписи.\n"
            "Находимся по адресу: г. Йошкар-Ола, ул. Первомайская, д. 115ж.\n\n"
            "📍 TGK - @euphoria_session\n\n"
            "Ждём вас! 🎧"
        )

    elif text == "🎛️ Наша аппаратура":
        await message.answer(
            "🎛️ АППАРАТУРА СТУДИИ\n\n"
            "🎤 Микрофон:\n• Neumann TLM 103\n\n"
            "🎧 Наушники:\n• Beyerdynamic DT 900 Pro X (открытые)\n• Beyerdynamic DT 700 Pro X (закрытые)\n\n"
            "🔊 Мониторы:\n• KRK Rokit 5 G4\n\n"
            "🎚️ Звуковая карта:\n• Apollo Twin DUO USB\n\n"
            "💻 ПК:\n• AMD Ryzen 5 1600\n• 16 GB RAM\n• SSD 512 GB\n\n"
            "🧩 Плагины:\n• SoundToys\n• Waves\n• FabFilter\n• И другие\n\n"
            "📶 Быстрый Wi-Fi — если потребуется что-то докачать"
        )

    elif text == "📋 Все записи":
        if user_id not in studio_members_ids:
            await message.answer("⛔ У вас нет доступа к этой команде.")
            return
        all_bookings = get_all_active_bookings()
        if not all_bookings:
            await message.answer("📭 Нет актуальных броней.")
        else:
            result = "📋 АКТУАЛЬНЫЕ БРОНИ (сегодня и позже):\n\n"
            for i, row in enumerate(all_bookings[:10], 1):
                result += f"{i}. {row[4]}\n\n"
            await message.answer(result)

    elif text.startswith("⏳ Продлить"):
        booking_id = text.replace("⏳ Продлить ", "").strip()
        if booking_id not in bookings:
            await message.answer("⛔ Это не ваша бронь или она не найдена.")
            return
        if f"|{user_id}" not in bookings[booking_id]:
            await message.answer("⛔ Это не ваша бронь.")
            return
        booking_data = bookings[booking_id].split('|')[0]
        await message.answer(
            "⏳ Введите новое время окончания в формате ЧЧ-ЧЧ\n"
            f"Пример: 15-18\n\n"
            f"Текущая бронь: {booking_data}"
        )
        await state.update_data(extend_booking_id=booking_id)
        await state.set_state(BookingStates.waiting_for_extend)

    elif text.startswith("❌ Отменить"):
        booking_id = text.replace("❌ Отменить ", "").strip()
        if booking_id not in bookings:
            await message.answer("❌ Бронь не найдена.")
            return
        if f"|{user_id}" not in bookings[booking_id]:
            await message.answer("⛔ Это не ваша бронь.")
            return
        booking_data = bookings[booking_id].split('|')[0]
        if delete_booking(booking_id):
            await message.answer("✅ Бронь успешно отменена.")
            await bot.send_message(CHAT_ID, f"❌ ОТМЕНЕНА БРОНЬ!\n\n{booking_data}\n👤 Отменил: @{username}")
            await bot.send_message(YOUR_USER_ID, f"❌ ОТМЕНЕНА БРОНЬ!\n\n{booking_data}\n👤 Отменил: @{username}")
        else:
            await message.answer("❌ Ошибка при отмене брони.")
        await message.answer("Главное меню:", reply_markup=get_main_keyboard(user_id))

    elif text == "🔙 Назад в меню":
        await message.answer("Главное меню:", reply_markup=get_main_keyboard(user_id))

    else:
        await message.answer("❌ Неизвестная команда. Используйте кнопки меню.", reply_markup=get_main_keyboard(user_id))

# ==========================================
# ========== СОХРАНЕНИЕ БРОНИ ==============
# ==========================================

@dp.message(BookingStates.waiting_for_booking)
async def save_booking(message: types.Message, state: FSMContext):
    booking_text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    data = await state.get_data()
    selected_service = data.get("selected_service")

    if not selected_service:
        await message.answer("❌ Ошибка. Выберите услугу заново.")
        await state.clear()
        return

    if selected_service == "🎤 1 час записи - 500р":
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', booking_text)
        if not time_match:
            await message.answer("❌ Неверный формат. Пример: Анна, 31.12, 15-18")
            return
        start_hour = int(time_match.group(1))
        end_hour = int(time_match.group(2))
        duration = end_hour - start_hour
        if duration <= 0:
            await message.answer("❌ Время окончания должно быть позже времени начала.")
            return
        if user_id in studio_members_ids and 12 <= start_hour < 22 and duration > 4:
            await message.answer(f"⏰ В дневное время (12:00-22:00) участники могут бронировать максимум 4 часа. Вы выбрали {duration} ч.")
            return
        if is_time_conflict(start_hour, end_hour):
            await message.answer("❌ Это время уже занято другой бронью.")
            return
    else:
        date_match = re.search(r'(\d{2}\.\d{2})-(\d{2}\.\d{2})', booking_text)
        if not date_match:
            await message.answer("❌ Неверный формат. Пример: Анна, 31.12-01.01")
            return

    full_booking = f"{booking_text}, {selected_service}"
    booking_id = str(int(time.time()))
    add_booking(booking_id, full_booking, user_id)

    await message.answer("✅ Бронь сохранена! Спасибо, что выбрали нас ❤️")
    await state.clear()

    # ========== КТО ЗАБРОНИРОВАЛ ==========
    if user_id in studio_members_ids:
        member_name = studio_members.get(user_id, "Участник")
        who_booked = f"Участник: {member_name} (@{username})"
    else:
        who_booked = f"Клиент: {message.from_user.first_name} (@{username})"

    # ========== УВЕДОМЛЕНИЯ ==========
    # 1. В общий чат студии
    await bot.send_message(
        CHAT_ID,
        f"🔔 НОВАЯ БРОНЬ!\n\n{full_booking}\n\n👤 {who_booked}"
    )
    
    # 2. ЛИЧНО ТЕБЕ (Архив)
    await bot.send_message(
        YOUR_USER_ID,
        f"🔔 ТЕБЕ НОВАЯ ЗАПИСЬ!\n\n"
        f"👤 {who_booked}\n"
        f"📋 Данные: {booking_text}\n"
        f"🎵 Услуга: {selected_service}\n"
        f"🆔 ID брони: {booking_id}"
    )

    await message.answer("Главное меню:", reply_markup=get_main_keyboard(user_id))

# ==========================================
# ========== ПРОДЛЕНИЕ БРОНИ ===============
# ==========================================

@dp.message(BookingStates.waiting_for_extend)
async def extend_booking(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    data = await state.get_data()
    booking_id = data.get("extend_booking_id")
    if not booking_id:
        await message.answer("❌ Ошибка. Попробуйте снова.")
        await state.clear()
        return
    if booking_id not in bookings:
        await message.answer("❌ Бронь не найдена.")
        await state.clear()
        return
    old_booking = bookings[booking_id].split('|')[0]
    new_time = message.text.strip()
    time_match = re.search(r'(\d{1,2})-(\d{1,2})', new_time)
    if not time_match:
        await message.answer("❌ Неверный формат. Используйте ЧЧ-ЧЧ, например 15-18")
        return
    new_start = int(time_match.group(1))
    new_end = int(time_match.group(2))
    if is_time_conflict(new_start, new_end, booking_id):
        await message.answer("❌ Это время уже занято другой бронью.")
        return
    new_booking = re.sub(r'\d{1,2}-\d{1,2}', new_time, old_booking)
    update_booking(booking_id, new_booking)
    await message.answer("✅ Бронь успешно продлена!")
    await state.clear()
    await bot.send_message(CHAT_ID, f"⏳ ПРОДЛЕНА БРОНЬ!\n\n{new_booking}\n👤 Продлил: @{username}")
    await bot.send_message(YOUR_USER_ID, f"⏳ ПРОДЛЕНА БРОНЬ!\n\n{new_booking}\n👤 Продлил: @{username}")
    await message.answer("Главное меню:", reply_markup=get_main_keyboard(user_id))

# ==========================================
# ========== ЗАПУСК БОТА ===================
# ==========================================

async def main():
    print("🤖 Бот запущен!")
    print(f"📂 Загружено броней: {len(bookings)}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
