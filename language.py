# /app/language.py

LEXICON = {
    'choose_language': "🌐 Выберите язык / Please select a language / Tilni tanlang",
    'language_selected': {
        'ru': "🇷🇺 Выбран русский язык.",
        'en': "🇬🇧 English language selected.",
        'uz': "🇺🇿 O'zbek tili tanlandi."
    },
    'dashboard_header': {
        'ru': "<b>🛎️ Панель Ресепшена</b>\n\n<b>Новые сообщения: {count}</b>\n\nВыберите чат для ответа:",
        'en': "<b>🛎️ Reception Dashboard</b>\n\n<b>New messages: {count}</b>\n\nSelect a chat to reply:",
        'uz': "<b>🛎️ Qabulxona Paneli</b>\n\n<b>Yangi xabarlar: {count}</b>\n\nJavob berish uchun chatni tanlang:"
    },
    'no_new_messages': {
        'ru': "<b>✅ Новых сообщений нет</b>\n\nВсе чаты обработаны. Отличная работа!",
        'en': "<b>✅ No new messages</b>\n\nAll chats have been handled. Great job!",
        'uz': "<b>✅ Yangi xabarlar yo'q</b>\n\nBarcha chatlar bilan ishlangan. Ajoyib ish!"
    },
    'claim_button': {
        'ru': "Комната {room_number}",
        'en': "Room {room_number}",
        'uz': "{room_number}-xona"
    },
    'employee_chat_info': {
        'ru': (
            "<b>Информация по чату №{chat_id}</b>\n\n"
            "👤 <b>Клиент:</b> {user_name}\n"
            "🚪 <b>Комната:</b> {room_number}\n\n"
            "<b>📜 История сообщений:</b>\n"
            "-----------------------------------\n"
            "{history}\n"
            "-----------------------------------\n\n"
            "<i>👇 Чтобы ответить, используйте функцию 'Ответить' (Reply) на это сообщение.</i>"
        ),
        'en': (
            "<b>Chat Info #{chat_id}</b>\n\n"
            "👤 <b>Client:</b> {user_name}\n"
            "🚪 <b>Room:</b> {room_number}\n\n"
            "<b>📜 Message History:</b>\n"
            "-----------------------------------\n"
            "{history}\n"
            "-----------------------------------\n\n"
            "<i>👇 To respond, use the 'Reply' function on this message.</i>"
        ),
        'uz': (
            "<b>#{chat_id} sonli chat ma'lumoti</b>\n\n"
            "👤 <b>Mijoz:</b> {user_name}\n"
            "🚪 <b>Xona:</b> {room_number}\n\n"
            "<b>📜 Xabarlar tarixi:</b>\n"
            "-----------------------------------\n"
            "{history}\n"
            "-----------------------------------\n\n"
            "<i>👇 Javob berish uchun ushbu xabarga 'Javob berish' (Reply) funksiyasidan foydalaning.</i>"
        )
    },
    'chat_claimed_notification': {
        'ru': "✅ Сотрудник {employee_name} взял в работу чат с комнатой <b>{room_number}</b>.",
        'en': "✅ Staff member {employee_name} has claimed the chat with room <b>{room_number}</b>.",
        'uz': "✅ Xodim {employee_name} <b>{room_number}</b>-xonadagi chatni o'z zimmasiga oldi."
    },
    'reply_sent': {
        'ru': "✅ Ваше сообщение отправлено клиенту.",
        'en': "✅ Your message has been sent to the client.",
        'uz': "✅ Sizning xabaringiz mijozga yuborildi."
    },
    'error_api': {
       'ru': "⚠️ Ошибка при обращении к API. Попробуйте позже.",
       'en': "⚠️ Error while contacting the API. Please try again later.",
       'uz': "⚠️ APIga murojaat qilishda xatolik. Keyinroq urinib ko'ring."
    },
     'history_line': {
        'ru': "[{sender_type}] {sender_name} ({time}):\n{content}\n",
        'en': "[{sender_type}] {sender_name} ({time}):\n{content}\n",
        'uz': "[{sender_type}] {sender_name} ({time}):\n{content}\n",
    }
}