#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============= КОНФИГУРАЦИЯ =============
# Для хостинга используйте переменные окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', 'ВАШ_ТОКЕН_БОТА')

# Конфигурация студии
STUDIO_NAME = "SoundWave Studio"
STUDIO_ADDRESS = "ул. Звуковая, д. 42, Москва"
STUDIO_PHONE = "+7 (999) 123-45-67"
STUDIO_EMAIL = "info@soundwave.ru"

PRICES = {
    'recording': '3000 ₽/час',
    'mixing': '5000 ₽/трек',
    'mastering': '3000 ₽/трек',
    'full': '10000 ₽/трек (запись + сведение + мастеринг)'
}

AVAILABLE_TIMES = ['10:00', '11:00', '12:00', '13:00', '14:00', 
                   '15:00', '16:00', '17:00', '18:00', '19:00', '20:00']

ADMIN_ID = 123456789  # Замените на ваш Telegram ID

# ============= КЛАВИАТУРЫ =============
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎵 Услуги и цены", callback_data='services')],
        [InlineKeyboardButton("📅 Забронировать время", callback_data='booking')],
        [InlineKeyboardButton("🎧 Портфолио", callback_data='portfolio')],
        [InlineKeyboardButton("📞 Контакты", callback_data='contacts')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
    ]
    return InlineKeyboardMarkup(keyboard)

def booking_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📅 Выбрать дату", callback_data='select_date')],
        [InlineKeyboardButton("🕐 Выбрать время", callback_data='select_time')],
        [InlineKeyboardButton("↩️ Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def services_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎤 Запись вокала", callback_data='service_recording')],
        [InlineKeyboardButton("🎛️ Сведение", callback_data='service_mixing')],
        [InlineKeyboardButton("🔊 Мастеринг", callback_data='service_mastering')],
        [InlineKeyboardButton("⭐ Полный пакет", callback_data='service_full')],
        [InlineKeyboardButton("↩️ Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def portfolio_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎸 Рок", callback_data='portfolio_rock')],
        [InlineKeyboardButton("🎹 Поп", callback_data='portfolio_pop')],
        [InlineKeyboardButton("🎧 Электроника", callback_data='portfolio_electronic')],
        [InlineKeyboardButton("🎻 Акустика", callback_data='portfolio_acoustic')],
        [InlineKeyboardButton("↩️ Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data='back_to_main')]]
    return InlineKeyboardMarkup(keyboard)

def booking_time_keyboard():
    keyboard = []
    row = []
    for i, time in enumerate(AVAILABLE_TIMES):
        row.append(InlineKeyboardButton(time, callback_data=f'time_{time}'))
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data='back_to_booking')])
    return InlineKeyboardMarkup(keyboard)

# ============= ОБРАБОТЧИКИ =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = f"""
🎵 *Добро пожаловать в {STUDIO_NAME}!*

Привет, {user.first_name}! 👋

Мы - профессиональная студия звукозаписи с современным оборудованием и опытными звукорежиссёрами.

📌 *Что мы предлагаем:*
• Запись вокала и инструментов
• Сведение и мастеринг
• Полный цикл продакшна

Выберите интересующий вас раздел в меню ниже:
"""
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🏠 *Главное меню*\n\nВыберите нужный раздел:",
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )

async def services_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = f"""
🎵 *Услуги {STUDIO_NAME}*

Выберите интересующую услугу для получения подробной информации:

💰 *Стоимость:*
• Запись: {PRICES['recording']}
• Сведение: {PRICES['mixing']}
• Мастеринг: {PRICES['mastering']}
• Полный пакет: {PRICES['full']}

