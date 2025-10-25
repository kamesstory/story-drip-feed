# Architecture Migration Plan: Modal → Vercel/NextJS

## Overview

Migrate the story processing pipeline from Modal-only to Vercel/NextJS with Modal as a separate Python API service, improving debuggability, logging, and maintainability.

**Current Architecture**: All-in-one Modal app (processing + scheduling + storage)

**Target Architecture**:

- NextJS/Vercel (main API, database, blob storage, cron)
- Modal (separate Python API service for AI/agent operations only)
- Brevo (SMTP + email webhooks)

## High-Level Task Breakdown

### Task 1: NextJS Project Setup & Infrastructure

**Goal**: Initialize NextJS project with Vercel infrastructure

**Steps**:

- Initialize NextJS 14+ project with TypeScript and App Router
- Configure Vercel deployment settings
- Set up environment variables and secrets management
- Initialize Vercel Postgres database
- Set up Vercel Blob storage for EPUB files
- Create basic project structure (`/app/api`, `/lib`, `/types`)

**Key files to create**:

- `package.json`
- `next.config.js`
- `tsconfig.json`
- `/lib/db.ts`
- `/lib/storage.ts`

**Test script**: `scripts/test/test-health.sh` - verify NextJS runs and health endpoint works

---

### Task 2: Database Schema & Models

**Goal**: Design and implement PostgreSQL schema for stories, chunks, and logs

**Steps**:

- Design schema: `stories`, `chunks`, `delivery_log`, `processing_log`
- Create TypeScript types matching schema
- Write migration scripts for Vercel Postgres
- Add indexes for common queries (next unsent chunk, story status)
- Create database utility functions (CRUD operations)

**Key considerations**:

- Track story source (email, manual API, etc.)
- Processing status (pending, extracting, chunking, complete, failed)
- Chunk order and delivery sequence
- Delivery timestamps and status
- Error logs with stack traces

**Test script**: `scripts/test/test-database.sh` - test CRUD operations for all tables

---

### Task 3: Modal Python API Service

**Goal**: Refactor existing Modal code into HTTP API endpoints

**Steps**:

- Refactor existing Modal code (`main.py`, `src/`) to expose HTTP endpoints
- Create `/extract-content` endpoint (calls `content_extraction_agent.py`)
- Create `/chunk-story` endpoint (calls `chunker.py` with agent/LLM/simple fallbacks)
- Keep existing agent logic intact, just wrap in HTTP handlers
- Add request/response validation and error handling
- Deploy as separate Modal app

**Endpoints needed**:

- `POST /extract-content`
  - Input: `{ "content": "...", "url": "...", "password": "..." }`
  - Output: `{ "content": "...", "metadata": {...} }`
- `POST /chunk-story`
  - Input: `{ "content": "...", "target_words": 5000 }`
  - Output: `{ "chunks": [{ "content": "...", "word_count": 4998 }] }`

**Test script**: `scripts/test/test-modal-api.sh` - test both endpoints with sample data

---

### Task 4: Brevo Email Integration

**Goal**: Set up email sending and receiving via Brevo

**Steps**:

- Set up Brevo account and API keys
- Create SMTP client for Kindle delivery emails (using Brevo)
- Create SMTP client for admin notification emails
- Set up Brevo inbound webhook URL in NextJS
- Create NextJS webhook handler at `/api/webhooks/email`
- Parse inbound emails and extract story links/content

**Key files**:

- `/lib/email/brevo-smtp.ts`
- `/lib/email/notifications.ts`
- `/app/api/webhooks/email/route.ts`

**Test script**: `scripts/test/test-email.sh` - test SMTP with TEST_MODE (no actual sends)

---

### Task 5: Story Processing Pipeline (NextJS API)

**Goal**: Build end-to-end story ingestion and processing pipeline

**Steps**:

- Create `/api/stories/ingest` endpoint (receives story from email webhook or manual POST)
- Implement content extraction flow (calls Modal API)
- Implement chunking flow (calls Modal API)
- Save story metadata to Postgres
- Save chunk EPUBs to Vercel Blob
- Record processing events in `processing_log` table
- Send notification email on success/failure

**Flow**:

```
Webhook/API → Parse input → Call Modal /extract-content →
Call Modal /chunk-story → Generate EPUBs → Store in Blob →
Update DB → Send notification email
```

**Test script**: `scripts/test/test-ingest.sh` - end-to-end test with sample story

---

### Task 6: Daily Delivery System (Cron + API)

**Goal**: Implement scheduled daily delivery to Kindle

