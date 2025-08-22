import asyncio
from datetime import datetime, timedelta
from pytz import timezone
import json
import logging
import os
import sys
from typing import Optional, Dict, Any, List
import time
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

TOPICS_MAP_FILE = "topics.json"
LAST_MESSAGE_IDS_FILE = "last_message_ids.json"

# { "room_number": {"status": "occupied", "api_chat_id": 123, "guest_name": "..."} }
PREVIOUS_HOTEL_STATE: Dict[str, Dict] = {}

NOTIFICATIONS_SENT: Dict[str, bool] = {}


class APIClient:
    def __init__(self, base_url: str, username: str, password: str):
        self._base_url = base_url
        self._username = username
        self._password = password
        self._token: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=20.0)

    async def login(self) -> bool:
        logging.info("Попытка входа в API...")
        try:
            response = await self._client.post(
                f"{self._base_url}/admin/login",
                json={"username": self._username, "password": self._password}
            )
            response.raise_for_status()
            self._token = response.json().get("access_token")
            if self._token:
                self._client.headers["Authorization"] = f"Bearer {self._token}"
                logging.info("Успешный вход в API.")
                return True
            logging.error("В ответе API отсутствует токен доступа.")
            return False
        except Exception as e:
            logging.error(f"Критическая ошибка при входе в API: {e}")
            return False

    async def _make_request(self, method: str, url: str, **kwargs) -> Optional[Any]:
        if not self._token:
            if not await self.login():
                return None

        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logging.warning("Токен истек. Повторный вход...")
                if await self.login():
                    response = await self._client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response.json()
            logging.error(f"Ошибка API запроса {method} {url}: {e.response.status_code} {e.response.text}")
            return None
        except Exception as e:
            logging.error(f"Критическая ошибка при запросе {method} {url}: {e}")
            return None

    async def get_rooms(self) -> Optional[List[Dict]]:
        return await self._make_request("GET", f"{self._base_url}/reception/rooms")

    async def get_chat_messages(self, chat_id: int, since_id: Optional[int] = None) -> Optional[List[Dict]]:
        url = f"{self._base_url}/reception/chats/{chat_id}/messages"
        params = {"since_id": since_id} if since_id else {}
        return await self._make_request("GET", url, params=params)

    async def send_employee_message(self, chat_id: int, text: str) -> Optional[Dict]:
        return await self._make_request(
            "POST",
            f"{self._base_url}/reception/chats/{chat_id}/messages",
            json={"content": text}
        )
    async def get_all_bookings(self) -> Optional[List[Dict]]:
        return await self._make_request("GET", f"{self._base_url}/reception/getusers")

    async def close(self):
        await self._client.aclose()

async def automated_checkout_process(bot: Bot, api_client: APIClient, chat_id: int):
    """
    Получает ВСЕ бронирования, находит просроченные и выполняет выселение.
    """
    logging.info("Запуск задачи автоматического выселения (v2)...")
    
    # ШАГ 1: Получаем все бронирования, а не комнаты
    all_bookings = await api_client.get_all_bookings()
    if not all_bookings:
        logging.warning("Задача выселения: не удалось получить список бронирований.")
        return

    # Устанавливаем часовой пояс один раз
    tashkent_tz = timezone("Asia/Tashkent")
    now_tashkent = datetime.now(tashkent_tz)

    for booking in all_bookings:
        booking_status = booking.get("booking_status")
        booking_id = booking.get("booking_id")

        # Пропускаем уже завершенные или отмененные бронирования
        if booking_status not in ["active", "confirmed"]:
            continue

        try:
            # Преобразуем дату выезда в объект datetime
            checkout_date_str = booking["check_out_date"]
            # ВАЖНО: Присваиваем "наивной" дате из БД правильный часовой пояс
            naive_datetime = datetime.fromisoformat(checkout_date_str)
            checkout_date = tashkent_tz.localize(naive_datetime)
        except (KeyError, ValueError) as e:
            logging.error(f"Не удалось обработать check_out_date для бронирования {booking_id}: {e}")
            continue

        # 1. ЛОГИКА АВТОМАТИЧЕСКОГО ВЫСЕЛЕНИЯ
        if checkout_date <= now_tashkent:
            logging.info(f"ACTION: Найдено просроченное бронирование ID {booking_id}. Запуск выселения...")
            
            # Вызываем PATCH-эндпоинт для обновления статуса
            response = await api_client._make_request(
                "PATCH",
                f"{api_client._base_url}/reception/bookings/{booking_id}",
                json={"status": "completed"}
            )
            if response:
                guest_name = booking.get("last_name", "Гость")
                # Примечание: в этом ответе нет номера комнаты, уведомление будет более общим
                await send_message_with_retry(
                    bot, chat_id, f"✅ **Автоматическое выселение**\nГость: {guest_name}\nБронь ID: {booking_id}"
                )
            continue # Переходим к следующему бронированию

        # 2. ЛОГИКА УВЕДОМЛЕНИЙ (остается без изменений)
        time_left = checkout_date - now_tashkent
        notification_levels = {
            "3h": timedelta(hours=3), "2h": timedelta(hours=2),
            "1h": timedelta(hours=1), "30m": timedelta(minutes=30)
        }
        
        for level, duration in notification_levels.items():
            notification_key = f"{booking_id}:{level}"
            if time_left <= duration and not NOTIFICATIONS_SENT.get(notification_key):
                guest_name = booking.get("last_name", "Гость")
                await send_message_with_retry(
                    bot, chat_id, f"⏳ **Скоро выселение ({level})**\nГость: {guest_name}\nБронь ID: {booking_id}"
                )
                NOTIFICATIONS_SENT[notification_key] = True
                break


