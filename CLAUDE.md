# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated pipeline that receives Patreon stories via email, intelligently chunks them using AI, generates EPUBs, and delivers ONE chunk per day to Kindle at 8am UTC (drip-feed system).

## Architecture

**Core Pipeline:**
1. Email webhook receives parsed emails → `extract_content()` extracts story content (with optional agent-based analysis)
   - Agent extraction (optional): Claude Agent SDK analyzes email to determine best extraction strategy
   - Fallback strategies: `InlineTextStrategy`, `PasswordProtectedURLStrategy`
2. Intelligent chunking splits text into ~5k word chunks at natural narrative breaks:
   - `AgentChunker` (optional): Uses Claude Agent SDK for holistic story analysis and context-aware break points
   - `LLMChunker`: Uses Claude API to identify natural breaks (scene changes, perspective shifts, completed emotional arcs)
   - `SimpleChunker`: Word-count based fallback
   - All chunkers preserve your recap system: adds "Previously:" sections between chunks
3. Chunks are saved to database with full text and extraction metadata
4. `send_daily_chunk` scheduled function (8am UTC) sends ONE chunk per day
5. `EPUBGenerator` creates EPUB on-demand when sending
6. `KindleSender` delivers via SMTP to Kindle email
7. `Database` (SQLite on Modal Volume) tracks status: pending → processing → chunked → sent/failed

**Key Design Patterns:**
- Agent-first architecture: Claude Agent SDK for intelligent extraction and chunking (with automatic fallbacks)
- Strategy pattern for chunking: `AgentChunker` → `LLMChunker` → `SimpleChunker`
- Strategy pattern for email parsing: supports inline text, URLs, password-protected content
- Metadata tracking: stores extraction method and confidence for debugging
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

# Compare AgentChunker vs LLMChunker
poetry run python test_agent_chunker.py examples/inputs/pale-lights-example-1.txt 5000

# Test agent-based content extraction
poetry run python test_content_agent.py examples/inputs/wandering-inn-example-1.txt

# Test outputs are saved to test_outputs/ with timestamps
# See TEST_OUTPUTS_README.md for details on reading results

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
  USE_AGENT_CHUNKER=false \
  USE_LLM_CHUNKER=true \
  USE_AGENT_EXTRACTION=false \
  TARGET_WORDS=5000 \
  ANTHROPIC_API_KEY=your-anthropic-key

# Or use the convenience script (recommended)
./update-secrets.sh
```

**Configuration Options:**
- `USE_AGENT_CHUNKER=true`: Enable Claude Agent SDK for most context-aware chunking
- `USE_LLM_CHUNKER=true`: Enable Claude API chunking (fallback if agent disabled)
- `USE_AGENT_EXTRACTION=true`: Enable Claude Agent SDK for intelligent email parsing
- `TARGET_WORDS=5000`: Target words per chunk (flexible based on natural breaks)
- Set all agent flags to `false` to use traditional strategies (no API costs)

## Testing & Verification

**Full workflow test:**
```bash
# 1. Process a test story
poetry run modal run main.py
# ✅ Should output: "Successfully processed and chunked: Test Story. Chunks will be sent daily."

# 2. Inspect database to see pending chunks
poetry run modal run inspect_db.py
# ✅ Should show story with "⏳ PENDING" chunks

# 3. Manually trigger daily send (simulates scheduled function)
poetry run modal run main.py::send_daily_chunk
# ✅ Should send chunk 1/N (in TEST_MODE, logs email details instead of sending)

# 4. Run again to send next chunk
poetry run modal run main.py::send_daily_chunk
# ✅ Should send chunk 2/N

# 5. Verify all sent
poetry run modal run inspect_db.py
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
