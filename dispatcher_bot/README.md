# Диспетчер входящих — Telegram Bot

Telegram-бот для автоматической классификации входящих обращений. Использует OpenAI API для понимания типа обращения (intent), услуги (service) и извлечения дополнительных полей (бюджет, дедлайн, контакт, цель). Отправляет структурированные данные в Make.com для дальнейшей обработки.

## Требования

- Python 3.11+

## Установка

```bash
pip install -r requirements.txt
```

## Переменные окружения

| Переменная | Обязательная | Описание |
|------------|--------------|----------|
| BOT_TOKEN | Да | Токен Telegram бота от @BotFather |
| MAKE_WEBHOOK_URL | Да | URL вебхука Make.com |
| OPENAI_API_KEY | Нет | API ключ OpenAI. Без него — fallback режим |
| OPENAI_MODEL | Нет | Модель OpenAI (по умолчанию: gpt-4o-mini) |
| ADMIN_CHAT_ID | Нет | Chat ID админа для алертов об ошибках Make |
| MAKE_STATUS_WEBHOOK_URL | Нет | URL вебхука Make.com для обновления статусов лидов |

## Получение токенов

### Telegram Bot Token

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям, задайте имя и username бота
4. Скопируйте полученный токен

### OpenAI API Key

1. Перейдите на [platform.openai.com](https://platform.openai.com)
2. Войдите или зарегистрируйтесь
3. Перейдите в раздел **API Keys**
4. Нажмите **Create new secret key**
5. Скопируйте ключ (он показывается только один раз)

### Make.com Webhook URL

1. Создайте новый сценарий в [Make.com](https://www.make.com)
2. Добавьте модуль **Webhooks → Custom webhook**
3. Нажмите **Add** для создания нового webhook
4. Скопируйте URL webhook

### ADMIN_CHAT_ID

1. Напишите боту [@userinfobot](https://t.me/userinfobot) в Telegram
2. Он пришлёт ваш chat ID

## Настройка

```bash
cp .env.example .env
```

Откройте файл `.env` и заполните переменные:

```
BOT_TOKEN=ваш_токен_telegram_бота
OPENAI_API_KEY=ваш_ключ_openai_api
OPENAI_MODEL=gpt-4o-mini
MAKE_WEBHOOK_URL=https://hook.eu2.make.com/ваш_webhook
ADMIN_CHAT_ID=ваш_chat_id
```

## Запуск

```bash
python bot.py
```

## Скрипты

### Установка ADMIN_CHAT_ID

Скрипт автоматически устанавливает `ADMIN_CHAT_ID` в `.env` файле:

```bash
python scripts/ensure_admin_chat_id.py
```

Скрипт:
- Создаёт `.env` из `.env.example`, если файла нет
- Добавляет `ADMIN_CHAT_ID`, если строки нет
- Обновляет значение, если оно отличается
- Идемпотентный — повторный запуск безопасен

**Как узнать свой chat_id:** напишите боту [@userinfobot](https://t.me/userinfobot) в Telegram.

## Настройка Make сценария

Рекомендуемая структура сценария:

1. **Webhooks → Custom webhook** — принимает JSON от бота
2. **Google Sheets → Add a Row** — записывает данные в таблицу "Входящие"
3. **Telegram → Send a Message** — отправляет уведомление вам

### Колонки для Google Sheets

| Колонка | Поле JSON | Описание |
|---------|-----------|----------|
| trace_id | `trace_id` | Уникальный ID сообщения (chat_id:message_id) |
| created_at | `created_at` | Дата и время в UTC |
| source | `source` | Источник (telegram) |
| chat_id | `chat_id` | ID чата |
| from_name | `user.name` | Имя отправителя |
| from_username | `user.username` | Username отправителя |
| text | `text` | Текст сообщения |
| intent | `intent` | Тип обращения |
| service | `service` | Услуга |
| confidence | `confidence` | Уверенность (0-1) |
| summary | `summary` | Краткое резюме |
| budget | `fields.budget` | Бюджет в рублях (число или пусто) |
| deadline | `fields.deadline_text` | Срок ("к пятнице", "до 10 февраля") |
| contact | `fields.contact` | Контакт (телефон/email/ник) |
| goal | `fields.goal` | Цель клиента |

### Пример JSON от бота

```json
{
  "trace_id": "123456789:55",
  "created_at": "2026-01-31T12:00:00Z",
  "source": "telegram",
  "chat_id": 123456789,
  "message_id": 55,
  "user": {
    "id": 111,
    "username": "username",
    "name": "Имя Фамилия"
  },
  "text": "Хочу заказать чат-бота для сайта, бюджет 50к, нужно к пятнице",
  "intent": "lead",
  "service": "gpt_assistants",
  "confidence": 0.92,
  "summary": "Заявка на разработку чат-бота для сайта",
  "fields": {
    "budget": 50000,
    "deadline_text": "к пятнице",
    "contact": null,
    "goal": "чат-бот для сайта"
  }
}
```

### Статусы лидов (inline-кнопки)

При каждом новом обращении админу приходит уведомление с inline-кнопками статусов:

| Статус | Описание |
|--------|----------|
| new | Новый лид |
| in_progress | В работе |
| booked | Забронирован/записан |
| closed | Закрыт |
| spam | Спам |

При нажатии кнопки бот отправляет POST на `MAKE_STATUS_WEBHOOK_URL`:

```json
{
  "action": "status_update",
  "trace_id": "123456789:55",
  "status": "in_progress",
  "changed_at": "2026-01-31T12:05:00Z"
}
```

Если `MAKE_STATUS_WEBHOOK_URL` не настроен — кнопки показываются, но при нажатии выводится сообщение "MAKE_STATUS_WEBHOOK_URL не настроен".

## Отладка

- **trace_id** в логах бота и в Make позволяет связать запрос пользователя с записью в таблице
- Если OpenAI API недоступен, бот продолжает работать с fallback-классификацией
- Все ошибки логируются в консоль в формате: `[TIMESTAMP] [LEVEL] [trace_id] message`
- При ошибках Make админу отправляется алерт в Telegram (если задан ADMIN_CHAT_ID)

### Примеры логов

```
[2026-01-31T12:00:00Z] [INFO] [-] Starting bot...
[2026-01-31T12:00:01Z] [INFO] [-] Bot started, polling...
[2026-01-31T12:00:15Z] [INFO] [123456789:55] Received message: Хочу заказать чат-бота...
[2026-01-31T12:00:16Z] [INFO] [123456789:55] Classified: lead/gpt_assistants
[2026-01-31T12:00:17Z] [INFO] [123456789:55] Sent to Make successfully
```

## Типы классификации

### Intent (тип обращения)

| Значение | Описание |
|----------|----------|
| lead | Потенциальный клиент, заявка на услугу |
| question | Вопрос про услуги, цены, процесс |
| support | Техническая проблема, ошибка |
| other | Всё остальное (приветствие, благодарность, не по теме) |

### Service (услуга)

| Значение | Описание |
|----------|----------|
| ai_agents | ИИ-агенты (агент с инструментами, автономные сценарии) |
| make_automation | Автоматизация на Make.com (сценарии, интеграции) |
| gpt_assistants | GPT-ассистенты/чат-боты (бот-ассистент, FAQ) |
| consultation | Консультация (разбор, стратегия, аудит) |
| unknown | Не удалось определить |

### Fields (дополнительные поля)

| Поле | Тип | Описание |
|------|-----|----------|
| budget | number/null | Бюджет в рублях. "50k" → 50000, "40-60к" → 40000 |
| deadline_text | string/null | Срок как написал клиент |
| contact | string/null | Телефон, email или ник |
| goal | string/null | Краткое описание цели клиента |

## Обработка ошибок

- При недоступности OpenAI API — fallback классификация (intent=other, service=unknown)
- При ошибке Make webhook — 2 ретрая с паузами 1с и 2с
- При финальной ошибке Make:
  - Пользователю: "Временно не получилось зафиксировать сообщение. Попробуйте чуть позже."
  - Админу (если ADMIN_CHAT_ID задан): алерт с trace_id и текстом сообщения
