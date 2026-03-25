import os

# Telegram secret for webhook verification
TELEGRAM_SECRET = os.environ.get("TELEGRAM_SECRET")

# Provider aliases and simple per-agent fallback chain (env-driven)
PROVIDER_ALIASES = {
    "llm": os.environ.get("PROVIDER_LLM", "openai"),
    "vision": os.environ.get("PROVIDER_VISION", "openai-vision"),
    "search": os.environ.get("PROVIDER_SEARCH", "duckduckgo"),
}
