# Nighttime Story Prep - Complete Development Guide

Automated pipeline that receives Patreon stories via email, intelligently chunks them using AI, generates EPUBs, and delivers ONE chunk per day to Kindle at 8am UTC.

## Table of Contents

- [Quick Start](#quick-start)
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

## Local Development with Modal

Use `main_local.py` for local development with live endpoints that auto-reload on code changes.

### Start Dev Server

```bash
modal serve main_local.py
```

This starts a local development server with:
- ✅ Separate dev database (`story-data-dev` volume)
- ✅ Live webhook endpoints
- ✅ URL submission endpoint
- ✅ Status checking endpoint
- ✅ Hot-reload on file changes
- ✅ Won't affect production data

**Output:**
```
✓ Created web function submit_url => https://you--nighttime-story-prep-dev-submit-url.modal.run
✓ Created web function webhook => https://you--nighttime-story-prep-dev-webhook.modal.run
✓ Created web function status => https://you--nighttime-story-prep-dev-status.modal.run
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

#### Check Status

```bash
curl $STATUS_URL | jq
```

Response shows all stories and next chunk to send:
```json
{
  "status": "ok",
  "database": "/data/stories-dev.db",
  "stories": [
    {
      "id": 1,
      "title": "Test Story",
      "status": "chunked",
      "word_count": 7200,
      "chunks": "0/2"
    }
  ],
  "next_to_send": {
    "title": "Test Story",
    "chunk": "1/2",
    "words": 3600
  }
}
```

#### Send Next Chunk Manually

```bash
modal run main_local.py::send_next_chunk
```

### Typical Dev Workflow

```bash
# Terminal 1: Start dev server
modal serve main_local.py

# Terminal 2: Submit test story
curl -X POST https://your-dev/submit_url -d '{"url": "..."}'

# Watch Terminal 1 for processing logs

# Check result
curl https://your-dev/status | jq

# Test sending
modal run main_local.py::send_next_chunk

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
modal serve main_local.py                    # Start dev server
modal run main_local.py                      # Test with example story
modal run main_local.py::send_next_chunk     # Send next chunk
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

| Aspect | Dev (`main_local.py`) | Production (`main.py`) |
|--------|----------------------|----------------------|
| Database | `stories-dev.db` | `stories.db` |
| Volume | `story-data-dev` | `story-data` |
| Scheduling | Manual trigger only | Auto at 8am UTC |
| Hot reload | Yes (`modal serve`) | No |
| Webhooks | Dev URLs | Production URLs |
| Data isolation | Completely separate | Production data |

---

## Additional Documentation

- `CONTENT_CLEANING.md` - Details on metadata removal and content extraction
- `CLAUDE.md` - Project instructions for Claude Code
- `README.md` - High-level project overview