**Steps**:

- Create `/api/delivery/send-next` endpoint
- Query DB for next unsent chunk (earliest created, not yet sent)
- Retrieve EPUB from Vercel Blob
- Send via Brevo SMTP to Kindle email
- Update `delivery_log` with timestamp and status
- Send confirmation notification email
- Configure Vercel Cron to run daily at 12pm PT (8pm UTC)

**Key files**:

- `/app/api/delivery/send-next/route.ts`
- `vercel.json` (cron config)

**Test script**: `scripts/test/test-delivery.sh` - test delivery endpoint manually

---

### Task 7: Logging & Notification System

**Goal**: Add structured logging and email notifications

**Steps**:

- Create structured logging utility with levels (info, warn, error)
- Log to stdout (Vercel captures these) and optionally to DB
- Create notification email templates (new story, chunks created, delivery sent, errors)
- Add error boundaries and retry logic for external API calls
- Track processing duration and success rates

**Key files**:

- `/lib/logger.ts`
- `/lib/notifications.ts`
- Email templates in `/lib/email/templates/`

**Notification types**:

- New story received and queued
- Story successfully chunked (N chunks created)
- Daily chunk delivered to Kindle
- Processing errors with details
- Queue empty warning

**Test script**: Integrated into other test scripts (all should log properly)

---

### Task 8: Admin & Maintenance API Endpoints

**Goal**: Build API endpoints for manual story/chunk management

**Endpoints to create**:

- `GET /api/admin/stories` - List all stories with status
- `GET /api/admin/chunks/:storyId` - List chunks for a story
- `DELETE /api/admin/stories/:id` - Delete story and chunks
- `POST /api/admin/stories/:id/requeue` - Mark all chunks as unsent
- `POST /api/admin/chunks/:id/mark-sent` - Manually mark chunk as sent/unsent
- `POST /api/admin/stories/reorder` - Change queue order
- `POST /api/admin/reprocess/:storyId/:step` - Re-run extraction or chunking
- Add authentication middleware for admin endpoints

**Key files**:

- `/app/api/admin/**/route.ts`
- `/middleware.ts` (auth)

**Test script**: `scripts/test/test-admin.sh` - test all admin operations sequentially

---

### Task 9: Web UI Dashboard (Final Step)

**Goal**: Build admin dashboard for visual story management

**Features**:

- Story list view with filters (pending, processing, complete, failed)
- Individual story detail page showing chunks and delivery status
- Queue management interface with drag-and-drop reordering
- Manual action buttons (delete, requeue, mark sent, reprocess)
- Processing and delivery logs viewer
- Simple authentication (Vercel auth or basic password)

**Key files**:

- `/app/dashboard/page.tsx`
- `/app/dashboard/stories/[id]/page.tsx`
- `/components/admin/*`

**Test**: Manual testing via browser at `http://localhost:3000/dashboard`

---

## Testing Strategy

**Principle**: Keep it simple. Each architectural component gets one test script.

### Component Test Scripts (in `/scripts/test/`)

1. `test-health.sh` - Test health endpoint and basic NextJS setup
2. `test-database.sh` - Test DB operations (CRUD for stories/chunks)
3. `test-modal-api.sh` - Test Modal endpoints (extract-content, chunk-story)
4. `test-storage.sh` - Test Vercel Blob (upload/download EPUBs)
5. `test-email.sh` - Test Brevo SMTP (with TEST_MODE to skip actual sends)
6. `test-ingest.sh` - Test story ingestion endpoint
7. `test-delivery.sh` - Test delivery endpoint
8. `test-admin.sh` - Test admin endpoints (requeue, delete, etc.)

### Supporting Infrastructure

- **Health endpoint**: `/api/health` showing DB, Modal, and Brevo connectivity status
- **Test mode**: `TEST_MODE=true` environment variable to mock external calls
- **Local dev**: Use `next dev` locally with ngrok for webhook testing

### Local Development Workflow

```bash
# Run NextJS locally
npm run dev

# In another terminal, expose with ngrok for webhook testing
ngrok http 3000

# Run any test script
./scripts/test/test-ingest.sh

# Check health
curl http://localhost:3000/api/health
```

---

## Migration Strategy

1. **Build in parallel**: Develop NextJS infrastructure alongside existing Modal setup
2. **Deploy Modal API early**: Get Task 3 deployed first for integration testing
3. **Test incrementally**: Use test scripts to verify each component as it's built
4. **Gradual cutover**: Update Brevo webhook to point to new NextJS endpoint
5. **Keep backup**: Maintain Modal dev environment during transition period

