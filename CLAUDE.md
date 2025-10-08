# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated pipeline that receives Patreon stories via email, intelligently chunks them using AI, generates EPUBs, and delivers ONE chunk per day to Kindle at 8am UTC (drip-feed system).

## Project Structure

```
nighttime-story-prep/
├── src/                          # Core application code
│   ├── chunker.py               # Chunking strategies (Agent, LLM, Simple)
│   ├── content_extraction_agent.py  # AI-powered content extraction
│   ├── database.py              # SQLite database management
│   ├── email_parser.py          # Email parsing strategies
│   ├── epub_generator.py        # EPUB generation
│   ├── file_storage.py          # File I/O utilities
│   └── kindle_sender.py         # SMTP email sending
├── tests/                       # All test files
│   ├── test_*.py               # Unit and integration tests
│   └── test_story.sh           # Quick CLI test script
├── scripts/                     # Utility scripts
│   ├── inspect_db.py           # Database inspection tool
│   ├── quickstart.sh           # One-command setup
│   └── update-secrets.sh       # Update Modal secrets from .env
├── docs/                        # Documentation
│   ├── README.md               # Complete development guide
│   └── CONTENT_CLEANING.md     # Content extraction details
├── examples/inputs/             # Test story files
├── main.py                      # Production Modal app
├── main_local.py                # Local dev Modal app
└── pyproject.toml               # Poetry dependencies
```

## Architecture

**Core Pipeline:**
1. Email webhook receives parsed emails → `extract_content()` extracts story content
   - Agent extraction (optional): Claude Agent SDK analyzes email to determine best extraction strategy
   - Fallback strategies: `InlineTextStrategy`, `PasswordProtectedURLStrategy`
2. Intelligent chunking splits text into ~5k word chunks at natural narrative breaks:
   - `AgentChunker` (optional): Uses Claude Agent SDK for holistic story analysis and context-aware break points
   - `LLMChunker`: Uses Claude API to identify natural breaks (scene changes, perspective shifts, completed emotional arcs)
   - `SimpleChunker`: Word-count based fallback
   - All chunkers preserve recap system: adds "Previously:" sections between chunks
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

**Local development:**
```bash
# Start local Modal server with live endpoints (hot-reloads on file changes)
modal serve main_local.py

# Process a test story (chunks but doesn't send)
modal run main_local.py

# Manually send next unsent chunk
modal run main_local.py::send_next_chunk

# Inspect database state
modal run scripts/inspect_db.py
```

**Local testing (without Modal):**
```bash
# Quick test
./scripts/quickstart.sh

# Test chunker on example files
poetry run python tests/test_chunker.py examples/inputs/pale-lights-example-1.txt 5000

# Compare AgentChunker vs LLMChunker
poetry run python tests/test_agent_chunker.py examples/inputs/pale-lights-example-1.txt 5000

# Test agent-based content extraction
poetry run python tests/test_content_agent.py examples/inputs/wandering-inn-example-1.txt

# Test full pipeline
poetry run python tests/test_full_pipeline.py

# Test all examples
poetry run python tests/test_all_examples.py

# Update Modal secrets from .env
./scripts/update-secrets.sh
```

**Create/Update Modal secrets:**
```bash
# Use the convenience script (recommended)
./scripts/update-secrets.sh

# Or manually
poetry run modal secret create story-prep-secrets \
  KINDLE_EMAIL=your-kindle@kindle.com \
  SMTP_HOST=smtp.gmail.com \
  SMTP_PORT=587 \
  SMTP_USER=your-email@gmail.com \
  SMTP_PASSWORD=your-app-password \
  TEST_MODE=true \
  USE_AGENT_CHUNKER=true \
  USE_LLM_CHUNKER=true \
  USE_AGENT_EXTRACTION=true \
  TARGET_WORDS=5000 \
  ANTHROPIC_API_KEY=your-anthropic-key
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
modal run main_local.py
# ✅ Should output: "Successfully processed and chunked: Test Story. Chunks will be sent daily."

# 2. Inspect database to see pending chunks
modal run scripts/inspect_db.py
# ✅ Should show story with "⏳ PENDING" chunks

# 3. Manually trigger daily send (simulates scheduled function)
modal run main_local.py::send_next_chunk
# ✅ Should send chunk 1/N (in TEST_MODE, logs email details instead of sending)

# 4. Run again to send next chunk
modal run main_local.py::send_next_chunk
# ✅ Should send chunk 2/N

# 5. Verify all sent
modal run scripts/inspect_db.py
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

## Important Notes for Claude Code

**File Organization:**
- All source modules are in `src/`
- All tests are in `tests/`
- All utility scripts are in `scripts/`
- All documentation is in `docs/` or root-level markdown files

**Import Statements:**
- When editing files in `src/`, internal imports must use `src.` prefix (e.g., `from src.database import Database`)
- When editing `main.py` or `main_local.py`, imports must use `src.` prefix
- When editing test files, imports must use `src.` prefix
- Modal `.add_local_file()` calls must include the `src/` path (e.g., `.add_local_file("src/database.py", "/root/src/database.py")`)

**Modal Development:**
- Use `modal serve main_local.py` for local development with hot-reload
- Use `modal deploy main.py` for production deployment
- Dev and production use separate volumes and databases
- Always test locally before deploying to production

**Testing:**
- Run tests from project root: `poetry run python tests/test_*.py`
- Use `./scripts/quickstart.sh` for quick verification
- Local tests use `./local_data/` and `./test_stories.db`
- Modal tests use volume-mounted `/data/` directory
