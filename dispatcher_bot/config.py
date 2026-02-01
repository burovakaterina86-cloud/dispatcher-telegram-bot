"""
Конфигурация бота из переменных окружения.
"""

import os
import sys


# Таймауты (секунды)
OPENAI_TIMEOUT = 25
MAKE_TIMEOUT = 25
MAKE_RETRIES = 2

# Обязательные переменные
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")

# OpenAI (опционально, без них классификатор работает в fallback режиме)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Опциональный chat_id админа для алертов
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

# Опциональный webhook для обновления статусов лидов
MAKE_STATUS_WEBHOOK_URL = os.environ.get("MAKE_STATUS_WEBHOOK_URL")


def validate_config() -> None:
    """Проверяет наличие обязательных переменных окружения."""
    missing = []

    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")

    if not MAKE_WEBHOOK_URL:
        missing.append("MAKE_WEBHOOK_URL")

    if missing:
        print(f"[ERROR] Отсутствуют обязательные переменные окружения: {', '.join(missing)}")
        sys.exit(1)

    if not OPENAI_API_KEY:
        print("[WARNING] OPENAI_API_KEY не задан. Классификация будет в fallback режиме.")

    if not MAKE_STATUS_WEBHOOK_URL:
        print("[WARNING] MAKE_STATUS_WEBHOOK_URL не задан. Обновление статусов в Make недоступно.")
