"""
Тесты для build_payload и extract_goal.
Запуск: python test_payload.py
"""

from bot import build_payload
from classifier import extract_goal


def test_goal_always_present():
    """Проверяет, что goal всегда есть в payload."""

    # Случай 1: goal есть и не пустой
    classification_with_goal = {
        "intent": "lead",
        "service": "gpt_assistants",
        "confidence": 0.9,
        "summary": "Нужен бот",
        "fields": {
            "budget": 50000,
            "deadline_text": "к пятнице",
            "contact": "@user",
            "goal": "бот для записи клиентов"
        }
    }
    payload = build_payload(
        trace_id="123:1",
        created_at="2026-02-01T12:00:00Z",
        chat_id=123,
        message_id=1,
        user_info={"id": 123, "username": "user", "name": "User"},
        text="Нужен бот для записи",
        classification=classification_with_goal
    )
    assert "goal" in payload, "goal must be in payload"
    assert payload["goal"] == "бот для записи клиентов"
    print("[OK] Test 1: goal exists and correct")

    # Случай 2: goal = None
    classification_goal_none = {
        "intent": "question",
        "service": "unknown",
        "confidence": 0.5,
        "summary": "Вопрос",
        "fields": {
            "budget": None,
            "deadline_text": None,
            "contact": None,
            "goal": None
        }
    }
    payload = build_payload(
        trace_id="123:2",
        created_at="2026-02-01T12:00:00Z",
        chat_id=123,
        message_id=2,
        user_info={"id": 123, "username": "user", "name": "User"},
        text="Сколько стоит?",
        classification=classification_goal_none
    )
    assert "goal" in payload, "goal must be in payload even if None"
    assert payload["goal"] == "", "goal must be empty string, not None"
    print("[OK] Test 2: goal=None -> empty string")

    # Случай 3: fields отсутствует
    classification_no_fields = {
        "intent": "other",
        "service": "unknown",
        "confidence": 0.0,
        "summary": "Не понятно"
    }
    payload = build_payload(
        trace_id="123:3",
        created_at="2026-02-01T12:00:00Z",
        chat_id=123,
        message_id=3,
        user_info={"id": 123, "username": "user", "name": "User"},
        text="Привет",
        classification=classification_no_fields
    )
    assert "goal" in payload, "goal must be in payload even without fields"
    assert payload["goal"] == "", "goal must be empty string"
    print("[OK] Test 3: no fields -> goal is empty string")

    # Случай 4: goal с пробелами
    classification_goal_spaces = {
        "intent": "lead",
        "service": "ai_agents",
        "confidence": 0.8,
        "summary": "Агент",
        "fields": {
            "budget": None,
            "deadline_text": None,
            "contact": None,
            "goal": "  агент для поддержки  "
        }
    }
    payload = build_payload(
        trace_id="123:4",
        created_at="2026-02-01T12:00:00Z",
        chat_id=123,
        message_id=4,
        user_info={"id": 123, "username": "user", "name": "User"},
        text="Нужен агент",
        classification=classification_goal_spaces
    )
    assert payload["goal"] == "агент для поддержки", "goal must be stripped"
    print("[OK] Test 4: goal with spaces -> strip()")

    print("\n[SUCCESS] All payload tests passed!")


def test_extract_goal():
    """Тестирует fallback-извлечение goal из текста."""

    # Тест 1: "Хочу автоматизацию на Make"
    text1 = "Хочу автоматизацию на Make, бюджет 30к, до понедельника, @nikkk8"
    goal1 = extract_goal(text1)
    assert "автоматизаци" in goal1.lower(), f"Expected 'автоматизаци' in goal, got: {goal1}"
    print(f"[OK] Test 1: '{text1[:40]}...' -> '{goal1}'")

    # Тест 2: "Нужен бот для записи клиентов"
    text2 = "Нужен бот для записи клиентов, бюджет 50к, до пятницы"
    goal2 = extract_goal(text2)
    assert "бот" in goal2.lower(), f"Expected 'бот' in goal, got: {goal2}"
    print(f"[OK] Test 2: '{text2[:40]}...' -> '{goal2}'")

    # Тест 3: "Нужна интеграция с CRM"
    text3 = "Нужна интеграция с CRM, @username"
    goal3 = extract_goal(text3)
    assert "интеграци" in goal3.lower(), f"Expected 'интеграци' in goal, got: {goal3}"
    print(f"[OK] Test 3: '{text3[:40]}...' -> '{goal3}'")

    # Тест 4: Пустой текст
    goal4 = extract_goal("")
    assert goal4 == "", f"Expected empty string, got: {goal4}"
    print("[OK] Test 4: empty text -> empty goal")

    # Тест 5: Текст без ключевых слов
    text5 = "Привет, как дела?"
    goal5 = extract_goal(text5)
    assert goal5 == "", f"Expected empty string for greeting, got: {goal5}"
    print(f"[OK] Test 5: '{text5}' -> empty goal")

    print("\n[SUCCESS] All extract_goal tests passed!")


if __name__ == "__main__":
    test_goal_always_present()
    print()
    test_extract_goal()
