# CLAUDE.md

Project instructions for Claude Code when working with this codebase.

## Project Overview

Automated pipeline: Patreon stories → email ingestion → AI chunking → EPUB → daily Kindle delivery (8am UTC drip-feed).

## Key Architecture

- **Pipeline**: Email webhook → `extract_content()` (AI-powered) → Intelligent chunking (Agent/LLM/Simple fallbacks) → SQLite → Daily EPUB delivery
- **Modal**: Single codebase with env detection (`MODAL_ENVIRONMENT`). Dev mode (default) uses separate volume/DB and disables schedules.
- **Chunking**: AgentChunker (Claude Agent SDK) → LLMChunker (Claude API) → SimpleChunker (word-count)
- **Content extraction**: Agent-based metadata removal with strategy pattern fallbacks

## File Organization

```
src/                    # All source modules
  ├── chunker.py       # Chunking strategies
  ├── content_extraction_agent.py
  ├── database.py
  ├── email_parser.py
  ├── epub_generator.py
  ├── file_storage.py
  └── kindle_sender.py
tests/                  # All test files
scripts/                # Utility scripts
main.py                 # Modal app entry point
```

## Import Rules

**CRITICAL**: All imports must use `src.` prefix:

- ✅ `from src.database import Database`
- ✅ `from src.chunker import ChunkerFactory`
- ❌ `from database import Database`

This applies to:

- Files in `src/`
- `main.py`
- All test files
- Modal `.add_local_file()` calls must include `src/` path

## Common Commands

```bash
# Development
modal serve main.py                                    # Dev server (auto-reload)
modal run scripts/manage_dev_db.py::list_stories       # Inspect DB
modal run main.py::send_daily_chunk                    # Send next chunk

# Testing
./scripts/quickstart.sh                                # Quick test
poetry run python tests/test_full_pipeline.py          # Full test

# Production
modal deploy main.py                                   # Deploy
```

## Dev vs Production

| Aspect    | Dev (default)                        | Production                     |
| --------- | ------------------------------------ | ------------------------------ |
| Database  | `stories-dev.db` on `story-data-dev` | `stories.db` on `story-data`   |
| Schedules | Disabled                             | Enabled (8am UTC, 6hr retries) |
| Trigger   | `modal serve`                        | `modal deploy`                 |

## Configuration

Environment variables (`.env` or Modal secrets):

- `USE_AGENT_EXTRACTION=true` - AI content extraction
- `USE_AGENT_CHUNKER=true` - AI-powered chunking
- `USE_LLM_CHUNKER=true` - Fallback LLM chunker
- `TARGET_WORDS=5000` - Words per chunk
- `KINDLE_EMAIL` - Destination email for stories
- `FROM_EMAIL` - From address for outgoing emails
- `SMTP_USER` - SMTP authentication username
- `TEST_MODE=true` - Simulate email sending

## Testing Strategy

1. Local testing: Use `./scripts/quickstart.sh` or `poetry run python tests/test_*.py`
2. Modal dev: `modal serve main.py` (uses dev volume, hot-reload enabled)
3. Always test locally before deploying to production
4. Dev and prod are completely isolated (separate volumes/databases)

## Important Notes

- **Modal files**: Always use `src/` prefix in paths
- **Scheduled functions**: Only run in production mode (`MODAL_ENVIRONMENT=prod`)
- **Testing**: Local tests use `./local_data/` and `./test_stories.db`
- **Modal tests**: Use volume-mounted `/data/` directory

## Revamp Instructions

Right now, the entire codebase is hosted on Modal. This makes debugging / logging more difficult than it should be. Instead, we should change architecture so that Modal is only used for model / agent queries, and instead we have a long-running API server that is hosted on a box that captures our requests, includes rough logs, stores data within DB, etc.

The main goal of the project is still the same. I want to enqueue a variety of web serials (but this can be expanded to any stories including existing epubs) that will be chunked into ~X word parts. These will be drip fed via a cron job (once every day) to my Kindle via email, so that I have exactly 1 story to read each night.

The processing will happen like we have currently. We should have some agentic parser that extracts the actual content of the story from the input (which could be a variety of things, including email with a link to the story, email with a link to the story + the password, raw text, a raw epub, etc.). Then, we should take the content and run it through another agent that determines a reasonable breakpoint in the story (no cliffhangers, just scene changes or other natural breaks), roughly conforming to the desired word chunk size, and save those chunks as EPUBs in a blob storage system.

The cron job will once a day (say, 12pm PT) hit the API to find the latest unsent story, and then send it via SMTP to my kindle email address, so I can read it that night.

As for how to receive new stories to chunk + queue, there are a variety of ways:

1. Queue story via automatic email webhook. I'll forward my Patreon emails to a email webhook service which will then ping with the content.
2. Enqueue via Postman endpoint with a link to the actual content

Because logging and visibility is important, please add ability for me to receive updates via email (you can use SMTP here as well). These types of emails should do things like notify me about how we've chunked new stories (when we receive new things), when we queued new blobs to send, if any step failed, etc.

Finally, there is a need for maintenance / editing of story chunks. In the case that parsing looks incorrect, we need to re-queue certain stories, etc. we'll need a good way to remove / requeue stories and chunks to be sent. I'm imagining that in case there's problems we should be able to remove stories, enqueue new ones, change ordering of stories to be sent, and mark certain chunks (or stories) as already sent.

### Architecture

We're going to be leaning heavily on Vercel + NextJS for the API + storage (DB, blob storage, cron jobs for functions, etc.).

For SMTP and email webhooks we'll use Brevo (https://developers.brevo.com/).

### Design Considerations

Please make sure the code is easily debuggable, reviewable, logs, etc. so that I can fix if there are problems. Also, make sure code is modular so that we can rerun parts of the pipeline in case of failure in some intermediate step.

### Future

In the future we'll have other folks who might want to use this, so architecture should be extensible to support queues / stories by person, but for now we can keep it simple and just assume it's me.

Eventually we'll also want this to be a custom MCP server as well, so that I can ask questions about it / make changes via MCP.
