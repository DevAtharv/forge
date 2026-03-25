from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge.config import Settings


def main() -> int:
    load_dotenv(dotenv_path=ROOT / ".env")
    settings = Settings.from_env()

    required = {
        "TELEGRAM_TOKEN": settings.telegram_token,
        "WEBHOOK_SECRET": settings.webhook_secret,
        "GROQ_API_KEY": settings.groq_api_key,
        "NVIDIA_API_KEY": settings.nvidia_api_key,
        "OPENROUTER_API_KEY": settings.openrouter_api_key,
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_ANON_KEY": settings.supabase_anon_key,
        "SUPABASE_KEY": settings.supabase_key,
    }

    print("Forge readiness check")
    print("=" * 22)

    missing = []
    for key, value in required.items():
        present = bool(value)
        print(f"{key:<20} {'OK' if present else 'MISSING'}")
        if not present:
            missing.append(key)

    print()
    if missing:
        print("Blocking items:")
        for key in missing:
            print(f"- {key}")
        return 1

    print("All required env vars are present.")
    print("Next steps:")
    print("- Apply sql/schema.sql in Supabase if you have not done that already.")
    print("- Deploy the app to a public HTTPS URL.")
    print("- Run scripts/set_telegram_webhook.py with that public URL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