*В стоимость входит:* использование оборудования, работа звукорежиссёра, чай/кофе ☕
"""
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=services_keyboard()
    )

async def service_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    service_map = {
        'service_recording': {
            'name': '🎤 Запись вокала',
            'desc': 'Профессиональная запись вокала и инструментов',
            'price': PRICES['recording'],
            'details': '• Конденсаторные микрофоны Neumann\n• Предусилители Universal Audio\n• Наушники для мониторинга\n• Акустическая обработка помещения'
        },
        'service_mixing': {
            'name': '🎛️ Сведение',
            'desc': 'Профессиональное сведение ваших треков',
            'price': PRICES['mixing'],
            'details': '• DAW: Pro Tools / Logic Pro\n• Плагины Waves, UAD, FabFilter\n• До 3 версий микса\n• Бесплатные правки в течение недели'
        },
        'service_mastering': {
            'name': '🔊 Мастеринг',
            'desc': 'Финальная обработка трека для релиза',
            'price': PRICES['mastering'],
            'details': '• Лудинг и нормализация\n• Эквализация и компрессия\n• Подготовка для стримингов\n• 2 версии мастера'
        },
        'service_full': {
            'name': '⭐ Полный пакет',
            'desc': 'Всё в одном: запись + сведение + мастеринг',
            'price': PRICES['full'],
            'details': '• Запись вокала (до 3 часов)\n• Профессиональное сведение\n• Мастеринг для релиза\n• Экономия до 20%'
        }
    }
    
    service = service_map.get(query.data)
    if service:
        text = f"""
*{service['name']}*

{service['desc']}

💰 *Стоимость:* {service['price']}

*Что входит:*
{service['details']}

Для бронирования перейдите в раздел "Забронировать время" 📅
"""
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )

async def booking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = """
📅 *Бронирование времени*

Для бронирования сессии выполните несколько шагов:

1️⃣ Выберите дату
2️⃣ Выберите время
3️⃣ Подтвердите бронирование

*Доступное время:* 10:00 - 20:00
*Длительность сессии:* от 1 часа
*Предоплата:* не требуется
"""
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=booking_menu_keyboard()
    )

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = """
📅 *Выберите дату*

*Доступные даты (ближайшие):*
• 20 августа - Доступно
• 21 августа - Доступно
• 22 августа - Занято
• 23 августа - Доступно
• 24 августа - Доступно

Введите дату в формате: *ДД.ММ.ГГГГ*
Например: 20.08.2024
"""
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=booking_time_keyboard()
    )

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = """
🕐 *Выберите время*

Доступные слоты для записи (1 час):
"""
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=booking_time_keyboard()
    )

async def book_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time = query.data.replace('time_', '')
    context.user_data['booking_time'] = time
    text = f"""
✅ *Вы выбрали время:* {time}

Теперь укажите:
• Ваше имя
• Что хотите записать (вокал, инструмент и т.д.)

Отправьте сообщение в формате:
*Имя:* Ваше имя
*Что записываем:* Описание

Например:
Имя: Иван Петров
Что записываем: Вокал для песни
"""
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=back_keyboard()
    )

async def handle_booking_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    lines = user_text.split('\n')
    name = ""
    description = ""
    
    for line in lines:
        if line.lower().startswith('имя:'):
            name = line.split(':', 1)[1].strip()
        elif line.lower().startswith('что записываем:'):
            description = line.split(':', 1)[1].strip()
    
    if not name or not description:
        await update.message.reply_text(
            "⚠️ Пожалуйста, заполните форму полностью:\n"
            "Имя: [ваше имя]\n"
            "Что записываем: [описание]"
        )
        return
    
    booking_info = {
        'user_id': update.effective_user.id,
        'username': update.effective_user.username,
        'name': name,
        'description': description,
        'time': context.user_data.get('booking_time', 'не указано')
    }
    
    # Отправка уведомления админу
    try:
        admin_text = f"""
🔔 *НОВОЕ БРОНИРОВАНИЕ!*

👤 Имя: {name}
🕐 Время: {booking_info['time']}
📝 Описание: {description}
🆔 User ID: {booking_info['user_id']}
👤 Username: @{booking_info['username'] or 'не указан'}
        """
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode='Markdown')
    except:
        pass  # Если админ не найден
    
    await update.message.reply_text(
        f"""
✅ *Бронирование создано!*

📋 *Данные:*
• Имя: {name}
• Описание: {description}
• Время: {booking_info['time']}

Скоро с вами свяжется наш менеджер для подтверждения! 📞

*Спасибо, что выбрали {STUDIO_NAME}!* 🎵
""",
        parse_mode='Markdown',
        reply_markup=back_keyboard()
    )

async def portfolio_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = """
🎧 *Портфолио*

