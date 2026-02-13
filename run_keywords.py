"""
Run search for keywords and settings from config.json.
Edit config.json to change keywords and results_per_keyword, then run:
  python run_keywords.py

Output:
  - output/history/YYYY-MM-DD.json  → full result of each run, one file per day (history).
  - output/activity.json              → unique URLs only, with first_seen datetime (activity).
  - output/telegram_bot.json          → same as activity + telegram_sent (true/false); bot sends only false, then sets true.
  - Telegram group                    → only URLs with telegram_sent false (if TELEGRAM_BOT_TOKEN + TELEGRAM_GROUP_CHAT_ID set).
"""

import json
import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

from google_search_tool import search_google

load_dotenv()

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
HISTORY_DIR = os.path.join(OUTPUT_DIR, "history")


def _load_config() -> tuple[list[str], int]:
    """Load keywords and results_per_keyword from config.json."""
    if not os.path.exists(CONFIG_FILE):
        raise SystemExit(f"Config not found: {CONFIG_FILE}. Create it with 'keywords' and 'results_per_keyword'.")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    keywords = data.get("keywords", [])
    if not isinstance(keywords, list):
        keywords = []
    results_per_keyword = data.get("results_per_keyword", 10)
    if not isinstance(results_per_keyword, (int, float)) or results_per_keyword < 1:
        results_per_keyword = 10
    return keywords, int(results_per_keyword)
ACTIVITY_FILE = os.path.join(OUTPUT_DIR, "activity.json")
TELEGRAM_BOT_FILE = os.path.join(OUTPUT_DIR, "telegram_bot.json")


def _send_one_telegram_message(text: str, bot_token: str, chat_id: str) -> tuple[bool, str]:
    """Send one message to Telegram. Returns (success, error_message)."""
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(api_url, json={"chat_id": chat_id, "text": text}, timeout=10)
        if r.status_code == 200:
            return True, ""
        try:
            err = r.json().get("description", r.text[:200])
        except Exception:
            err = r.text[:200] if r.text else str(r.status_code)
        return False, err
    except Exception as e:
        return False, str(e)


def _sync_telegram_bot_and_send(new_activity_entries: list[dict]) -> None:
    """
    Keep telegram_bot.json in sync with activity (same fields + telegram_sent).
    If telegram_bot is empty but activity has data, backfill from activity (telegram_sent: true).
    Add new entries with telegram_sent: false; send only those with false, then set true.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID")
    _ensure_dirs()

    bot_list: list[dict] = []
    if os.path.exists(TELEGRAM_BOT_FILE):
        try:
            with open(TELEGRAM_BOT_FILE, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                bot_list = json.loads(raw) if raw else []
            if not isinstance(bot_list, list):
                bot_list = []
        except (json.JSONDecodeError, TypeError):
            bot_list = []
    seen_urls = {e["url"] for e in bot_list}

    # Backfill: if telegram_bot is empty but activity has data, copy activity with telegram_sent: true (don't resend old URLs)
    if not bot_list and os.path.exists(ACTIVITY_FILE):
        with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
            activity_list = json.load(f)
        for e in activity_list:
            url = e.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                bot_list.append({
                    "url": url,
                    "first_seen": e.get("first_seen", ""),
                    "keyword": e.get("keyword", ""),
                    "title": e.get("title", ""),
                    "telegram_sent": True,
                })

    for e in new_activity_entries:
        url = e.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            bot_list.append({
                "url": url,
                "first_seen": e.get("first_seen", ""),
                "keyword": e.get("keyword", ""),
                "title": e.get("title", ""),
                "telegram_sent": False,
            })

    pending = [e for e in bot_list if e.get("telegram_sent") is False]
    if not pending:
        with open(TELEGRAM_BOT_FILE, "w", encoding="utf-8") as f:
            json.dump(bot_list, f, ensure_ascii=False, indent=2)
        print("Telegram: nothing to send — no new URLs this run (all results were already in activity). Only new URLs are sent. To send all once: python send_telegram_pending.py --resend-all")
        return

    if not token or not chat_id:
        with open(TELEGRAM_BOT_FILE, "w", encoding="utf-8") as f:
            json.dump(bot_list, f, ensure_ascii=False, indent=2)
        print("Telegram: TELEGRAM_BOT_TOKEN or TELEGRAM_GROUP_CHAT_ID not set in .env")
        return

    # Send one URL per message (easy to view, no long block)
    total_pending = len(pending)
    print(f"Telegram: sending {total_pending} URLs (one per message)...")
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
        if i % 10 == 0 or i == total_pending:
            print(f"  {i}/{total_pending} sent (ok: {sent_count})")
        time.sleep(0.2)
    with open(TELEGRAM_BOT_FILE, "w", encoding="utf-8") as f:
        json.dump(bot_list, f, ensure_ascii=False, indent=2)
    if sent_count:
        print(f"Telegram: sent {sent_count} URLs (one per message).")
    else:
        print(f"Telegram: send failed. Error: {first_error}", flush=True)


def _ensure_dirs() -> None:
    os.makedirs(HISTORY_DIR, exist_ok=True)


def _save_history(run_at: str, results_by_keyword: dict) -> None:
    """Append this run to today's history file (one file per day)."""
    _ensure_dirs()
    date_str = run_at[:10]
    path = os.path.join(HISTORY_DIR, f"{date_str}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"date": date_str, "runs": []}
    data["runs"].append({
        "run_at": run_at,
        "results": results_by_keyword,
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _save_activity(run_at: str, results_by_keyword: dict) -> list[dict]:
    """Append only new (unique) URLs to activity with first_seen datetime. Returns newly added entries."""
    _ensure_dirs()
    existing: list[dict] = []
    if os.path.exists(ACTIVITY_FILE):
        with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
    seen_urls = {e["url"] for e in existing}
    new_entries: list[dict] = []
    for keyword, items in results_by_keyword.items():
        for r in items:
            link = r.get("link")
            if not link or link in seen_urls:
                continue
            seen_urls.add(link)
            entry = {
                "url": link,
                "first_seen": run_at,
                "keyword": keyword,
                "title": r.get("title", ""),
            }
            existing.append(entry)
            new_entries.append(entry)
    with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    return new_entries


def main() -> None:
    keywords, results_per_keyword = _load_config()
    run_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    results_by_keyword: dict = {}

    for keyword in keywords:
        print(f"\n{'='*60}")
        print(f"Keyword: {keyword}")
        print("=" * 60)
        try:
            results = search_google(keyword=keyword, num_results=results_per_keyword)
            results_by_keyword[keyword] = results
            for i, r in enumerate(results, 1):
                print(f"{i}. {r['title']}")
                print(f"   {r['link']}")
                if r["snippet"]:
                    print(f"   {r['snippet'][:120]}...")
                print()
        except (ValueError, RuntimeError) as e:
            print(f"Error for '{keyword}': {e}")
            results_by_keyword[keyword] = []

    _ensure_dirs()
    _save_history(run_at, results_by_keyword)
    new_entries = _save_activity(run_at, results_by_keyword)
    print(f"\nNew URLs this run: {len(new_entries)} (only these are sent to Telegram)")
    _sync_telegram_bot_and_send(new_entries)
    print(f"Saved: history → {os.path.join(HISTORY_DIR, run_at[:10] + '.json')}, activity → {ACTIVITY_FILE}, telegram_bot → {TELEGRAM_BOT_FILE}")


if __name__ == "__main__":
    main()
