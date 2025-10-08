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
├── main.py                      # Modal app (dev + production)
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
- Single codebase with environment detection (dev vs production via `MODAL_ENVIRONMENT`)
- Persistent volume for SQLite DB and generated EPUBs
- Webhook endpoint for email ingestion
- URL submission endpoint for manual story ingestion
- Scheduled cron jobs (production only): daily chunk sending (8am UTC), retry failed stories (every 6 hours)
- Dev mode disables scheduled functions for safe testing

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
# Deploy to production (sets MODAL_ENVIRONMENT=prod automatically)
poetry run modal deploy main.py
```

**Local development:**
```bash
# Start local Modal server (defaults to dev mode)
# - Uses story-data-dev volume and stories-dev.db
# - Disables scheduled functions
# - Hot-reloads on file changes
modal serve main.py

# Process a test story (chunks but doesn't send)
modal run main.py

# Manually send next unsent chunk
modal run main.py::send_daily_chunk

# Inspect dev database state
modal run scripts/inspect_db_dev.py

# Manage dev database (list, view, delete stories)
modal run scripts/manage_dev_db.py::list_stories
modal run scripts/manage_dev_db.py::view_story --story-id 1
modal run scripts/manage_dev_db.py::delete_story --story-id 1
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
# 1. Start dev server
modal serve main.py
# ✅ Should output: "🚀 Running in DEVELOPMENT mode"

# 2. Submit test story (in another terminal)
curl -X POST 'https://your-dev-submit-url.modal.run' \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com/story", "title": "Test", "author": "Author"}'
# ✅ Should return: {"status": "accepted", ...}

# 3. List stories to verify processing
modal run scripts/manage_dev_db.py::list_stories
# ✅ Should show story with status "chunked" and "0/N sent"

# 4. Manually trigger daily send
modal run main.py::send_daily_chunk
# ✅ Should send chunk 1/N (in TEST_MODE, logs email details instead of sending)

# 5. Verify chunk was sent
modal run scripts/manage_dev_db.py::view_story --story-id 1
# ✅ Should show chunk 1 as "✅ SENT"

# 6. Clean up
modal run scripts/manage_dev_db.py::delete_story --story-id 1
```

**For detailed step-by-step workflow, see:** `docs/TESTING_WORKFLOW.md`

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
- When editing `main.py`, imports must use `src.` prefix
- When editing test files, imports must use `src.` prefix
- Modal `.add_local_file()` calls must include the `src/` path (e.g., `.add_local_file("src/database.py", "/root/src/database.py")`)

**Modal Development:**
- Use `modal serve main.py` for local development (defaults to dev mode with hot-reload)
- Use `modal deploy main.py` for production deployment (automatically sets prod mode)
- Dev and production use separate volumes and databases (`story-data-dev` vs `story-data`)
- Environment is controlled by `MODAL_ENVIRONMENT` variable (defaults to `dev`)
- Scheduled functions only run in production mode
- Always test locally before deploying to production

**Testing:**
- Run tests from project root: `poetry run python tests/test_*.py`
- Use `./scripts/quickstart.sh` for quick verification
- Local tests use `./local_data/` and `./test_stories.db`
- Modal tests use volume-mounted `/data/` directory
