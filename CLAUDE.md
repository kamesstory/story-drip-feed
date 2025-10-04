# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated pipeline that receives Patreon stories via email, chunks them into ~10k word segments, generates EPUBs, and delivers to Kindle.

## Architecture

**Core Pipeline:**
1. Email webhook receives parsed emails → `EmailParser` extracts story content (inline text or password-protected URLs)
2. `SimpleChunker` splits text into ~10k word chunks at paragraph boundaries (strategy pattern for future intelligent chunking)
3. `EPUBGenerator` creates EPUB files for each chunk
4. `KindleSender` delivers via SMTP to Kindle email
5. `Database` (SQLite on Modal Volume) tracks status: pending → processing → chunked → sent/failed

**Key Design Patterns:**
- Strategy pattern for chunking (extendable to LLM-based intelligent chunking)
- Strategy pattern for email parsing (supports multiple content sources)
- Status tracking with retry logic for failed deliveries

**Modal Infrastructure:**
- Persistent volume for SQLite DB and generated EPUBs
- Webhook endpoint for email ingestion
- Scheduled cron job (every 6 hours) retries failed stories (max 3 attempts)

## Development Commands

**Setup:**
```bash
pip install -r requirements.txt
modal token new
# Copy .env.example to .env and configure
```

**Deploy:**
```bash
modal deploy main.py
```

**Test locally:**
```bash
modal run main.py
```

**Create Modal secret:**
```bash
modal secret create story-prep-secrets \
  KINDLE_EMAIL=your-kindle@kindle.com \
  SMTP_HOST=smtp.gmail.com \
  SMTP_PORT=587 \
  SMTP_USER=your-email@gmail.com \
  SMTP_PASSWORD=your-app-password
```

## Email Ingestion Setup

Use Mailgun/SendGrid/Cloudflare Email Workers to forward Patreon emails to the webhook URL.

Example webhook URL after deployment:
```
https://your-username--nighttime-story-prep-webhook.modal.run
```

Configure your email service to POST parsed emails to this endpoint.
