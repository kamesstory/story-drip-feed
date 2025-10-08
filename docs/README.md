# Nighttime Story Prep - Complete Development Guide

Automated pipeline that receives Patreon stories via email, intelligently chunks them using AI, generates EPUBs, and delivers ONE chunk per day to Kindle at 8am UTC.

## Table of Contents

- [Quick Start](#quick-start)
- [Complete Testing Workflow](TESTING_WORKFLOW.md) ⭐ **Step-by-step guide**
- [Modal CLI Tools](#modal-cli-tools)
- [Local Development with Modal](#local-development-with-modal)
- [Local Testing Without Modal](#local-testing-without-modal)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Common Commands](#common-commands)
- [Testing](#testing)
- [Debugging](#debugging)

---

## Quick Start

### One-Command Setup

```bash
# Run this from project root
./scripts/quickstart.sh
```

This will:
1. Install dependencies with Poetry
2. Authenticate with Modal
3. Copy `.env.example` to `.env`
4. Run a complete pipeline test

### Manual Setup

```bash
# Install dependencies
poetry install

# Authenticate with Modal
poetry run modal token new

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

---

## Modal CLI Tools

Modal provides powerful CLI tools for inspecting and managing your development environment. **Use these instead of web endpoints for debugging!**

### Database Management

```bash
# List all stories in dev database
modal run scripts/manage_dev_db.py::list_stories

# View specific story with chunks
modal run scripts/manage_dev_db.py::view_story --story-id 1

# View chunk text content
modal run scripts/manage_dev_db.py::view_chunk --chunk-id 1

# Delete a story
modal run scripts/manage_dev_db.py::delete_story --story-id 1

# Clear all dev data
modal run scripts/manage_dev_db.py::clear_all

# Show database stats
modal run scripts/manage_dev_db.py::stats

# Quick inspection
modal run scripts/inspect_db_dev.py
```

### Volume/File Operations

```bash
# List volume contents
modal volume ls story-data-dev
modal volume ls story-data-dev /data/raw
modal volume ls story-data-dev /data/chunks

# Download files
modal volume get story-data-dev stories-dev.db ./local-dev.db
modal volume get story-data-dev /data/chunks/story_000001/chunk_001.txt ./chunk.txt

# Upload files (if needed)
modal volume put story-data-dev ./local-file.txt /data/remote-file.txt

# Delete files
modal volume rm story-data-dev /data/stories-dev.db
modal volume rm story-data-dev /data/raw/story_000001 --recursive

# Delete entire volume (nuclear option)
modal volume delete story-data-dev
modal volume create story-data-dev
```

### Interactive Shell

Start an interactive shell with your function's environment (image, volumes, secrets):

```bash
# Shell with process_story environment
modal shell main_local.py::process_story

# Inside shell - full access to volume
> ls /data
> sqlite3 /data/stories-dev.db
> cat /data/raw/story_000001/content.txt
> python
>>> from src.database import Database
>>> db = Database("/data/stories-dev.db")
>>> db.get_all_stories()
```

### Query Database Locally

```bash
# Download and query with SQLite
modal volume get story-data-dev stories-dev.db ./dev.db

sqlite3 ./dev.db <<SQL
SELECT id, title, status FROM stories;
SELECT chunk_number, word_count FROM story_chunks WHERE story_id = 1;
SQL
```

---

## Local Development with Modal

Use `main.py` with dev environment for local development with live endpoints that auto-reload on code changes.

### Start Dev Server

```bash
# Defaults to dev mode (MODAL_ENVIRONMENT=dev)
modal serve main.py
```

This starts a local development server with:
- ✅ Separate dev database (`story-data-dev` volume)
- ✅ Live webhook endpoints
- ✅ URL submission endpoint
- ✅ Hot-reload on file changes
- ✅ Won't affect production data
- ✅ Scheduled functions disabled in dev mode

**Output:**
```
🚀 Running in DEVELOPMENT mode
   App: nighttime-story-prep-dev
   Volume: story-data-dev
   Database: /data/stories-dev.db
✓ Created web function submit_url => https://you--nighttime-story-prep-dev-submit-url-dev.modal.run
✓ Created web function webhook => https://you--nighttime-story-prep-dev-webhook-dev.modal.run
```

### Using the Dev Server

#### Submit Story via Email Webhook

```bash
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "message-id": "test-123",
    "subject": "Test Story - Chapter 1",
    "from": "Author <author@patreon.com>",
    "text": "Story content here..."
  }'
```

#### Submit Story via URL

```bash
curl -X POST $SUBMIT_URL \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/my-story",
    "password": "secret123",
    "title": "My Story - Chapter 5",
    "author": "Author Name"
  }'
```

#### Inspect Database & Stories

Use Modal CLI tools to inspect your dev database:

```bash
# List all stories
modal run scripts/manage_dev_db.py::list_stories

# View specific story with all chunks
modal run scripts/manage_dev_db.py::view_story --story-id 1

# View full chunk text
modal run scripts/manage_dev_db.py::view_chunk --chunk-id 1

# Quick inspection
modal run scripts/inspect_db_dev.py
```

#### Download & Browse Files

```bash
# Download database locally
modal volume get story-data-dev stories-dev.db ./dev.db
sqlite3 ./dev.db "SELECT * FROM stories"

# List files in volume
modal volume ls story-data-dev /data/raw
modal volume ls story-data-dev /data/chunks

# Download specific files
modal volume get story-data-dev /data/raw/story_000001/content.txt ./content.txt
modal volume get story-data-dev /data/chunks/story_000001/chunk_001.txt ./chunk.txt
```

#### Interactive Shell

Start a shell with the volume mounted:

```bash
# Shell with same environment as process_story function
modal shell main.py::process_story

# Inside shell, explore the volume
> ls /data
> sqlite3 /data/stories-dev.db
> cat /data/raw/story_000001/content.txt
> python  # can import and use your modules
```

#### Send Next Chunk Manually

```bash
modal run main.py::send_daily_chunk
```

#### Clean Up Test Data

```bash
# Delete specific story
modal run scripts/manage_dev_db.py::delete_story --story-id 1

# Clear all dev data (nuclear option)
modal run scripts/manage_dev_db.py::clear_all

# Or delete entire volume and recreate
modal volume delete story-data-dev
modal volume create story-data-dev
```

### Typical Dev Workflow

**For detailed step-by-step instructions, see [TESTING_WORKFLOW.md](TESTING_WORKFLOW.md)**

Quick overview:

```bash
# Terminal 1: Start dev server (defaults to dev mode)
modal serve main.py

# Terminal 2: Submit test story
curl -X POST https://your-dev/submit_url -d '{"url": "...", "password": "..."}'

# Watch Terminal 1 for processing logs

# Check what was created
modal run scripts/manage_dev_db.py::list_stories

# View chunk content
modal run scripts/manage_dev_db.py::view_chunk --chunk-id 1

# Test sending
modal run main.py::send_daily_chunk

# Clean up
modal run scripts/manage_dev_db.py::delete_story --story-id 1

# Iterate: Edit code → Auto-reload → Test again
```

### View Dev Database

```bash
# List volume contents
modal volume ls story-data-dev /data/raw
modal volume ls story-data-dev /data/chunks

# Download database
modal volume get story-data-dev stories-dev.db ./local-dev.db
sqlite3 ./local-dev.db
```

---

## Local Testing Without Modal

Test the entire pipeline locally without deploying to Modal.

### Test Individual Components

#### Test Chunking

```bash
# Test with a specific story
./scripts/test_story.sh examples/inputs/pale-lights-example-1.txt

# Test all examples
poetry run python tests/test_all_examples.py
```

#### Test Content Extraction

```bash
poetry run python tests/test_extraction_cleaning.py
```

This verifies:
- ✅ Chapter numbers removed
- ✅ Dates removed
- ✅ Patreon links removed
- ✅ Story content preserved

#### Test Multi-Chunk with Recaps

```bash
poetry run python tests/test_multi_chunk.py
```

### Test Full Pipeline

```bash
poetry run python tests/test_full_pipeline.py
```

This runs the COMPLETE workflow:
1. Email ingestion
2. Content extraction
3. File storage
4. Chunking
5. Database creation
6. EPUB generation
7. Kindle send (simulation)

**Output:**
```
✅ Story extracted from email
✅ Content cleaned (metadata removed)
✅ Story chunked into 2 part(s)
✅ EPUB generated (45,123 bytes)
✅ Chunk marked for Kindle delivery
✅ Database tracking working
```

### Inspect Generated Files

```bash
# View file structure
tree local_data/

# View database
sqlite3 test_stories.db "SELECT * FROM stories;"
sqlite3 test_stories.db "SELECT * FROM story_chunks;"

# Read a chunk
cat local_data/chunks/story_000001/chunk_001.txt

# View metadata
cat local_data/raw/story_000001/metadata.yaml
```

### Test with Your Own Story

```bash
# Add your story to examples
cp ~/Downloads/my-story.txt examples/inputs/

# Test it
./scripts/test_story.sh examples/inputs/my-story.txt
```

### Test Email Sending

**Simulation (no actual sending):**

Set `TEST_MODE=true` in `.env`, then:

```bash
poetry run python tests/test_full_pipeline.py
```

**Actual sending:**

1. Set up Gmail App Password
2. Update `.env`:
   ```bash
   TEST_MODE=false
   KINDLE_EMAIL=your-name@kindle.com
   SMTP_HOST=smtp.gmail.com
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   ```
3. Run test:
   ```bash
   poetry run python tests/test_full_pipeline.py
   ```

---

## Production Deployment

### Deploy to Production

```bash
modal deploy main.py
```

This deploys the production version with:
- Production database (`/data/stories.db` on `story-data` volume)
- Scheduled cron job (8am UTC daily) sends next unsent chunk
- Scheduled cron job (every 6 hours) retries failed stories (max 3 attempts)
- Webhook endpoint for email ingestion

### Production Webhook URL

After deployment, get your webhook URL:
```
https://your-username--nighttime-story-prep-webhook.modal.run
```

Configure your email service (Mailgun/SendGrid/Cloudflare) to POST parsed emails to this endpoint.

### Environment Variables

Control dev vs production mode with `MODAL_ENVIRONMENT`:

```bash
# Development mode (default)
modal serve main.py  # Uses dev database and volume

# Production mode
MODAL_ENVIRONMENT=prod modal deploy main.py  # Uses production database
```

### Check Production Status

```bash
modal run scripts/inspect_db.py
```

### Manual Operations

```bash
# Send next chunk immediately (instead of waiting for 8am UTC)
modal run main.py::send_daily_chunk

# View logs
modal logs nighttime-story-prep.send_daily_chunk
modal logs nighttime-story-prep.process_story
```

---

## Configuration

### Environment Variables

Create `.env` or use Modal secrets:

```bash
# AI Features
USE_AGENT_EXTRACTION=true       # AI-powered metadata cleaning
USE_AGENT_CHUNKER=true          # AI-powered smart chunking
USE_LLM_CHUNKER=true            # Fallback LLM chunker
TARGET_WORDS=5000               # Words per chunk (flexible)
ANTHROPIC_API_KEY=sk-...        # Required for AI features

# Email Configuration
KINDLE_EMAIL=you@kindle.com     # Your Kindle email
SMTP_HOST=smtp.gmail.com        # Email server
SMTP_PORT=587                   # SMTP port
SMTP_USER=you@gmail.com         # Email username
SMTP_PASSWORD=app-pass          # Email app password

# Testing
TEST_MODE=true                  # Simulate sending (don't actually send)
```

### Update Modal Secrets

```bash
# Use convenience script
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

---

## Common Commands

### Setup
```bash
poetry install                  # Install dependencies
poetry run modal token new      # Authenticate with Modal
cp .env.example .env            # Copy environment file
```

### Local Modal Development
```bash
modal serve main.py                          # Start dev server
modal run main.py                            # Test with example story
modal run main.py::send_daily_chunk          # Send next chunk
modal logs nighttime-story-prep-dev.process_story  # View logs
```

### Local Testing (No Modal)
```bash
./scripts/quickstart.sh                      # One-command test
./scripts/test_story.sh examples/inputs/story.txt  # Quick test
poetry run python tests/test_full_pipeline.py      # Full test
poetry run python tests/test_all_examples.py       # Test all examples
```

### Production
```bash
modal deploy main.py                         # Deploy
modal run main.py::send_daily_chunk          # Manual send
modal run scripts/inspect_db.py              # Check status
modal logs nighttime-story-prep.send_daily_chunk  # View logs
```

### Secrets Management
```bash
./scripts/update-secrets.sh                  # Update from .env
modal secret list                            # List secrets
```

---

## Testing

### Available Test Scripts

| Script | Purpose |
|--------|---------|
| `tests/test_full_pipeline.py` | Complete end-to-end test |
| `tests/test_all_examples.py` | Test all example stories |
| `tests/test_chunker.py` | Test chunking algorithms |
| `tests/test_agent_chunker.py` | Compare Agent vs LLM chunker |
| `tests/test_content_agent.py` | Test agent-based extraction |
| `tests/test_extraction_cleaning.py` | Test metadata removal |
| `tests/test_multi_chunk.py` | Test multi-chunk with recaps |
| `tests/test_email_parser.py` | Test email parsing strategies |
| `scripts/test_story.sh` | Quick CLI test script |

### Running Tests

```bash
# Full pipeline test
poetry run python tests/test_full_pipeline.py

# Test specific story
./scripts/test_story.sh examples/inputs/your-story.txt

# Test all examples
poetry run python tests/test_all_examples.py

# Compare chunking strategies
poetry run python tests/test_agent_chunker.py examples/inputs/pale-lights-example-1.txt 5000
```

---

## Debugging

### Common Issues

#### "No such secret"
```bash
modal secret list
./scripts/update-secrets.sh
```

#### "Volume not found"
```bash
# Volume is created automatically on first run
# Or create manually:
modal volume create story-data-dev
```

#### Agent extraction not working
- Check `ANTHROPIC_API_KEY` in secrets
- Check logs for API errors
- Test locally first: `poetry run python tests/test_extraction_cleaning.py`

#### Content not cleaned properly
```bash
# Check extracted content
cat local_data/raw/story_000001/content.txt

# Verify environment
echo $USE_AGENT_EXTRACTION
echo $ANTHROPIC_API_KEY
```

#### Chunking issues
```bash
# Use simple chunker instead of agent
USE_AGENT_CHUNKER=false ./scripts/test_story.sh examples/inputs/story.txt

# Check chunk files
ls -la local_data/chunks/story_000001/
cat local_data/chunks/story_000001/chunk_manifest.yaml
```

### View Logs

```bash
# Dev logs
modal logs nighttime-story-prep-dev.process_story

# Production logs
modal logs nighttime-story-prep.send_daily_chunk
modal logs nighttime-story-prep.process_story
```

### Inspect Database

```bash
# Production
modal run scripts/inspect_db.py

# Local
sqlite3 test_stories.db

# SQL queries
SELECT id, title, status, word_count FROM stories;
SELECT chunk_number, word_count, sent_to_kindle_at FROM story_chunks WHERE story_id = 1;
```

---

## File Locations

### Dev (Modal Local)
- Database: `/data/stories-dev.db` on `story-data-dev` volume
- Files: `/data/raw/`, `/data/chunks/`, `/data/epubs/`

### Production (Modal)
- Database: `/data/stories.db` on `story-data` volume
- Files: `/data/raw/`, `/data/chunks/`, `/data/epubs/`

### Local Testing
- Database: `./test_stories.db`
- Files: `./local_data/raw/`, `./local_data/chunks/`, `./local_data/epubs/`

---

## Dev vs Production

| Aspect | Dev (default) | Production (`MODAL_ENVIRONMENT=prod`) |
|--------|--------------|--------------------------------------|
| Database | `stories-dev.db` | `stories.db` |
| Volume | `story-data-dev` | `story-data` |
| App Name | `nighttime-story-prep-dev` | `nighttime-story-prep` |
| Scheduling | Manual trigger only | Auto at 8am UTC |
| Hot reload | Yes (`modal serve`) | No |
| Webhooks | Dev URLs | Production URLs |
| Data isolation | Completely separate | Production data |

---

## Additional Documentation

- `CONTENT_CLEANING.md` - Details on metadata removal and content extraction
- `CLAUDE.md` - Project instructions for Claude Code
- `README.md` - High-level project overview
