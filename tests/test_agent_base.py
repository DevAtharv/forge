from forge.agents.base import coerce_agent_result


def test_coerce_agent_result_handles_partial_json_schema() -> None:
    payload = """
{
  "summary": "Looks good",
  "user_visible_text": "The implementation is solid and ready for use.",
  "artifacts": [
    {"name": "app.py", "content": "print('ok')", "language": "python"},
    {"bad": "shape"}
  ],
  "citations": [
    {"title": "FastAPI docs", "url": "https://fastapi.tiangolo.com/"}
  ],
  "confidence": "0.9"
}
""".strip()

    result = coerce_agent_result("reviewer", payload)

    assert result.agent == "reviewer"
    assert result.user_visible_text.startswith("The implementation is solid")
    assert len(result.artifacts) == 1
    assert result.artifacts[0].name == "app.py"
    assert len(result.citations) == 1
    assert result.citations[0].title == "FastAPI docs"
    assert result.confidence == 0.9
