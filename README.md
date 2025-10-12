# Nighttime Story Prep

Automated pipeline that receives Patreon stories via email, chunks them using AI, generates EPUBs, and delivers ONE chunk per day to Kindle at 8am UTC.

## Features

- **Email ingestion**: Webhook receives stories from Mailgun/SendGrid/etc
- **AI content extraction**: Strips metadata, keeps only story text
- **Intelligent chunking**: ~5k word chunks at natural narrative breaks
- **Daily drip-feed**: Sends one chunk per day to control reading pace
- **EPUB generation**: Creates properly formatted ebooks
- **Robust tracking**: SQLite database with retry logic

## Quick Start

```bash
# Install and setup
poetry install
poetry run modal token new
cp .env.example .env
# Edit .env with your credentials

# Deploy to production
poetry run modal deploy main.py
```

## Development

### Local testing (no Modal)

```bash
# Quick test
./scripts/quickstart.sh

# Full pipeline test
poetry run python tests/test_full_pipeline.py
```

### Modal development server

```bash
# Terminal 1: Start dev server (auto-reloads on changes)
poetry run modal serve main.py

# Terminal 2: Submit test story
curl -X POST 'https://your-dev-submit-url.modal.run' \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com/story", "title": "Test", "author": "Author"}'

# Inspect database
poetry run modal run scripts/manage_dev_db.py::list_stories
poetry run modal run scripts/manage_dev_db.py::view_story --story-id 1

# Manually send next chunk
poetry run modal run main.py::send_daily_chunk

# Clean up
poetry run modal run scripts/manage_dev_db.py::delete_story --story-id 1
```

## Configuration

Create `.env` or use Modal secrets:

```bash
# AI Features (requires ANTHROPIC_API_KEY)
USE_AGENT_EXTRACTION=true    # AI-powered content extraction
USE_AGENT_CHUNKER=true       # AI-powered chunking
USE_LLM_CHUNKER=true         # Fallback LLM chunker
TARGET_WORDS=5000            # Target words per chunk

# Email Delivery
KINDLE_EMAIL=you@kindle.com      # Destination Kindle email
FROM_EMAIL=your-email@gmail.com  # From address for emails
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com   # SMTP login (usually same as FROM_EMAIL)
SMTP_PASSWORD=your-app-password  # Gmail App Password

# Testing
TEST_MODE=true               # Simulate sending (don't actually send)

# Update Modal secrets from .env
./scripts/update-secrets.sh
```

## Project Structure

```
src/                          # Core application
├── chunker.py               # Chunking strategies (Agent/LLM/Simple)
├── content_extraction_agent.py  # AI content extraction
├── database.py              # SQLite management
├── email_parser.py          # Email parsing strategies
├── epub_generator.py        # EPUB generation
├── file_storage.py          # File I/O
└── kindle_sender.py         # SMTP email sending

scripts/                     # Utilities
├── manage_dev_db.py         # Database inspection/management
├── quickstart.sh            # One-command setup
└── update-secrets.sh        # Update Modal secrets

tests/                       # Test files
main.py                      # Modal app (dev + prod)
```

## Architecture

**Pipeline Flow:**

1. Email webhook → `extract_content()` extracts story (AI-powered with fallbacks)
2. Intelligent chunking splits at natural narrative breaks (AgentChunker → LLMChunker → SimpleChunker)
3. Chunks saved to SQLite database with metadata
4. `send_daily_chunk` scheduled function (8am UTC) sends ONE chunk
5. `EPUBGenerator` creates EPUB on-demand
6. `KindleSender` delivers via SMTP
7. Status tracking: pending → processing → chunked → sent/failed

**Modal Infrastructure:**

- Single codebase with environment detection (dev vs prod via `MODAL_ENVIRONMENT`)
- Persistent volumes: `story-data-dev` (dev) / `story-data` (prod)
- Scheduled functions (prod only): daily sends (8am UTC), retry failures (every 6 hours)
- Dev mode disables schedules for safe testing

## Common Commands

```bash
# Setup
poetry install
poetry run modal token new
./scripts/update-secrets.sh

# Local testing
./scripts/quickstart.sh
poetry run python tests/test_full_pipeline.py
poetry run python tests/test_all_examples.py

# Modal development
poetry run modal serve main.py                      # Start dev server
poetry run modal run main.py::send_daily_chunk      # Send next chunk
poetry run modal run scripts/manage_dev_db.py::list_stories
poetry run modal run scripts/manage_dev_db.py::view_story --story-id 1
poetry run modal run scripts/manage_dev_db.py::delete_story --story-id 1

# Production
poetry run modal deploy main.py                     # Deploy
poetry run modal run scripts/inspect_db.py          # Check production DB
poetry run modal logs nighttime-story-prep.send_daily_chunk

# Database inspection
poetry run modal volume get story-data-dev stories-dev.db ./local.db
sqlite3 ./local.db "SELECT * FROM stories"
```

## Testing

| Test                          | Purpose                      |
| ----------------------------- | ---------------------------- |
| `tests/test_full_pipeline.py` | Complete end-to-end test     |
| `tests/test_all_examples.py`  | Test all example stories     |
| `tests/test_chunker.py`       | Test chunking algorithms     |
| `tests/test_agent_chunker.py` | Compare Agent vs LLM chunker |
| `tests/test_content_agent.py` | Test AI extraction           |
| `scripts/test_story.sh`       | Quick CLI test               |

## Debugging

```bash
# Check logs
poetry run modal logs nighttime-story-prep-dev.process_story

# Download database for inspection
poetry run modal volume get story-data-dev stories-dev.db ./dev.db
sqlite3 ./dev.db

# List volume contents
poetry run modal volume ls story-data-dev /data/raw
poetry run modal volume ls story-data-dev /data/chunks

# Interactive shell with volume mounted
poetry run modal shell main.py::process_story
```

## Production Setup

### Brevo (Sendinblue) Inbound Email Setup

1. **Deploy your app:**
   ```bash
   modal deploy main.py
   ```

2. **Get your webhook URL:**
   ```
   https://your-username--nighttime-story-prep-webhook.modal.run
   ```

3. **Configure Brevo inbound domain:**
   - Go to Brevo dashboard → Settings → Inbound Parsing
   - Add your domain (e.g., `reply.yourdomain.com`)
   - Point your domain's MX records to Brevo's servers
   - Set webhook URL to your Modal endpoint

4. **Forward Patreon emails:**
   - Create email rule in Patreon to forward to `story@reply.yourdomain.com`
   - Or use Gmail filters to forward to your Brevo inbound address

**Brevo webhook format:** The webhook receives JSON with an `items` array containing parsed emails. Each email has `Subject`, `From`, `RawTextBody`, `RawHtmlBody`, etc.

### Production Schedules

- **8am UTC**: Send next unsent chunk
- **Every 6 hours**: Retry failed stories (max 3 attempts)
