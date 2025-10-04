# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated pipeline that receives Patreon stories via email, intelligently chunks them using AI, generates EPUBs, and delivers ONE chunk per day to Kindle at 8am UTC (drip-feed system).

## Architecture

**Core Pipeline:**
1. Email webhook receives parsed emails → `EmailParser` extracts story content (inline text or password-protected URLs)
2. `LLMChunker` (or `SimpleChunker`) splits text into ~5k word chunks at natural narrative breaks (scene changes, perspective shifts, completed emotional arcs)
3. Chunks are saved to database with full text
4. `send_daily_chunk` scheduled function (8am UTC) sends ONE chunk per day
5. `EPUBGenerator` creates EPUB on-demand when sending
6. `KindleSender` delivers via SMTP to Kindle email
7. `Database` (SQLite on Modal Volume) tracks status: pending → processing → chunked → sent/failed

**Key Design Patterns:**
- Strategy pattern for chunking: `LLMChunker` uses Claude to identify natural break points, `SimpleChunker` as fallback
- Strategy pattern for email parsing (supports multiple content sources)
- Status tracking with retry logic for failed deliveries
- Drip-feed delivery system: one chunk per day to control reading pace

**Modal Infrastructure:**
- Persistent volume for SQLite DB and generated EPUBs
- Webhook endpoint for email ingestion
- Scheduled cron job (8am UTC daily) sends next unsent chunk
- Scheduled cron job (every 6 hours) retries failed stories (max 3 attempts)

## Development Commands

**Setup:**
```bash
# Install dependencies with Poetry
poetry install

# Authenticate with Modal
poetry run modal token new

# Copy .env.example to .env and configure
cp .env.example .env
# Edit .env with your credentials
```

**Deploy:**
```bash
poetry run modal deploy main.py
```

**Test locally:**
```bash
# Process a test story (chunks but doesn't send)
poetry run modal run main.py

# Manually send next unsent chunk
poetry run modal run main.py::send_daily_chunk

# Inspect database state
poetry run modal run inspect_db.py

# Test chunker on example files
poetry run python test_chunker.py examples/inputs/pale-lights-example-1.txt 5000

# Update Modal secrets from .env
./update-secrets.sh
```

**Create/Update Modal secrets:**
```bash
# Initial setup
poetry run modal secret create story-prep-secrets \
  KINDLE_EMAIL=your-kindle@kindle.com \
  SMTP_HOST=smtp.gmail.com \
  SMTP_PORT=587 \
  SMTP_USER=your-email@gmail.com \
  SMTP_PASSWORD=your-app-password \
  TEST_MODE=true \
  USE_LLM_CHUNKER=true \
  TARGET_WORDS=5000 \
  ANTHROPIC_API_KEY=your-anthropic-key

# Or use the convenience script (recommended)
./update-secrets.sh
```

## Testing & Verification

**Full workflow test:**
```bash
# 1. Process a test story
modal run main.py
# ✅ Should output: "Successfully processed and chunked: Test Story. Chunks will be sent daily."

# 2. Inspect database to see pending chunks
modal run inspect_db.py
# ✅ Should show story with "⏳ PENDING" chunks

# 3. Manually trigger daily send (simulates scheduled function)
modal run main.py::send_daily_chunk
# ✅ Should send chunk 1/N (in TEST_MODE, logs email details instead of sending)

# 4. Run again to send next chunk
modal run main.py::send_daily_chunk
# ✅ Should send chunk 2/N

# 5. Verify all sent
modal run inspect_db.py
# ✅ Should show all chunks as "✅ SENT" and output "No pending chunks - all caught up!"
```

**Monitoring production:**
- View scheduled function runs: https://modal.com/apps
- Check function logs in Modal dashboard
- Daily sends happen automatically at 8am UTC
- Failed deliveries retry every 6 hours (max 3 attempts)

## Email Ingestion Setup

Use Mailgun/SendGrid/Cloudflare Email Workers to forward Patreon emails to the webhook URL.

Example webhook URL after deployment:
```
https://your-username--nighttime-story-prep-webhook.modal.run
```

Configure your email service to POST parsed emails to this endpoint.
