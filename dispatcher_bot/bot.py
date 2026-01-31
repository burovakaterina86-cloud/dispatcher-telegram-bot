"""
Telegram-бот "Диспетчер входящих".
Принимает сообщения, классифицирует через Claude, отправляет в Make.com.
"""

import logging
import sys
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Загружаем .env если есть (для локальной разработки)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import BOT_TOKEN, validate_config
from classifier import classify
from webhook import send_to_make, WebhookError


# Настройка логирования
class TraceFormatter(logging.Formatter):
    """Форматтер с поддержкой trace_id."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        level = record.levelname
        trace_id = getattr(record, "trace_id", "-")
        message = record.getMessage()
        return f"[{timestamp}] [{level}] [{trace_id}] {message}"


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(TraceFormatter())
logger.addHandler(handler)


def log_with_trace(level: int, trace_id: str, message: str) -> None:
    """Логирует сообщение с trace_id."""
    extra = {"trace_id": trace_id}
    logger.log(level, message, extra=extra)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает входящее текстовое сообщение."""
    message = update.message
    if not message or not message.text:
        return

    # Проверяем что текст не пустой
    text = message.text.strip()
    if not text:
        return

    # Формируем trace_id
    chat_id = message.chat_id
    message_id = message.message_id
    trace_id = f"{chat_id}:{message_id}"

    log_with_trace(logging.INFO, trace_id, f"Received message: {text[:50]}...")

    # Классифицируем сообщение
    try:
        classification = classify(text)
        log_with_trace(logging.INFO, trace_id, f"Classified: {classification['intent']}/{classification['service']}")
    except Exception as e:
        log_with_trace(logging.ERROR, trace_id, f"Classification error: {e}")
        classification = {
            "intent": "other",
            "service": "unknown",
            "confidence": 0.0,
            "summary": "Не удалось классифицировать"
        }

    # Формируем payload для Make
    user = message.from_user
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "trace_id": trace_id,
        "created_at": created_at,
        "source": "telegram",
        "chat_id": chat_id,
        "message_id": message_id,
        "user": {
            "id": user.id if user else None,
            "username": user.username if user else None,
            "name": user.full_name if user else None
        },
        "text": text,
        "intent": classification["intent"],
        "service": classification["service"],
        "confidence": classification["confidence"],
        "summary": classification["summary"]
    }

    # Отправляем в Make
    try:
        send_to_make(payload)
        log_with_trace(logging.INFO, trace_id, "Sent to Make successfully")
    except WebhookError as e:
        log_with_trace(logging.ERROR, trace_id, f"Make webhook failed: {e}")
        await message.reply_text(
            "Временно не удалось обработать сообщение. Попробуйте позже."
        )
        return

    # Отвечаем пользователю подтверждением
    confirmation = (
        f"Принято\n"
        f"Тип: {classification['intent']}\n"
        f"Услуга: {classification['service']}\n"
        f"Кратко: {classification['summary']}"
    )
    await message.reply_text(confirmation)


def main() -> None:
    """Запускает бота."""
    # Валидируем конфигурацию
    validate_config()

    log_with_trace(logging.INFO, "-", "Starting bot...")

    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчик текстовых сообщений (не команд)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Запускаем polling
    log_with_trace(logging.INFO, "-", "Bot started, polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
