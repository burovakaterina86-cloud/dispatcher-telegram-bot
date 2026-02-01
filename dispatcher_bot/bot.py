"""
Telegram-бот "Диспетчер входящих".
Принимает сообщения, классифицирует через OpenAI, отправляет в Make.com.
"""

import logging
import sys
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, CommandHandler, filters, ContextTypes

# Загружаем .env если есть (для локальной разработки)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import BOT_TOKEN, ADMIN_CHAT_ID, MAKE_STATUS_WEBHOOK_URL, validate_config
from classifier import classify
from webhook import send_to_make, send_status_update_to_make, WebhookError


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
# Используем UTF-8 для корректного вывода эмодзи в Windows
handler = logging.StreamHandler(sys.stdout)
handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
handler.setFormatter(TraceFormatter())
logger.addHandler(handler)


# ==================== КОНСТАНТЫ ====================

# Статусы лидов (для админа)
# Коды статусов (ASCII, для callback_data)
LEAD_STATUSES = ["new", "in_progress", "booked", "closed", "spam"]

# Русские подписи для inline-кнопок и отображения
STATUS_LABELS = {
    "new": "🆕 новая заявка",
    "in_progress": "🛠 в работе",
    "booked": "📅 созвон назначен",
    "closed": "✅ закрыто",
    "spam": "🚫 спам"
}

# Тексты кнопок ReplyKeyboard (для пользователя)
BTN_NEW_REQUEST = "📝 Оставить заявку"
BTN_HOW_TO = "ℹ️ Как написать заявку"

# Множество текстов кнопок для быстрой проверки
BUTTON_TEXTS = {BTN_NEW_REQUEST, BTN_HOW_TO}

# Тексты сообщений
START_MESSAGE = """Привет! Я диспетчер входящих Буровой Екатерины.

Я принимаю обращения 4 типов:
1) лид — заявка на услугу
2) вопрос — цены/процесс
3) поддержка — что-то не работает
4) консультация — хочу разбор

Напиши одним сообщением: что нужно + бюджет (если есть) + срок (если есть) + контакт.

Примеры:
— Нужен бот записи, бюджет 50к, срок до пятницы, @username
— Бот не отвечает, ошибка при оплате, прикрепляю скрин, @username
— Хочу консультацию по Make на этой неделе, 1 час, @username"""

NEW_REQUEST_MESSAGE = """Ок 🙂 Напиши одним сообщением:
— что нужно
— бюджет (если есть)
— срок (если есть)
— контакт

Пример: Нужен бот записи, бюджет 50к, срок до пятницы, @username"""

HELP_MESSAGE = """Шаблон:
что нужно — бюджет — срок — контакт

Пример: Сколько стоит бот записи и какие сроки? @username"""


# ==================== УТИЛИТЫ ====================

def build_payload(
    trace_id: str,
    created_at: str,
    chat_id: int,
    message_id: int,
    user_info: dict,
    text: str,
    classification: dict
) -> dict:
    """
    Собирает payload для MAKE_WEBHOOK_URL.
    Гарантирует наличие ключа 'goal' (даже если пустая строка).
    """
    # Извлекаем goal из fields и нормализуем
    fields = classification.get("fields", {}) or {}
    goal = (fields.get("goal") or "").strip()

    return {
        "trace_id": trace_id,
        "created_at": created_at,
        "source": "telegram",
        "chat_id": chat_id,
        "message_id": message_id,
        "user": user_info,
        "text": text,
        "intent": classification.get("intent", "other"),
        "service": classification.get("service", "unknown"),
        "confidence": classification.get("confidence", 0.0),
        "summary": classification.get("summary", ""),
        "goal": goal,  # Всегда присутствует, даже если пустая строка
        "budget": fields.get("budget"),
        "deadline_text": fields.get("deadline_text"),
        "contact": fields.get("contact"),
    }


def log_with_trace(level: int, trace_id: str, message: str) -> None:
    """Логирует сообщение с trace_id."""
    extra = {"trace_id": trace_id}
    logger.log(level, message, extra=extra)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создаёт основную клавиатуру для пользователя."""
    keyboard = [
        [KeyboardButton(BTN_NEW_REQUEST), KeyboardButton(BTN_HOW_TO)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def build_status_keyboard(trace_id: str) -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру со статусами для админа."""
    buttons = [
        InlineKeyboardButton(
            text=STATUS_LABELS[status],
            callback_data=f"status|{trace_id}|{status}"
        )
        for status in LEAD_STATUSES
    ]
    return InlineKeyboardMarkup([buttons])


