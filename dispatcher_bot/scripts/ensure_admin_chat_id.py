#!/usr/bin/env python3
"""
Скрипт для установки ADMIN_CHAT_ID в .env файле.
Идемпотентный: повторный запуск не меняет ничего лишнего.
"""

import os
import re
import shutil
from pathlib import Path

ADMIN_CHAT_ID = "943657550"
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
ENV_FILE = PROJECT_DIR / ".env"
ENV_EXAMPLE = PROJECT_DIR / ".env.example"


def ensure_admin_chat_id() -> None:
    """Устанавливает ADMIN_CHAT_ID=943657550 в .env файле."""

    # Если .env не существует — копируем из .env.example
    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy(ENV_EXAMPLE, ENV_FILE)
        else:
            # Создаём пустой .env
            ENV_FILE.touch()

    # Читаем содержимое
    content = ENV_FILE.read_text(encoding="utf-8")

    # Проверяем наличие ADMIN_CHAT_ID
    pattern = r"^ADMIN_CHAT_ID\s*=.*$"

    if re.search(pattern, content, re.MULTILINE):
        # Строка есть — заменяем значение
        new_content = re.sub(
            pattern,
            f"ADMIN_CHAT_ID={ADMIN_CHAT_ID}",
            content,
            flags=re.MULTILINE
        )
    else:
        # Строки нет — добавляем в конец
        # Убеждаемся что есть перенос строки в конце
        if content and not content.endswith("\n"):
            content += "\n"
        new_content = content + f"ADMIN_CHAT_ID={ADMIN_CHAT_ID}\n"

    # Записываем только если что-то изменилось
    if new_content != content:
        ENV_FILE.write_text(new_content, encoding="utf-8")

    print(f"ADMIN_CHAT_ID ensured: {ADMIN_CHAT_ID}")


if __name__ == "__main__":
    ensure_admin_chat_id()
