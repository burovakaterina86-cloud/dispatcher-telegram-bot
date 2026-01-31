"""
Классификация сообщений через Claude API.
"""

import json
import re
from typing import Any

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_TIMEOUT


SYSTEM_PROMPT = """Ты диспетчер входящих обращений студии.
Классифицируй сообщение и верни ТОЛЬКО валидный JSON.
Используй обычные двойные кавычки. Без markdown. Без пояснений. Без текста до или после JSON.
Если не уверен — ставь service="unknown" и confidence низкое.

Типы обращений (intent):
- lead — потенциальный клиент, заявка на услугу
- question — вопрос про услуги, цены, процесс
- support — техническая проблема, ошибка, "не работает"
- other — всё остальное (приветствие, благодарность, не по теме)

Услуги (service):
- ai_agents — ИИ-агенты (агент с инструментами, автономные сценарии, 24/7 агент)
- make_automation — автоматизация на Make.com (сценарии, интеграции, webhooks)
- gpt_assistants — GPT-ассистенты/чат-боты (бот-ассистент, FAQ, помощник по услугам)
- consultation — консультация (разбор, стратегия, аудит, созвон/чат)
- unknown — не удалось определить

JSON схема:
{"intent": "lead", "service": "make_automation", "confidence": 0.85, "summary": "краткое резюме на русском"}"""


FALLBACK_RESULT = {
    "intent": "other",
    "service": "unknown",
    "confidence": 0.0,
    "summary": "Не удалось классифицировать"
}

VALID_INTENTS = {"lead", "question", "support", "other"}
VALID_SERVICES = {"ai_agents", "make_automation", "gpt_assistants", "consultation", "unknown"}


def _extract_json(text: str) -> dict[str, Any] | None:
    """Извлекает JSON из текста, даже если обёрнут в markdown."""
    # Пробуем напрямую распарсить
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Пробуем извлечь из markdown блока ```json ... ```
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Пробуем найти просто JSON объект в тексте
    json_match = re.search(r"\{[^{}]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _validate_result(data: dict[str, Any]) -> dict[str, Any]:
    """Валидирует и нормализует результат классификации."""
    result = {}

    # intent
    intent = data.get("intent", "other")
    result["intent"] = intent if intent in VALID_INTENTS else "other"

    # service
    service = data.get("service", "unknown")
    result["service"] = service if service in VALID_SERVICES else "unknown"

    # confidence
    try:
        confidence = float(data.get("confidence", 0.0))
        result["confidence"] = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        result["confidence"] = 0.0

    # summary
    summary = data.get("summary", "")
    result["summary"] = str(summary) if summary else "Нет описания"

    return result


def classify(text: str) -> dict[str, Any]:
    """
    Классифицирует текст сообщения через Claude API.

    Returns:
        dict с ключами: intent, service, confidence, summary
    """
    # Если нет API ключа или модели — сразу fallback
    if not ANTHROPIC_API_KEY or not CLAUDE_MODEL:
        return FALLBACK_RESULT.copy()

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=256,
            timeout=CLAUDE_TIMEOUT,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": text}
            ]
        )

        # Извлекаем текст ответа
        response_text = message.content[0].text if message.content else ""

        # Парсим JSON
        parsed = _extract_json(response_text)
        if parsed is None:
            return FALLBACK_RESULT.copy()

        # Валидируем и возвращаем
        return _validate_result(parsed)

    except Exception:
        # Любая ошибка (сеть, API, парсинг) — fallback
        return FALLBACK_RESULT.copy()
