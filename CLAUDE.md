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

| Aspect | Dev (default) | Production |
|--------|--------------|------------|
| Database | `stories-dev.db` on `story-data-dev` | `stories.db` on `story-data` |
| Schedules | Disabled | Enabled (8am UTC, 6hr retries) |
| Trigger | `modal serve` | `modal deploy` |

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
