"""
Send entries from output/telegram_bot.json that have telegram_sent: false to the Telegram group.

Usage:
  python send_telegram_pending.py              → send only entries with telegram_sent: false
  python send_telegram_pending.py --resend-all → set ALL entries to unsent, then send everything once
"""

import argparse
import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
TELEGRAM_BOT_FILE = os.path.join(OUTPUT_DIR, "telegram_bot.json")


def _send_one_telegram_message(text: str, bot_token: str, chat_id: str) -> tuple[bool, str]:
    """Returns (success, error_message)."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        if r.status_code == 200:
            return True, ""
        try:
            err = r.json().get("description", r.text[:200])
        except Exception:
            err = r.text[:200] if r.text else str(r.status_code)
        return False, err
    except Exception as e:
        return False, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send telegram_sent: false entries to Telegram group.")
    parser.add_argument("--resend-all", action="store_true", help="Set all telegram_sent to false, then send everything once")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID")
    if not token or not chat_id:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_GROUP_CHAT_ID in .env")
        return

    if not os.path.exists(TELEGRAM_BOT_FILE):
        print(f"No {TELEGRAM_BOT_FILE} found. Run run_keywords.py first.")
        return

    try:
        with open(TELEGRAM_BOT_FILE, "r", encoding="utf-8") as f:
            raw = f.read().strip()
            bot_list = json.loads(raw) if raw else []
        if not isinstance(bot_list, list):
            bot_list = []
    except (json.JSONDecodeError, TypeError):
        bot_list = []

    if args.resend_all:
        for e in bot_list:
            e["telegram_sent"] = False
        print("Marked all entries as unsent (telegram_sent: false).")

    pending = [e for e in bot_list if e.get("telegram_sent") is False]
    if not pending:
        print("Nothing to send (no entries with telegram_sent: false).")
        if args.resend_all:
            with open(TELEGRAM_BOT_FILE, "w", encoding="utf-8") as f:
                json.dump(bot_list, f, ensure_ascii=False, indent=2)
        return

    total = len(pending)
    print(f"Sending {total} URLs (one per message). Progress below:")
    sent_count = 0
    first_error = ""
    for i, e in enumerate(pending, 1):
        link = e.get("url", "")
        if not link:
            continue
        kw = e.get("keyword", "")
        text = f"Keyword: {kw}\n{link}"
        ok, err = _send_one_telegram_message(text, token, chat_id)
        if ok:
            e["telegram_sent"] = True
            sent_count += 1
        elif not first_error:
            first_error = err
        if i % 10 == 0 or i == total:
            print(f"  {i}/{total} sent (ok: {sent_count})")
        time.sleep(0.2)
    with open(TELEGRAM_BOT_FILE, "w", encoding="utf-8") as f:
        json.dump(bot_list, f, ensure_ascii=False, indent=2)

    if sent_count:
        print(f"Done. Sent {sent_count}/{total} URLs to Telegram.")
    else:
        print(f"Failed. Telegram API error: {first_error}")
        print("Check: (1) Bot is in the group, (2) TELEGRAM_GROUP_CHAT_ID is correct (negative number).")


if __name__ == "__main__":
    main()
