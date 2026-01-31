"""
Отправка данных в Make.com webhook с ретраями.
"""

import time
from typing import Any

import requests

from config import MAKE_WEBHOOK_URL, MAKE_TIMEOUT, MAKE_RETRIES


class WebhookError(Exception):
    """Ошибка при отправке в webhook."""
    pass


def send_to_make(payload: dict[str, Any]) -> None:
    """
    Отправляет JSON payload в Make webhook.

    Args:
        payload: Данные для отправки

    Raises:
        WebhookError: При ошибке после всех попыток
    """
    delays = [1, 2]  # Паузы между ретраями в секундах
    last_error = None

    for attempt in range(MAKE_RETRIES + 1):
        try:
            response = requests.post(
                MAKE_WEBHOOK_URL,
                json=payload,
                timeout=MAKE_TIMEOUT,
                headers={"Content-Type": "application/json"}
            )

            # Успешный ответ
            if 200 <= response.status_code < 300:
                return

            # 4xx — ошибка в данных, не ретраим
            if 400 <= response.status_code < 500:
                raise WebhookError(f"HTTP {response.status_code}: {response.text[:200]}")

            # 5xx — серверная ошибка, ретраим
            last_error = f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            last_error = "timeout"

        except requests.exceptions.ConnectionError as e:
            last_error = f"connection error: {str(e)[:100]}"

        except requests.exceptions.RequestException as e:
            last_error = f"request error: {str(e)[:100]}"

        # Пауза перед следующей попыткой (если есть)
        if attempt < MAKE_RETRIES:
            time.sleep(delays[attempt])

    # Все попытки исчерпаны
    raise WebhookError(f"Make webhook failed after {MAKE_RETRIES + 1} attempts: {last_error}")
