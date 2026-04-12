from forge.workers.processor import (
    _extract_link_code,
    _looks_like_greeting,
    _normalize_telegram_command_text,
    _parse_project_command,
)


def test_normalize_strips_bot_suffix_from_command() -> None:
    assert _normalize_telegram_command_text("/start@ForggeBot") == "/start"
    assert _normalize_telegram_command_text("/help@my_bot") == "/help"
    assert _normalize_telegram_command_text("/build@ForgeBot a cafe site") == "/build a cafe site"
    assert _normalize_telegram_command_text("  /projects@bot  ") == "/projects"


def test_greeting_recognizes_start_with_bot_suffix() -> None:
    assert _looks_like_greeting("/start@SomeBot")
    assert _looks_like_greeting("/start")


def test_parse_command_after_suffix() -> None:
    assert _parse_project_command("/build@MyBot landing page") == ("/build", "landing page")
    assert _parse_project_command("/help@MyBot") == ("/help", "")


def test_link_code_after_suffix() -> None:
    assert _extract_link_code("/link@MyBot AB12CD") == "AB12CD"