def load_json_file(filename: str) -> Dict:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json_file(filename: str, data: Dict):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_guest_info(room_data: Dict) -> Dict:
    booking = room_data.get("current_booking")
    if not booking or not booking.get("user"):
        return {"api_chat_id": None, "guest_name": "Неизвестный гость"}

    user = booking["user"]
    full_name = ' '.join(filter(None, [user.get("last_name"), user.get("first_name"), user.get("patronymic")])).strip()
    
    api_chat_id = booking.get("reception_chat_id")

    return {"api_chat_id": api_chat_id, "guest_name": full_name or "Гость"}


async def recreate_room_topic(bot: Bot, chat_id: int, room_number: str, topic_map: Dict) -> Optional[int]:
    old_topic_id = topic_map.get(room_number)
    if old_topic_id:
        try:
            await bot.delete_forum_topic(chat_id=chat_id, message_thread_id=old_topic_id)
            logging.info(f"Старый топик для комнаты {room_number} (ID: {old_topic_id}) удален.")
        except Exception as e:
            logging.warning(f"Не удалось удалить старый топик {old_topic_id} для комнаты {room_number}: {e}")

    while True:
        try:
            new_topic = await bot.create_forum_topic(chat_id=chat_id, name=f"Комната {room_number}")
            logging.info(f"Создан новый топик для комнаты {room_number} с ID: {new_topic.message_thread_id}")
            return new_topic.message_thread_id

        except TelegramRetryAfter as e:
            # Telegram попросил подождать
            logging.warning(
                f"Превышен лимит на создание топиков. Ждем {e.retry_after} секунд, как просит Telegram..."
            )
            await asyncio.sleep(e.retry_after) # Ждем указанное время

        except Exception as e:
            # Произошла другая, непредвиденная ошибка
            logging.error(f"Критическая ошибка при создании нового топика для комнаты {room_number}: {e}")
            return None

async def sync_hotel_state(bot: Bot, api_client: APIClient, chat_id: int):
    logging.debug("Запущена синхронизация состояния отеля...")
    
    topic_map = load_json_file(TOPICS_MAP_FILE)
    last_message_ids = load_json_file(LAST_MESSAGE_IDS_FILE)
    
    current_rooms_data = await api_client.get_rooms()
    if not current_rooms_data:
        logging.warning("Не удалось получить данные о комнатах от API. Пропуск цикла.")
        return

    topics_changed = False
    for room in current_rooms_data:
        room_number = str(room.get("room_number"))
        if room_number and room_number not in topic_map:
            logging.info(f"Обнаружена новая комната '{room_number}', для которой нет топика. Создание...")
            new_topic_id = await recreate_room_topic(bot, chat_id, room_number, topic_map)
            if new_topic_id:
                topic_map[room_number] = new_topic_id
                topics_changed = True
                await asyncio.sleep(2)
    if topics_changed:
        save_json_file(TOPICS_MAP_FILE, topic_map)


    for room in current_rooms_data:
        room_number = str(room.get("room_number"))
        topic_id = topic_map.get(room_number)
        if not topic_id:
            continue

        current_status = room.get("status")
        previous_state = PREVIOUS_HOTEL_STATE.get(room_number, {})
        previous_status = previous_state.get("status")

        if current_status != previous_status:
            if current_status == "available" and previous_status == "occupied":
                logging.info(f"Гость выехал из комнаты {room_number}. Очистка истории...")
                new_topic_id = await recreate_room_topic(bot, chat_id, room_number, topic_map)
                if new_topic_id:
                    topic_map[room_number] = new_topic_id
                    save_json_file(TOPICS_MAP_FILE, topic_map)
                    await bot.send_message(chat_id, f"✅ Комната {room_number} свободна", message_thread_id=new_topic_id)
                    topic_id = new_topic_id
            
            elif current_status == "occupied" and previous_status in ["available", None]:
                logging.info(f"В комнату {room_number} заселился гость.")
                guest_info = get_guest_info(room)
                await send_message_with_retry(
                    bot, chat_id, f"👤 Комната {room_number} занята.\n<b>Гость:</b> {guest_info['guest_name']}", topic_id
                )

        if current_status == "occupied":
            guest_info = get_guest_info(room)
            api_chat_id = guest_info.get("api_chat_id")
            await asyncio.sleep(1)
            if api_chat_id:
                api_chat_id_str = str(api_chat_id)
                since_id = last_message_ids.get(api_chat_id_str)
                messages = await api_client.get_chat_messages(api_chat_id, since_id)
                
                if messages:
                    for msg in messages:
                        if msg.get("sender", {}).get("type") == "user":
                            try:
                                await bot.send_message(
                                    chat_id=chat_id,
                                    message_thread_id=topic_id,
                                    text=f"👤 <b>Гость:</b>\n{msg.get('content')}"
                                )
                                last_message_ids[api_chat_id_str] = msg.get("id")
                                save_json_file(LAST_MESSAGE_IDS_FILE, last_message_ids)
                                await asyncio.sleep(1)
                            except Exception as e:
                                logging.error(f"Не удалось отправить сообщение из API-чата {api_chat_id}: {e}")
                                break
        
        guest_info = get_guest_info(room) if current_status == "occupied" else {}
        PREVIOUS_HOTEL_STATE[room_number] = {
            "status": current_status,
            "api_chat_id": guest_info.get("api_chat_id"),
            "guest_name": guest_info.get("guest_name")
        }


