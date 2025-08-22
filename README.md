## Hotel Service API — документация

Современное backend‑приложение на FastAPI для управления отелем: пользователи, сотрудники, номера, типы номеров, бронирования, сервисы, чаты (гость ↔ ресепшен), интеграция с Telegram и AI.

### Стек
- **FastAPI**, **Pydantic**
- **SQLAlchemy (async) + MySQL** (драйвер `aiomysql`)
- **JWT** (python‑jose)
- **Redis** (rate limiting на логине)
- **aiogram** (Telegram‑бот ресепшена)
- **google-generativeai** (Gemini для AI‑ответов)

### Архитектура и сущности
- **Пользователи**: регистрация/статус, бронирования, чаты, сервис‑заявки
- **Сотрудники**: роли `admin`, `reception`, `manager`, статус `active/archived`
- **Номера**: статусы `available/occupied/maintenance`, типы номеров с переводами (`ru/en/uz`)
- **Бронирования**: статусы `confirmed/active/completed/cancelled`
- **Сервисы**: справочник услуг + переводы, сервис‑заявки с назначением сотрудника
- **Чаты и сообщения**: тип чата `AI/RECEPTION`, история сообщений гость↔ресепшен

Схема БД полностью приведена в `database.sql`.

### Требования
- Python 3.11+
- MySQL 8+
- Redis (по умолчанию `redis://localhost:6379/0`)

### Установка
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
```

### Конфигурация (.env)
Создайте файл `.env` в корне `Hotel_Service_API/` со значениями:
```env
# База данных (async URL для SQLAlchemy)
DATABASE=mysql+aiomysql://USER:PASSWORD@HOST:3306/DB_NAME

# JWT
SECRET_KEY=your-secret
TOKEN_EXPIRE=120  # минуты

# Google Gemini (опционально, для AI)
API_KEY=your-google-generativeai-key

# Telegram‑бот (для файла telegram_bot.py)
TELEGRAM_BOT_TOKEN=123:ABC
SUPER_GROUP_CHAT_ID=-1001234567890
API_BASE_URL=http://127.0.0.1:8000
API_EMPLOYEE_USERNAME=reception_login
API_EMPLOYEE_PASSWORD=reception_password
```

Примечания:
- Убедитесь, что в БД есть минимум один сотрудник с ролью `reception` для авторизации бота (`/admin/employees`).
- Redis должен быть доступен локально (или измените инициализацию в коде на ваш URL).

### Инициализация БД
1) Создайте пустую БД в MySQL.
2) Выполните в MySQL клиенте импорт `database.sql` из корня проекта:
```bash
mysql -u USER -p DB_NAME < database.sql
```

### Запуск API
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

API стартует без Swagger/Redoc (отключено). Корневой эндпоинт `/` возвращает служебное сообщение.

### Запуск Telegram‑бота ресепшена
```bash
python telegram_bot.py
```

Бот:
- периодически синхронизирует состояние номеров с API
- создает/поддерживает топики по номерам в супергруппе
- ретранслирует ответы сотрудников гостям через API
- отправляет уведомления и авто‑закрывает просроченные бронирования

### Аутентификация и роли
- Пользовательский вход: `POST /auth/login` (телефон + пароль), в ответ — `access_token`
- Сотрудники: логин через `POST /admin/login` (username/password), токен применяется к ресепшен/админ эндпоинтам
- Роли проверяются через JWT; недоступные действия отдают 403

### Обзор основных эндпоинтов

- **Корень**
  - `GET /` — ping/health сообщение

- **Auth (пользователь)**
  - `POST /auth/login` — логин по телефону и паролю, ответ: `{access_token, token_type}`

- **User** (требует токен пользователя)
  - `GET /user/profile` — профиль пользователя
  - `GET /user/bookings` — список бронирований
  - `GET /user/bookings/{booking_id}` — детали бронирования
  - `GET /user/services` — доступные услуги
  - `POST /user/service-requests` — создать запрос услуги
  - `GET /user/service-requests` — мои запросы
  - `POST /user/chats` — создать чат (AI/RECEPTION)
  - `GET /user/chats/{chat_id}/messages` — история сообщений
  - `POST /user/chats/{chat_id}/messages` — отправить сообщение

- **Reception** (токен сотрудника `reception`/`manager`/`admin`)
  - `GET /reception/rooms` — доска по комнатам с текущими гостями/чатами
  - `GET /reception/chats` — список чатов ресепшена
  - `GET /reception/chats/{chat_id}/messages` — история сообщений
  - `POST /reception/chats/{chat_id}/messages` — ответ сотрудника гостю
  - `GET /reception/service-requests` — заявки на услуги
  - `GET /reception/service-requests/{request_id}` — одна заявка
  - `POST /reception/bookings` — создать бронирование
  - `GET /reception/getusers` — агрегированный список активных гостей/броней
  - `GET /reception/bookings/{booking_id}` — сведения по бронированию для панели
  - `PATCH /reception/bookings/{booking_id}` — обновить статус (используется ботом для авто‑выезда)

- **Admin** (токен сотрудника с ролью `admin`)
  - `POST /admin/login` — вход админа
  - `POST /admin/employees` | `GET /admin/employees` | `GET /admin/employees/{id}` | `PUT /admin/employees/{id}` | `DELETE /admin/employees/{id}`
  - `POST /admin/room-types` | `GET /admin/room-types`
  - `POST /admin/rooms` | `PUT /admin/rooms/{room_id}`

Строгие схемы запросов/ответов описаны в `main.py` через Pydantic‑модели.

### Примеры запросов

- **Логин пользователя**
```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"+998901112233","password":"1234"}'
```

- **Профиль пользователя**
```bash
curl -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8000/user/profile
```

### Лимитирование и безопасность
- Логин пользователя ограничен rate‑limit (Redis): 10 попыток/мин, блокировка на 3 минуты
- Все защищенные эндпоинты требуют корректного JWT в `Authorization: Bearer <token>`
- CORS открыт по умолчанию — рекомендуем ограничить `allow_origins` на ваш фронтенд‑домен в `main.py`

### Логи и мониторинг
- Включены базовые логгеры Uvicorn; неудачные запросы (4xx/5xx) дополнительно пишутся в `/var/log/uvicorn/access.log` для fail2ban

### Частые проблемы
- Неправильный `DATABASE` (используйте async‑URL `mysql+aiomysql://...`)
- Не запущен Redis → логин отдает 500/429
- Отсутствует сотрудник `reception` → Telegram‑бот не сможет авторизоваться
