# Как подключить бота @toi3_bot к сайту TOIIM

Это инструкция для разработчика бота. Сайт уже готов, в бота нужно добавить две вещи:

1. Открывать услугу, когда человек пришёл с сайта по ссылке `t.me/toi3_bot?start=service_12`.
2. Отправлять заявку клиента на сайт.

## Что нужно знать

| Что | Значение |
|---|---|
| Адрес сайта | `SITE_URL`. Пока сайт не выложен — `http://127.0.0.1:8000`, после деплоя — адрес на Render |
| Секретный ключ | `BOT_API_KEY`. Одна и та же строка у сайта и у бота. Хранить в `.env` бота, не в коде и не на GitHub |
| Токен бота | Нужен и боту, и сайту (сайт через него присылает уведомления о заявках). Сайт только отправляет сообщения, обновления (`getUpdates`) не читает, поэтому боту не мешает |

Ключ генерируется командой:

```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## API сайта

### Получить одну услугу

```
GET {SITE_URL}/api/services/12/
```

Ответ (сокращённо):

```json
{
  "id": 12,
  "title": "Ведущий Нурлан (демо)",
  "short_description": "...",
  "description": "...",
  "city": {"slug": "almaty", "name_ru": "Алматы"},
  "category": {"slug": "host", "name_ru": "Ведущие", "kind": "performer"},
  "price_from": 150000,
  "price_unit": "event",
  "rating_avg": "4.67",
  "reviews_count": 3,
  "address": "",
  "instagram": "",
  "url": "https://.../services/nurlan-host-almaty/",
  "images": ["https://..."],
  "cover_url": "https://..."
}
```

Если услуги нет или она не опубликована, придёт ответ `404`.

Другие запросы: `GET /api/services/?city=almaty&category=host&q=текст` — список с поиском, `GET /api/cities/`, `GET /api/categories/`.

### Отправить заявку

```
POST {SITE_URL}/api/requests/
Заголовки: Content-Type: application/json
           X-Bot-Key: <BOT_API_KEY>
```

```json
{
  "service": 12,
  "name": "Алия",
  "phone": "+7 700 123 45 67",
  "event_date": "2026-08-15",
  "guests": 150,
  "message": "Свадьба",
  "telegram_chat_id": 123456789,
  "idempotency_key": "любой uuid4"
}
```

Обязательные поля: `service`, `name`, `phone`. Остальные можно не отправлять.

| Ответ | Что значит |
|---|---|
| `201` `{"id": 5, "status": "new", "created": true}` | Заявка создана |
| `200` `{"created": false}` | Заявка с этим `idempotency_key` уже есть, повтор не создан |
| `400` `{"phone": ["Введите номер..."]}` | Ошибка в полях. Текст можно показать пользователю |
| `403` | Неверный или пустой ключ `X-Bot-Key` |

`idempotency_key` защищает от двойных заявок, если пользователь нажал кнопку два раза. Генерируйте один uuid на одну заявку.

## Пример для aiogram 3

```python
import os
import uuid

import aiohttp
from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

SITE_URL = os.environ["SITE_URL"].rstrip("/")
BOT_API_KEY = os.environ["BOT_API_KEY"]

router = Router()


async def get_service(service_id: int):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{SITE_URL}/api/services/{service_id}/", timeout=10) as resp:
            return await resp.json() if resp.status == 200 else None


async def send_request(data: dict):
    data.setdefault("idempotency_key", str(uuid.uuid4()))
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SITE_URL}/api/requests/", json=data, headers={"X-Bot-Key": BOT_API_KEY}, timeout=10,
        ) as resp:
            return resp.status, await resp.json()


@router.message(CommandStart(deep_link=True))
async def start_with_service(message: Message, command: CommandObject):
    # Ссылка с сайта: t.me/toi3_bot?start=service_12  ->  command.args == "service_12"
    args = command.args or ""
    if not args.startswith("service_") or not args[8:].isdigit():
        return await message.answer("Здравствуйте! Это TOIIM.")
    service = await get_service(int(args[8:]))
    if service is None:
        return await message.answer("Эта услуга сейчас недоступна.")
    await message.answer(
        f"<b>{service['title']}</b>\n"
        f"{service['city']['name_ru']} · от {service['price_from']:,} ₸\n\n"
        f"{service['short_description']}\n\n"
        f"Подробнее: {service['url']}",
        parse_mode="HTML",
    )
    # Дальше: ваша кнопка «Оставить заявку» -> спросить имя, телефон, дату, гостей -> send_request({...})
```

Когда собрали данные, отправляем заявку:

```python
status, body = await send_request({
    "service": service_id, "name": name, "phone": phone,
    "event_date": "2026-08-15", "guests": 150,
    "telegram_chat_id": message.chat.id,
})
if status in (200, 201):
    await message.answer("Заявка отправлена! Исполнитель свяжется с вами.")
elif status == 400:
    await message.answer("Проверьте данные: " + "; ".join(sum(body.values(), [])))
else:
    await message.answer("Не получилось отправить заявку, попробуйте позже.")
```

Если бот написан на python-telegram-bot, логика та же: в `/start` придёт `context.args == ["service_12"]`, а запросы можно делать через `httpx` или `requests`.

## Уведомления о заявках

Сайт сам пишет в Telegram о каждой новой заявке, с сайта и из бота. Чтобы это работало, на сервере сайта задаются:

- `TELEGRAM_BOT_TOKEN` — токен бота;
- `TELEGRAM_ADMIN_CHAT_ID` — куда слать: личный чат или группа команды. Свой chat id можно узнать у бота @userinfobot. Для группы добавьте в неё @toi3_bot, и id будет отрицательным числом.

Важно: бот может написать человеку, только если тот сам хоть раз нажал Start в боте.

## Проверка на своём компьютере

1. Сайт: в `.env` впишите `BOT_API_KEY=...`, запустите `python manage.py runserver`.
2. Бот: в `.env` бота впишите `SITE_URL=http://127.0.0.1:8000` и тот же `BOT_API_KEY`.
3. Откройте на сайте любую услугу и нажмите «Спросить в Telegram-боте». Бот должен показать эту услугу.
4. Отправьте заявку из бота. Она появится в админке сайта (`/admin/`, раздел «Заявки») с источником «Telegram-бот».
