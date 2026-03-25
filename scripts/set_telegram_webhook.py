from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge.config import Settings


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register the Forge Telegram webhook.")
    parser.add_argument("--base-url", required=True, help="Public HTTPS base URL, for example https://forge-bot.onrender.com")
    parser.add_argument("--drop-pending-updates", action="store_true", help="Drop any pending Telegram updates when setting the webhook")
    args = parser.parse_args()

    load_dotenv(dotenv_path=ROOT / ".env")
    settings = Settings.from_env()

    if not settings.telegram_token:
        print("TELEGRAM_TOKEN is missing.")
        return 1
    if not settings.webhook_secret:
        print("WEBHOOK_SECRET is missing.")
        return 1

    base_url = normalize_base_url(args.base_url)
    if not base_url.startswith("https://"):
        print("The webhook base URL must use https://")
        return 1

    webhook_url = f"{base_url}/webhook"
    endpoint = f"https://api.telegram.org/bot{settings.telegram_token}/setWebhook"
    payload = {
        "url": webhook_url,
        "secret_token": settings.webhook_secret,
        "drop_pending_updates": args.drop_pending_updates,
    }

    response = requests.post(endpoint, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    print(data)
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
