import asyncio
import re
import time
import datetime
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import pytz
import os
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# ========== КОНФИГУРАЦИЯ ==================
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "-1004374514040"
YOUR_USER_ID = 1442416548

# Список участников студии
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
# ========== ПОДКЛЮЧЕНИЕ К GOOGLE ==========
# ==========================================

# Путь к файлу с ключом (должен лежать в папке с ботом)
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
client = gspread.authorize(creds)

# Открой таблицу по названию (создай её заранее в Google Диске)
SHEET_NAME = "Брони студии"  # Название твоей таблицы
sheet = client.open(SHEET_NAME).sheet1

# Если таблица пустая — добавляем заголовки
if not sheet.get_all_values():
    sheet.append_row(["ID", "Дата и время брони", "Клиент", "Услуга", "Данные брони", "ID пользователя"])

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
# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ТАБЛИЦЕЙ =
# ==========================================

def get_all_bookings():
    """Возвращает все строки из таблицы, кроме заголовка"""
    rows = sheet.get_all_values()
    if len(rows) > 1:
        return rows[1:]  # Пропускаем заголовок
    return []

def add_booking(booking_id, full_booking, user_id):
    """Добавляет новую бронь в таблицу"""
    now = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%Y-%m-%d %H:%M")
    # Парсим имя клиента из строки брони
    name_match = re.search(r'^([^,]+)', full_booking)
    client_name = name_match.group(1).strip() if name_match else "Не указан"
    # Парсим услугу
    service_match = re.search(r',\s*(.+)$', full_booking)
    service = service_match.group(1).strip() if service_match else "Не указана"
    
    sheet.append_row([booking_id, now, client_name, service, full_booking, str(user_id)])

def delete_booking(booking_id):
    """Удаляет бронь по ID"""
    rows = sheet.get_all_values()
    for i, row in enumerate(rows):
        if row[0] == booking_id:
            sheet.delete_rows(i + 1)  # +1 потому что индексация с 0, а строки в Google с 1
            return True
    return False

def get_user_bookings(user_id):
    """Возвращает все брони пользователя"""
    rows = get_all_bookings()
    user_bookings = []
    for row in rows:
        if row[5] == str(user_id):  # ID пользователя в 6-й колонке (индекс 5)
            user_bookings.append(row)
    return user_bookings

def get_all_active_bookings():
    """Возвращает все актуальные брони (сегодня и позже)"""
    rows = get_all_bookings()
    active = []
    today = datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime("%d.%m")
    for row in rows:
        booking_text = row[4]  # Данные брони в 5-й колонке
        date_match = re.search(r'(\d{2}\.\d{2})', booking_text)
        if date_match:
            booking_date = date_match.group(1)
            try:
                b_day, b_month = map(int, booking_date.split('.'))
                t_day, t_month = map(int, today.split('.'))
                if (b_month > t_month) or (b_month == t_month and b_day >= t_day):
                    active.append(row)
            except:
                pass
    return active

def update_booking(booking_id, new_booking_text):
    """Обновляет текст брони по ID"""
    rows = sheet.get_all_values()
    for i, row in enumerate(rows):
        if row[0] == booking_id:
            sheet.update_cell(i + 1, 5, new_booking_text)  # 5-я колонка = данные брони
            return True
    return False

def is_time_conflict(new_start, new_end, exclude_booking_id=None):
    """Проверяет пересечение времени с другими бронями"""
    rows = get_all_bookings()
    for row in rows:
        booking_id = row[0]
        if exclude_booking_id and booking_id == exclude_booking_id:
            continue
        booking_text = row[4]
        time_match = re.search(r'(\d{1,2})-(\d{1,2})', booking_text)
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

@dp.message(lambda message: True)
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
        # Проверяем, что бронь принадлежит пользователю
        user_bookings = get_user_bookings(user_id)
        booking_exists = any(row[0] == booking_id for row in user_bookings)
        if not booking_exists:
            await message.answer("⛔ Это не ваша бронь или она не найдена.")
            return
        # Получаем текущий текст брони
        rows = get_all_bookings()
        booking_data = None
        for row in rows:
            if row[0] == booking_id:
                booking_data = row[4]
                break
        if not booking_data:
            await message.answer("❌ Бронь не найдена.")
            return
        await message.answer(
            "⏳ Введите новое время окончания в формате ЧЧ-ЧЧ\n"
            f"Пример: 15-18\n\n"
            f"Текущая бронь: {booking_data}"
        )
        await state.update_data(extend_booking_id=booking_id)
        await state.set_state(BookingStates.waiting_for_extend)

    elif text.startswith("❌ Отменить"):
        booking_id = text.replace("❌ Отменить ", "").strip()
        user_bookings = get_user_bookings(user_id)
        booking_exists = any(row[0] == booking_id for row in user_bookings)
        if not booking_exists:
            await message.answer("⛔ Это не ваша бронь или она не найдена.")
            return
        # Получаем текст брони для уведомления
        rows = get_all_bookings()
        booking_data = None
        for row in rows:
            if row[0] == booking_id:
                booking_data = row[4]
                break
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
        # Проверка пересечений
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

    who_booked = f"Участник: {studio_members.get(user_id, 'Участник')} (@{username})" if user_id in studio_members_ids else f"Клиент: {message.from_user.first_name} (@{username})"
    await bot.send_message(CHAT_ID, f"🔔 НОВАЯ БРОНЬ!\n\n{full_booking}\n\n👤 {who_booked}")
    await bot.send_message(YOUR_USER_ID, f"🔔 ТЕБЕ НОВАЯ ЗАПИСЬ!\n\n👤 {who_booked}\n📋 Данные: {booking_text}\n🎵 Услуга: {selected_service}\n🆔 ID брони: {booking_id}")
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
    rows = get_all_bookings()
    old_booking = None
    for row in rows:
        if row[0] == booking_id:
            old_booking = row[4]
            break
    if not old_booking:
        await message.answer("❌ Бронь не найдена.")
        await state.clear()
        return
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
# ========== ЗАПУСК ========================
# ==========================================

async def main():
    print("🤖 Бот с Google Таблицами запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())