# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated pipeline that receives Patreon stories via email, intelligently chunks them using AI, generates EPUBs, and delivers ONE chunk per day to Kindle at 8am UTC (drip-feed system).

## Architecture

**Core Pipeline:**
1. Email webhook receives parsed emails → `EmailParser` extracts story content (inline text or password-protected URLs)
2. `LLMChunker` (or `SimpleChunker`) splits text into ~5k word chunks at natural narrative breaks (scene changes, perspective shifts, completed emotional arcs)
3. Chunks are saved to database with full text
4. `send_daily_chunk` scheduled function (8am UTC) sends ONE chunk per day
5. `EPUBGenerator` creates EPUB on-demand when sending
6. `KindleSender` delivers via SMTP to Kindle email
7. `Database` (SQLite on Modal Volume) tracks status: pending → processing → chunked → sent/failed

**Key Design Patterns:**
- Strategy pattern for chunking: `LLMChunker` uses Claude to identify natural break points, `SimpleChunker` as fallback
- Strategy pattern for email parsing (supports multiple content sources)
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
