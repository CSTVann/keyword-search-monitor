# Keyword Search Monitor

**Keyword Search Monitor** is an open-source Python tool that runs Google searches for configurable keywords, stores unique results, and optionally delivers new matches to a Telegram group. Use it to monitor mentions, news, or topics without manual searching.

---

## What It Does

1. **Searches** — Runs Google searches for each keyword in `config.json` (via SerpAPI or Google Custom Search API).
2. **Stores** — Saves full daily history and a deduplicated activity list (URLs with first-seen time).
3. **Notifies** — Sends only *new* URLs to a Telegram group so you get alerts without duplicates.

---

## Features

| Feature | Description |
|--------|-------------|
| **Keyword tracking** | Define keywords in `config.json`; results are fetched per keyword. |
| **Deduplication** | Tracks unique URLs in `activity.json`; only new URLs are sent to Telegram. |
| **Telegram delivery** | Optional: new links sent to a group via a bot (one message per URL). |
| **Search backends** | SerpAPI (recommended) or Google Custom Search JSON API. |
| **History** | One JSON file per day under `output/history/` for full run data. |

---

## Prerequisites

- **Python 3.10+**
- **Search API** — Either:
  - [SerpAPI](https://serpapi.com/) key (recommended; works for new users), or
  - Google Custom Search API key + Search Engine ID
- **Telegram** (optional) — Bot token and group chat ID for notifications

---

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/keyword-search-monitor.git
   cd keyword-search-monitor
   ```

2. **Create a virtual environment and install dependencies**

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment**

   Copy the example env file and fill in your keys:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your values (see [Configuration](#configuration) below).

4. **Configure keywords**

   Edit `config.json` to set your keywords and how many results to fetch per keyword (see [Configuration](#configuration)).

---

## Configuration

### `config.json`

| Field | Type | Description |
|-------|------|-------------|
| `keywords` | array of strings | Search terms to monitor (e.g. `["Topic A", "Topic B"]`). |
| `results_per_keyword` | number | Number of results to fetch per keyword (e.g. `10` or `100`). |

**Example:**

```json
{
  "keywords": ["Your Keyword 1", "Your Keyword 2"],
  "results_per_keyword": 10
}
```

### Environment variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `SERPAPI_KEY` | One of SerpAPI or Google CSE | SerpAPI key (recommended). |
| `GOOGLE_SEARCH_API_KEY` | One of SerpAPI or Google CSE | Google Custom Search API key. |
| `GOOGLE_SEARCH_ENGINE_ID` | If using Google CSE | Search Engine ID (cx). |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot token for sending messages. |
| `TELEGRAM_GROUP_CHAT_ID` | Optional | Telegram group chat ID (e.g. negative number). |

- **Search:** If `SERPAPI_KEY` is set, SerpAPI is used. Otherwise, both `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID` must be set for Google Custom Search.
- **Telegram:** If both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_GROUP_CHAT_ID` are set, new URLs are sent to that group after each run.

---

## Usage

### Run keyword search and send new URLs to Telegram

From the project root (with `venv` activated):

```bash
python run_keywords.py
```

This will:

- Load keywords and `results_per_keyword` from `config.json`
- Run a Google search for each keyword
- Append today’s run to `output/history/YYYY-MM-DD.json`
- Update `output/activity.json` with unique URLs (and first-seen time)
- Update `output/telegram_bot.json` and send only **new** URLs to the Telegram group (if credentials are set)

### Send pending Telegram messages only

If you only want to send previously collected URLs that haven’t been sent yet:

```bash
python send_telegram_pending.py
```

To mark all stored URLs as unsent and send everything once:

```bash
python send_telegram_pending.py --resend-all
```

### Optional: Use the search tool from the command line

```bash
python google_search_tool.py "your keyword" -n 10
```

Use `--links-only` to print only URLs.

---

## Output Files

| Path | Description |
|------|-------------|
| `output/history/YYYY-MM-DD.json` | Full results for each run, one file per day. |
| `output/activity.json` | All unique URLs with `first_seen`, `keyword`, and `title`. |
| `output/telegram_bot.json` | Same as activity plus `telegram_sent`; only entries with `telegram_sent: false` are sent. |

After a run, new URLs are merged into `activity.json` and `telegram_bot.json`; only new ones are sent to Telegram, then marked `telegram_sent: true`.

---

## Scheduling (optional)

Run the monitor on a schedule (e.g. cron) so keywords are checked periodically:

```bash
# Every 6 hours
0 */6 * * * cd /path/to/keyword-search-monitor && /path/to/venv/bin/python run_keywords.py
```

Adjust the path to your project and Python executable.

---

## License

MIT License — see [LICENSE](LICENSE).