### Cutover Checklist

- [ ] All test scripts passing
- [ ] Modal API deployed and responding
- [ ] Database schema migrated
- [ ] Brevo configured with new webhook URL
- [ ] First manual story successfully processed end-to-end
- [ ] Cron job tested and delivering correctly
- [ ] Admin endpoints tested and working

---

## Environment Variables

### NextJS (Vercel)

```env
# Database
POSTGRES_URL=<vercel-postgres-url>

# Blob Storage
BLOB_READ_WRITE_TOKEN=<vercel-blob-token>

# Modal API
MODAL_API_URL=https://<modal-app-url>
MODAL_API_KEY=<modal-api-key>

# Brevo
BREVO_API_KEY=<brevo-api-key>
BREVO_SMTP_HOST=smtp-relay.brevo.com
BREVO_SMTP_PORT=587
BREVO_SMTP_USER=<brevo-smtp-user>
BREVO_SMTP_PASSWORD=<brevo-smtp-password>

# Email addresses
KINDLE_EMAIL=<your-kindle-email>
FROM_EMAIL=<from-email>
ADMIN_EMAIL=<your-email-for-notifications>

# Configuration
TARGET_WORDS=5000
TEST_MODE=false

# Authentication (for admin endpoints)
ADMIN_PASSWORD=<secure-password>
```

### Modal API

```env
# Keep existing Modal secrets
ANTHROPIC_API_KEY=<key>

# Add authentication for NextJS to call Modal
MODAL_API_KEY=<shared-secret>
```

---

## File Structure (Target)

```
nighttime-story-prep/
├── MIGRATION_PLAN.md          # This file
├── CLAUDE.md                   # Updated with new architecture
├── README.md                   # Updated with new setup instructions
│
├── modal-api/                  # Refactored Modal code
│   ├── main.py                 # HTTP endpoints
│   └── src/                    # Existing logic (mostly unchanged)
│       ├── content_extraction_agent.py
│       ├── chunker.py
│       └── ...
│
├── nextjs-app/                 # New NextJS application
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── vercel.json             # Cron configuration
│   │
│   ├── app/
│   │   ├── api/
│   │   │   ├── health/route.ts
│   │   │   ├── webhooks/email/route.ts
│   │   │   ├── stories/ingest/route.ts
│   │   │   ├── delivery/send-next/route.ts
│   │   │   └── admin/
│   │   │       ├── stories/route.ts
│   │   │       ├── chunks/[storyId]/route.ts
│   │   │       └── ...
│   │   │
│   │   └── dashboard/
│   │       ├── page.tsx
│   │       └── stories/[id]/page.tsx
│   │
│   ├── lib/
│   │   ├── db.ts               # Database utilities
│   │   ├── storage.ts          # Blob storage utilities
│   │   ├── logger.ts           # Logging utilities
│   │   ├── notifications.ts    # Email notifications
│   │   ├── modal-client.ts     # Modal API client
│   │   └── email/
│   │       ├── brevo-smtp.ts
│   │       └── templates/
│   │
│   ├── types/
│   │   └── index.ts            # TypeScript types
│   │
│   └── components/
│       └── admin/              # Dashboard components
│
└── scripts/
    └── test/
        ├── test-health.sh
        ├── test-database.sh
        ├── test-modal-api.sh
        ├── test-storage.sh
        ├── test-email.sh
        ├── test-ingest.sh
        ├── test-delivery.sh
        └── test-admin.sh
```

---

## Timeline Estimate

- **Task 1**: 2-3 hours (setup + basic infrastructure)
- **Task 2**: 3-4 hours (schema design + migrations + utilities)
- **Task 3**: 4-5 hours (refactor Modal code to HTTP endpoints)
- **Task 4**: 3-4 hours (Brevo integration + webhook handler)
- **Task 5**: 5-6 hours (full processing pipeline with error handling)
- **Task 6**: 2-3 hours (delivery endpoint + cron configuration)
- **Task 7**: 2-3 hours (logging + notification templates)
- **Task 8**: 4-5 hours (admin API endpoints + auth)
- **Task 9**: 6-8 hours (dashboard UI + authentication)

**Total**: ~30-40 hours of development time

---

## Future Enhancements

- Multi-user support (separate queues per user)
- MCP server integration for AI-assisted management
- Advanced scheduling (specific times per user)
- Story recommendation system
- Reading analytics and progress tracking
- Web reader interface (alternative to Kindle)
