# Nighttime Story Prep

Automated pipeline that receives Patreon stories via email, chunks them using AI, generates EPUBs, and delivers ONE chunk per day to Kindle at 8pm UTC.

## Features

- **Email ingestion**: Webhook receives stories from Brevo/email providers
- **AI content extraction**: Strips metadata, keeps only story text (Claude Agent SDK)
- **Intelligent chunking**: ~8k word chunks at natural narrative breaks
- **Daily drip-feed**: Sends one chunk per day to control reading pace
- **EPUB generation**: Creates properly formatted ebooks
- **Robust tracking**: PostgreSQL (Supabase) database with Supabase Storage

## Architecture

- **Modal API**: Python service for AI-powered content extraction and chunking
- **Next.js App**: Web application on Vercel with API routes
- **Supabase**: PostgreSQL database and object storage
- **Brevo**: Email ingestion (webhook) and SMTP delivery
- **Vercel Crons**: Scheduled daily delivery (8pm UTC)

## 🚀 Production Deployment

Ready to deploy to production? Choose your guide:

### Quick Start (30-40 minutes)

**[DEPLOYMENT_QUICKSTART.md](DEPLOYMENT_QUICKSTART.md)** - Fast-track deployment guide

```bash
# Interactive setup (recommended)
./scripts/setup-production-env.sh

# Verify deployment
./scripts/verify-deployment.sh
```

### Detailed Guide

**[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Comprehensive step-by-step guide with explanations

### Deployment Checklist

**[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Printable checklist to track progress

### Component-Specific Guides

- **Modal API**: [modal-api/DEPLOYMENT.md](modal-api/DEPLOYMENT.md)
- **Next.js App**: [nextjs-app/README.md](nextjs-app/README.md)
- **Testing**: [scripts/TEST_README.md](scripts/TEST_README.md)

---

## 🔧 Development Setup

For local development and testing:

### Prerequisites

```bash
# Check versions
node --version          # Need 20.9.0+
supabase --version      # Supabase CLI
modal --version         # Modal CLI
```

### Quick Start (Local Development)

```bash
# 1. Start local Supabase
cd nextjs-app
supabase start
supabase db reset

# 2. Configure environment
cp env.example .env.local
# Edit .env.local with Supabase credentials from 'supabase start' output

# 3. Start Next.js dev server
npm install
npm run dev

# 4. In another terminal, run tests
cd ..
./scripts/test/test-all.sh
```

See [nextjs-app/README.md](nextjs-app/README.md) for detailed development setup.

## Old Quick Start (Legacy)

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

### View Logs

```bash
# Check function logs
poetry run modal logs nighttime-story-prep-dev.process_story
poetry run modal logs nighttime-story-prep-dev.webhook

# View webhook logs (stored in database)
poetry run modal run scripts/view_webhook_logs.py::list_webhooks_dev
poetry run modal run scripts/view_webhook_logs.py::view_latest
poetry run modal run scripts/view_webhook_logs.py::view_webhook_dev --log-id 1
```

### Inspect Database

```bash
# Download database for inspection
poetry run modal volume get story-data-dev stories-dev.db ./dev.db
sqlite3 ./dev.db

# Query webhook logs
sqlite3 ./dev.db "SELECT id, received_at, processing_status, parsed_emails_count FROM webhook_logs ORDER BY received_at DESC LIMIT 10"

# Query stories with errors
sqlite3 ./dev.db "SELECT id, title, status, error_message FROM stories WHERE status='failed'"
```

### File System

```bash
# List volume contents
poetry run modal volume ls story-data-dev /data/raw
poetry run modal volume ls story-data-dev /data/chunks

# Download raw email
poetry run modal volume get story-data-dev /data/raw/story_000001/original_email.txt ./email.txt

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