# ==================== КОМАНДЫ ====================

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /start."""
    message = update.message
    if not message:
        return

    await message.reply_text(
        START_MESSAGE,
        reply_markup=get_main_keyboard()
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /help."""
    message = update.message
    if not message:
        return

    await message.reply_text(
        HELP_MESSAGE,
        reply_markup=get_main_keyboard()
    )


# ==================== КНОПКИ REPLYKEYBOARD ====================

async def handle_button_new_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопку '📝 Оставить заявку'."""
    message = update.message
    if not message:
        return

    await message.reply_text(
        NEW_REQUEST_MESSAGE,
        reply_markup=get_main_keyboard()
    )


async def handle_button_how_to(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопку 'ℹ️ Как написать заявку'."""
    message = update.message
    if not message:
        return

    await message.reply_text(
        HELP_MESSAGE,
        reply_markup=get_main_keyboard()
    )


# ==================== АДМИН-УВЕДОМЛЕНИЯ ====================

async def send_admin_notification(
    context: ContextTypes.DEFAULT_TYPE,
    trace_id: str,
    classification: dict,
    user_info: dict,
    text: str
) -> None:
    """Отправляет уведомление админу о новом обращении с кнопками статуса."""
    if not ADMIN_CHAT_ID:
        return

    try:
        admin_id = int(ADMIN_CHAT_ID)
        short_text = text[:200] + "..." if len(text) > 200 else text

        message_text = (
            f"Новое обращение\n"
            f"trace_id: {trace_id}\n"
            f"Тип: {classification['intent']}\n"
            f"Услуга: {classification['service']}\n"
            f"Кратко: {classification['summary']}\n\n"
            f"От: {user_info.get('name', 'N/A')} (@{user_info.get('username', 'N/A')})\n\n"
            f"Текст: {short_text}"
        )

        keyboard = build_status_keyboard(trace_id)
        await context.bot.send_message(
            chat_id=admin_id,
            text=message_text,
            reply_markup=keyboard
        )
    except Exception as e:
        log_with_trace(logging.ERROR, trace_id, f"Failed to send admin notification: {e}")


async def send_admin_alert(context: ContextTypes.DEFAULT_TYPE, trace_id: str, error_msg: str, original_text: str) -> None:
    """Отправляет алерт админу в Telegram об ошибке."""
    if not ADMIN_CHAT_ID:
        return

    try:
        admin_id = int(ADMIN_CHAT_ID)
        short_text = original_text[:100] + "..." if len(original_text) > 100 else original_text
        alert = f"Make error | trace_id={trace_id} | err={error_msg[:50]}\n\nТекст: {short_text}"
        await context.bot.send_message(chat_id=admin_id, text=alert)
    except Exception as e:
        log_with_trace(logging.ERROR, trace_id, f"Failed to send admin alert: {e}")


# ==================== CALLBACK (INLINE КНОПКИ СТАТУСА) ====================