Наша студия работала с различными артистами и жанрами. 
Выберите жанр, чтобы посмотреть примеры работ:

*Наши работы можно послушать на:*
• SoundCloud: soundwave.studio
• YouTube: @soundwave_studio
• VK: vk.com/soundwave_studio
"""
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=portfolio_keyboard()
    )

async def portfolio_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    genre_map = {
        'portfolio_rock': {
            'name': '🎸 Рок',
            'description': 'Работа с рок-группами: запись барабанов, гитар, вокала'
        },
        'portfolio_pop': {
            'name': '🎹 Поп',
            'description': 'Современная поп-музыка: работа с вокалистами и продюсерами'
        },
        'portfolio_electronic': {
            'name': '🎧 Электроника',
            'description': 'Синтезаторы, драм-машины, электронная обработка'
        },
        'portfolio_acoustic': {
            'name': '🎻 Акустика',
            'description': 'Запись акустических инструментов: фортепиано, скрипка, гитара'
        }
    }
    
    genre = genre_map.get(query.data)
    if genre:
        text = f"""
*{genre['name']}*

{genre['description']}

🎵 *Примеры работ:*
• Трек 1 - [ссылка на аудио]
• Трек 2 - [ссылка на аудио]
• Трек 3 - [ссылка на аудио]

*Хотите записать что-то подобное?* 
Свяжитесь с нами или забронируйте время! 📅
"""
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )

async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = f"""
📞 *Контакты {STUDIO_NAME}*

📍 *Адрес:*
{STUDIO_ADDRESS}

📱 *Телефон:*
{STUDIO_PHONE}

✉️ *Email:*
{STUDIO_EMAIL}

🌐 *Социальные сети:*
• Instagram: @soundwave_studio
• VK: vk.com/soundwave_studio
• YouTube: @soundwave_studio

🕐 *Режим работы:*
Пн-Вс: 10:00 - 22:00

*Как добраться:*
Метро "Звуковая", выход к ТЦ "Музыкальный", 5 минут пешком
"""
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=back_keyboard()
    )

async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = """
❓ *Помощь*

*Как пользоваться ботом:*

1️⃣ *Главное меню* - навигация по всем разделам
2️⃣ *Услуги и цены* - информация о наших услугах
3️⃣ *Забронировать время* - бронирование сессии записи
4️⃣ *Портфолио* - примеры наших работ
5️⃣ *Контакты* - наши контакты и адрес

*Частые вопросы:*

❔ *Нужна ли предоплата?*
Нет, предоплата не требуется.

❔ *Можно ли отменить бронирование?*
Да, за 24 часа до сессии.

❔ *Какой бюджет нужен?*
Цены начинаются от 3000 ₽/час.

❔ *Есть ли скидки?*
Да, при бронировании от 5 часов - скидка 10%.

*Связь с администратором:*
Напишите нам в Telegram: @soundwave_admin
"""
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=back_keyboard()
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже."
        )

# ============= ЗАПУСК БОТА =============
def main():
    # Настройка логирования
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))

    # Callback-обработчики
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_booking$'))
    
    application.add_handler(CallbackQueryHandler(services_menu, pattern='^services$'))
    application.add_handler(CallbackQueryHandler(service_detail, pattern='^service_'))
    
    application.add_handler(CallbackQueryHandler(booking_menu, pattern='^booking$'))
    application.add_handler(CallbackQueryHandler(select_date, pattern='^select_date$'))
    application.add_handler(CallbackQueryHandler(select_time, pattern='^select_time$'))
    application.add_handler(CallbackQueryHandler(book_time, pattern='^time_'))
    
    application.add_handler(CallbackQueryHandler(portfolio_menu, pattern='^portfolio$'))
    application.add_handler(CallbackQueryHandler(portfolio_genre, pattern='^portfolio_'))
    
    application.add_handler(CallbackQueryHandler(contacts, pattern='^contacts$'))
    application.add_handler(CallbackQueryHandler(help_menu, pattern='^help$'))

    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_booking_form))

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    print("🤖 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
