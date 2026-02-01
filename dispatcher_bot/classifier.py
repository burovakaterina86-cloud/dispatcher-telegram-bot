"""
Классификация сообщений через OpenAI API.
"""

import json
import re
from typing import Any

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TIMEOUT


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

Дополнительные поля (fields):
- budget — бюджет в рублях (число или null). "50k" = 50000, "50-60к" = 50000 (нижняя граница)
- deadline_text — срок как написал клиент ("к пятнице", "до 10 февраля") или null
- contact — телефон/email/ник если есть, или null
- goal — кратко что хочет клиент ("бот для записи клиентов") или null

JSON схема:
{"intent": "lead", "service": "make_automation", "confidence": 0.85, "summary": "краткое резюме на русском", "fields": {"budget": 50000, "deadline_text": "к пятнице", "contact": null, "goal": "бот для записи"}}"""


FALLBACK_FIELDS = {
    "budget": None,
    "deadline_text": None,
    "contact": None,
    "goal": None
}

FALLBACK_RESULT = {
    "intent": "other",
    "service": "unknown",
    "confidence": 0.0,
    "summary": "Не удалось классифицировать",
    "fields": FALLBACK_FIELDS.copy()
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

    # Пробуем найти JSON объект в тексте (с вложенными объектами)
    brace_count = 0
    start_idx = -1
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                try:
                    return json.loads(text[start_idx:i + 1])
                except json.JSONDecodeError:
                    start_idx = -1

    return None


def _parse_budget(value: Any) -> int | None:
    """Парсит бюджет в число рублей."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        # Убираем пробелы и приводим к нижнему регистру
        s = value.lower().replace(" ", "").replace(",", ".")

        # "50k", "50к" -> 50000
        if s.endswith("k") or s.endswith("к"):
            try:
                return int(float(s[:-1]) * 1000)
            except ValueError:
                pass

        # Диапазон "40-60" или "40-60k" -> берём нижнюю границу
        range_match = re.match(r"(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*([kк])?", s)
        if range_match:
            try:
                lower = float(range_match.group(1))
                multiplier = 1000 if range_match.group(3) else 1
                return int(lower * multiplier)
            except ValueError:
                pass

        # Простое число
        try:
            return int(float(s))
        except ValueError:
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

    # fields
    raw_fields = data.get("fields", {}) or {}
    fields = {
        "budget": _parse_budget(raw_fields.get("budget")),
        "deadline_text": raw_fields.get("deadline_text") if isinstance(raw_fields.get("deadline_text"), str) else None,
        "contact": raw_fields.get("contact") if isinstance(raw_fields.get("contact"), str) else None,
        "goal": raw_fields.get("goal") if isinstance(raw_fields.get("goal"), str) else None,
    }
    result["fields"] = fields

    return result


def classify(text: str) -> dict[str, Any]:
    """
    Классифицирует текст сообщения через OpenAI API.

    Returns:
        dict с ключами: intent, service, confidence, summary, fields
    """
    # Если нет API ключа — сразу fallback
    if not OPENAI_API_KEY:
        return FALLBACK_RESULT.copy()

    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=512,
            timeout=OPENAI_TIMEOUT,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ]
        )

        # Извлекаем текст ответа
        response_text = response.choices[0].message.content if response.choices else ""

        # Парсим JSON
        parsed = _extract_json(response_text)
        if parsed is None:
            return FALLBACK_RESULT.copy()

        # Валидируем и возвращаем
        return _validate_result(parsed)

    except Exception:
        # Любая ошибка (сеть, API, парсинг) — fallback
        return FALLBACK_RESULT.copy()
