"""
Конфигурация бота из переменных окружения.
"""

import os
import sys


# Таймауты (секунды)
CLAUDE_TIMEOUT = 25
MAKE_TIMEOUT = 25
MAKE_RETRIES = 2

# Обязательные переменные
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")

# Опциональные переменные (без них классификатор работает в fallback режиме)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL")


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

    # Если есть API ключ, должна быть и модель
    if ANTHROPIC_API_KEY and not CLAUDE_MODEL:
        print("[WARNING] ANTHROPIC_API_KEY задан, но CLAUDE_MODEL не указан. Классификация будет в fallback режиме.")