async def employee_reply_handler(message: Message, api_client: APIClient):
    topic_id = message.message_thread_id
    
    room_number = None
    topic_map = load_json_file(TOPICS_MAP_FILE)
    for rn, tid in topic_map.items():
        if tid == topic_id:
            room_number = rn
            break
            
    if not room_number:
        logging.warning(f"Получен ответ в неизвестном топике {topic_id}. Игнорируется.")
        return

    current_state = PREVIOUS_HOTEL_STATE.get(room_number)
    if not current_state or current_state.get("status") != "occupied":
        await message.reply("❌ Нельзя отправить сообщение. В этой комнате сейчас нет гостя.")
        return

    api_chat_id = current_state.get("api_chat_id")
    if not api_chat_id:
        await message.reply("❌ Ошибка: не найден ID чата для текущего гостя.")
        return

    logging.info(f"Сотрудник ответил в топике комнаты {room_number}. Отправка в API-чат {api_chat_id}...")
    response = await api_client.send_employee_message(api_chat_id, message.text)

    if response:
        await message.reply("✅ Сообщение отправлено гостю")
    else:
        await message.reply("❌ Произошла ошибка при отправке сообщения гостю.")


async def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id_str = os.getenv("SUPER_GROUP_CHAT_ID")
    api_url = os.getenv("API_BASE_URL")
    api_user = os.getenv("API_EMPLOYEE_USERNAME")
    api_pass = os.getenv("API_EMPLOYEE_PASSWORD")

    if not all([token, chat_id_str, api_url, api_user, api_pass]):
        logging.critical("Ключевые переменные окружения не установлены. Проверьте .env файл.")
        sys.exit(1)
    
    chat_id = int(chat_id_str)

    api_client = APIClient(base_url=api_url, username=api_user, password=api_pass)
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Tashkent"))

    dp.message.register(
        employee_reply_handler,
        F.chat.id == chat_id,
        F.message_thread_id != None,
        F.from_user.is_bot == False,
        F.text
    )
    scheduler.add_job(sync_hotel_state, 'interval', seconds=5, args=[bot, api_client, chat_id])
    scheduler.add_job(automated_checkout_process, 'interval', minutes=1, args=[bot, api_client, chat_id])

    try:
        logging.info("Первоначальная синхронизация состояний...")
        await sync_hotel_state(bot, api_client, chat_id)
        logging.info("Синхронизация завершена.")
        
        scheduler.start()
        logging.info("Планировщик запущен. Бот начинает работу...")
        
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, api_client=api_client)

    finally:
        logging.info("Остановка бота...")
        scheduler.shutdown()
        await api_client.close()
        await bot.session.close()
        logging.info("Бот остановлен.")

async def send_message_with_retry(bot: Bot, chat_id: int, text: str, topic_id: int = None):
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            message_thread_id=topic_id
        )
    except TelegramRetryAfter as e:
        wait_time = e.retry_after
        logging.warning(f"Превышен лимит запросов. Ждем {wait_time} секунд...")
        await asyncio.sleep(wait_time)
        return await send_message_with_retry(bot, chat_id, text, topic_id)
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения: {e}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Программа завершена пользователем.")
