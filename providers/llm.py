def run_llm(input: dict, context: dict = None) -> dict:
    # Lightweight placeholder for LLM-based generation
    prompt = input.get("prompt", "")
    _ctx = context or {}
    # Return structured JSON-ish payload
    return {
        "summary": "LLM plan generated from prompt",
        "user_visible_text": f"Plan generated for: {prompt}",
        "artifacts": [],
        "handoff": None,
        "citations": [],
        "confidence": 0.75,
        "internal_notes": "stubbed-llm",
    }
