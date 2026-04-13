# Morning Digest Bot

Minimal token-efficient pipeline for a daily Telegram digest:

1. Fetch finance/economy news, AI news, quotes, and quote-of-the-day without using an LLM.
2. Pass only a compact structured payload into a short LLM polishing/ranking step.
3. Send the final message to Telegram.
4. Run a separate weekly OpenClaw release check with stateful deduplication.

The project uses Python standard library only.

## Features

- Daily digest for the last 24 hours:
  - 5 finance/economy stories
  - 3 AI stories
  - BTC / ETH / SOL / S&P 500 quotes with 24h change
  - quote of the day
- Weekly OpenClaw release watcher based on GitHub releases
- Telegram delivery with local fallback logging on send failure
- Dry-run mode for both jobs
- Local state to avoid duplicate notifications

## Layout

- `src/digest_bot/main.py` - entrypoint and CLI
- `src/digest_bot/fetchers.py` - RSS/API collectors
- `src/digest_bot/llm.py` - optional LLM formatting layer
- `src/digest_bot/telegram.py` - Telegram sender
- `src/digest_bot/storage.py` - state and fallback logs
- `data/quotes.txt` - local quote pool
- `scripts/` - cron-friendly wrappers
- `tests/` - lightweight regression tests

## Setup

1. Copy `.env.example` to `.env` or export the same variables in your shell.
2. Set at minimum:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. If you want the LLM layer enabled, also set:
   - `OPENAI_API_KEY`
   - optionally `OPENAI_MODEL`
4. Run a dry-run:

```bash
cp .env.example .env
PYTHONPATH=src python3 -m digest_bot.main daily --dry-run
PYTHONPATH=src python3 -m digest_bot.main weekly-openclaw --dry-run
```

Offline fixture runs:

```bash
PYTHONPATH=src python3 -m digest_bot.main daily --dry-run --fixture fixtures/daily_payload.json
PYTHONPATH=src python3 -m digest_bot.main weekly-openclaw --dry-run --fixture fixtures/openclaw_release.json
```

## Environment variables

See `.env.example` for the full list. Important ones:

- `DIGEST_TIMEZONE` - default `Europe/Moscow`
- `OPENAI_ENABLED` - `true` or `false`
- `OPENAI_MODEL` - default `gpt-4.1-mini`
- `TELEGRAM_ENABLED` - `true` or `false`
- `OPENCLAW_REPO` - default `openclaw/openclaw`
- `STATE_DIR` - where state and fallback logs are stored

## Cron examples

Daily at 09:00 Moscow time:

```cron
0 9 * * * cd "/Users/mikhail.frolov/Documents/Вайбс/Утренний дайджест" && ./scripts/run_daily.sh
```

Weekly on Sunday at 10:00 Moscow time:

```cron
0 10 * * 0 cd "/Users/mikhail.frolov/Documents/Вайбс/Утренний дайджест" && ./scripts/run_openclaw_weekly.sh
```

Set the process timezone explicitly in the wrapper if your cron host does not already use Moscow time.

## Notes

- The app auto-loads a local `.env` file from the project root before reading environment variables.
- If the LLM step is disabled or unavailable, the bot still produces a compact deterministic message.
- If Telegram delivery fails, the message is appended to a local log file and the LLM step is not re-run.
- Weekly OpenClaw checks send nothing if there is no new release.
