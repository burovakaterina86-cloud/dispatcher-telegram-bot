# Диспетчер входящих — Telegram Bot

Telegram-бот для автоматической классификации входящих обращений. Использует Claude API для понимания типа обращения (intent) и услуги (service). Отправляет структурированные данные в Make.com для дальнейшей обработки и автоматизации.

## Требования

- Python 3.11+

## Установка

```bash
pip install -r requirements.txt
```

## Получение токенов

### Telegram Bot Token

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям, задайте имя и username бота
4. Скопируйте полученный токен

### Claude API Key

1. Перейдите на [console.anthropic.com](https://console.anthropic.com)
2. Войдите или зарегистрируйтесь
3. Перейдите в раздел **API Keys**
4. Нажмите **Create Key**
5. Скопируйте ключ (он показывается только один раз)

### Make.com Webhook URL

1. Создайте новый сценарий в [Make.com](https://www.make.com)
2. Добавьте модуль **Webhooks → Custom webhook**
3. Нажмите **Add** для создания нового webhook
4. Скопируйте URL webhook

## Настройка

```bash
cp .env.example .env
```

Откройте файл `.env` и заполните переменные:

```
BOT_TOKEN=ваш_токен_telegram_бота
ANTHROPIC_API_KEY=ваш_ключ_claude_api
CLAUDE_MODEL=claude-sonnet-4-20250514
MAKE_WEBHOOK_URL=https://hook.eu2.make.com/ваш_webhook
```

**Примечание:** `ANTHROPIC_API_KEY` опционален. Без него бот будет работать в fallback-режиме, классифицируя все сообщения как `intent=other`, `service=unknown`.

## Запуск

```bash
python bot.py
```

## Настройка Make сценария

Рекомендуемая структура сценария:

1. **Webhooks → Custom webhook** — принимает JSON от бота
2. **Google Sheets → Add a Row** — записывает данные в таблицу "Входящие"
3. **Telegram → Send a Message** — отправляет уведомление вам

### Колонки для Google Sheets

| Колонка | Описание |
|---------|----------|
| trace_id | Уникальный ID сообщения (chat_id:message_id) |
| created_at | Дата и время в UTC |
| source | Источник (telegram) |
| chat_id | ID чата |
| from_name | Имя отправителя |
| from_username | Username отправителя |
| text | Текст сообщения |
| intent | Тип обращения (lead/question/support/other) |
| service | Услуга (ai_agents/make_automation/gpt_assistants/consultation/unknown) |
| confidence | Уверенность классификации (0-1) |
| summary | Краткое резюме на русском |

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
  "text": "Хочу заказать чат-бота для сайта",
  "intent": "lead",
  "service": "gpt_assistants",
  "confidence": 0.92,
  "summary": "Заявка на разработку чат-бота для сайта"
}
```

## Отладка

- **trace_id** в логах бота и в Make позволяет связать запрос пользователя с записью в таблице
- Если Claude API недоступен, бот продолжает работать с fallback-классификацией
- Все ошибки логируются в консоль в формате: `[TIMESTAMP] [LEVEL] [trace_id] message`

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