async def handle_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопку статуса (для админа)."""
    query = update.callback_query
    if not query or not query.data:
        return

    # Парсим callback_data: "status|<trace_id>|<status_code>"
    parts = query.data.split("|")
    if len(parts) != 3 or parts[0] != "status":
        await query.answer("Неверный формат данных")
        return

    _, trace_id, status_code = parts

    if status_code not in LEAD_STATUSES:
        await query.answer("Неизвестный статус")
        return

    # Получаем русский статус с эмодзи
    status_ru = STATUS_LABELS.get(status_code, status_code)

    log_with_trace(logging.INFO, trace_id, f"Status button pressed: {status_code}")

    # Проверяем настроен ли webhook
    if not MAKE_STATUS_WEBHOOK_URL:
        await query.answer("MAKE_STATUS_WEBHOOK_URL не настроен")
        log_with_trace(logging.WARNING, trace_id, "MAKE_STATUS_WEBHOOK_URL not configured")
        return

    # Формируем payload для обновления статуса
    changed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "action": "status_update",
        "trace_id": trace_id,
        "status": status_ru,           # Русский статус с эмодзи (для таблицы)
        "status_code": status_code,    # ASCII код (для отладки)
        "changed_at": changed_at
    }

    # Отправляем в Make
    try:
        send_status_update_to_make(payload)
        log_with_trace(logging.INFO, trace_id, f"Status update sent: {status_code} -> {status_ru}")

        # Успех — отвечаем на callback и редактируем сообщение
        await query.answer(f"Статус: {status_ru}")

        # Редактируем сообщение, добавляя русский статус
        original_text = query.message.text if query.message else ""
        new_text = f"[Статус: {status_ru}]\n\n{original_text}"

        await query.edit_message_text(
            text=new_text,
            reply_markup=build_status_keyboard(trace_id)
        )

    except (WebhookError, ValueError) as e:
        error_msg = str(e)
        log_with_trace(logging.ERROR, trace_id, f"Status update failed: {error_msg}")

        await query.answer("Не удалось обновить статус")

        # Отправляем админу сообщение об ошибке
        if ADMIN_CHAT_ID:
            try:
                admin_id = int(ADMIN_CHAT_ID)
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"Ошибка обновления статуса\ntrace_id: {trace_id}\nstatus: {status_ru}\nerror: {error_msg[:100]}"
                )
            except Exception:
                pass


# ==================== ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает входящее текстовое сообщение.
    Классифицирует и отправляет в Make.

    ИСКЛЮЧЕНИЯ (не отправляются в Make):
    - Команды (начинаются с "/")
    - Тексты кнопок ReplyKeyboard
    """
    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()
    if not text:
        return

    # ===== ИСКЛЮЧЕНИЕ 1: Команды =====
    # Команды обрабатываются отдельными handlers (CommandHandler),
    # но на всякий случай проверяем здесь тоже
    if text.startswith("/"):
        return

    # ===== ИСКЛЮЧЕНИЕ 2: Тексты кнопок ReplyKeyboard =====
    # Кнопки обрабатываются отдельными handlers с фильтром по точному тексту
    if text in BUTTON_TEXTS:
        return

    # ===== ОСНОВНАЯ ЛОГИКА: Классификация + Make =====

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
            "summary": "Не удалось классифицировать",
            "fields": {
                "budget": None,
                "deadline_text": None,
                "contact": None,
                "goal": None
            }
        }

    # Формируем payload для Make
    user = message.from_user
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    user_info = {
        "id": user.id if user else None,
        "username": user.username if user else None,
        "name": user.full_name if user else None
    }

    payload = build_payload(
        trace_id=trace_id,
        created_at=created_at,
        chat_id=chat_id,
        message_id=message_id,
        user_info=user_info,
        text=text,
        classification=classification
    )

    # Диагностика (временно)
    print("OUTGOING goal:", repr(payload.get("goal")))
    print("OUTGOING text:", payload.get("text", "")[:120])

    # Отправляем в Make
    try:
        send_to_make(payload)
        log_with_trace(logging.INFO, trace_id, "Sent to Make successfully")
    except WebhookError as e:
        error_msg = str(e)
        log_with_trace(logging.ERROR, trace_id, f"Make webhook failed: {error_msg}")

        # Отправляем алерт админу
        await send_admin_alert(context, trace_id, error_msg, text)

        # Сообщаем пользователю
        await message.reply_text(
            "Временно не получилось зафиксировать сообщение. Попробуйте чуть позже."
        )
        return

    # Отправляем уведомление админу с кнопками статуса
    await send_admin_notification(context, trace_id, classification, user_info, text)

    # Отвечаем пользователю подтверждением
    confirmation = (
        f"Принято\n"
        f"Тип: {classification['intent']}\n"
        f"Услуга: {classification['service']}\n"
        f"Кратко: {classification['summary']}"
    )
    await message.reply_text(confirmation, reply_markup=get_main_keyboard())


# ==================== MAIN ====================

def main() -> None:
    """Запускает бота."""
    # Валидируем конфигурацию
    validate_config()

    log_with_trace(logging.INFO, "-", "Starting bot...")

    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # ----- Команды -----
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))

    # ----- Кнопки ReplyKeyboard (фильтр по ТОЧНОМУ тексту) -----
    # Эти handlers срабатывают РАНЬШЕ общего handle_message
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_NEW_REQUEST}$"), handle_button_new_request)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_HOW_TO}$"), handle_button_how_to)
    )

    # ----- Общий обработчик текстовых сообщений -----
    # Срабатывает на всё остальное (не команды, не кнопки)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # ----- Callback-запросы (inline кнопки статуса для админа) -----
    application.add_handler(
        CallbackQueryHandler(handle_status_callback, pattern=r"^status\|")
    )

    # Запускаем polling
    log_with_trace(logging.INFO, "-", "Bot started, polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
