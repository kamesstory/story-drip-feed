# Nighttime Story Prep - NextJS App

This is the main web application for the story processing pipeline, built with Next.js 16 and Supabase.

## Prerequisites

- Node.js 20.9.0 or higher ⚠️
  - Next.js 16 requires Node.js >= 20.9.0
  - Check version: `node --version`
  - Upgrade if needed: Use nvm or download from nodejs.org
- Docker Desktop (for local Supabase)
- Supabase CLI: `npm install -g supabase`

## Local Development Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Initialize and Start Supabase

```bash
# Initialize Supabase (first time only)
supabase init

# Start local Supabase instance
supabase start
```

This will output your local credentials:

- API URL (usually `http://localhost:54321`)
- anon key
- service_role key

### 3. Configure Environment Variables

Copy `env.example` to `.env.local` and update with your Supabase credentials:

```bash
cp env.example .env.local
```

Edit `.env.local` and paste the keys from the `supabase start` output:

```env
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
```

### 4. Apply Database Migrations

```bash
supabase db reset
```

This creates all tables and indexes from the migration files.

### 5. Create Storage Bucket

The `epubs` storage bucket should be created automatically by Supabase. If not, create it manually:

```bash
# Open Supabase Studio
# Visit: http://localhost:54323

# Go to Storage → Create a new bucket
# Name: epubs
# Public: Yes
```

### 6. Start Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:3000`.

## Testing

### Health Check

Test that the API is running:

```bash
# Make sure dev server is running first
npm run dev

# In another terminal:
../scripts/test/test-health.sh
```

Expected output: `✅ Health check passed`

### Database Operations

Test all database CRUD operations:

```bash
# Prerequisites:
# - Supabase running (supabase start)
# - NextJS dev server running (npm run dev)

../scripts/test/test-database-operations.sh
```

This will:

- Create a test story
- Add chunks to the story
- Query and update records
- Test the delivery queue logic
- Clean up test data

### Storage Operations

Test Supabase Storage for EPUB files:

```bash
# Prerequisites:
# - Supabase running (supabase start)
# - NextJS dev server running (npm run dev)
# - Storage bucket 'epubs' exists

../scripts/test/test-storage-operations.sh
```

This will:

- Upload a test EPUB file
- Download it back
- Generate public URLs
- Delete the file

### Type Checking

Verify TypeScript compilation:

```bash
npm run build
```

## Project Structure

```
nextjs-app/
├── app/
│   ├── api/
│   │   └── health/          # Health check endpoint
│   ├── layout.tsx           # Root layout
│   └── page.tsx             # Home page
├── lib/
│   ├── db.ts                # Database utilities (Supabase)
│   ├── storage.ts           # Storage utilities (Supabase Storage)
│   └── supabase.ts          # Supabase client configuration
├── types/
│   └── index.ts             # TypeScript type definitions
├── supabase/
│   ├── config.toml          # Local Supabase configuration
│   └── migrations/          # Database migration files
└── env.example              # Environment variable template
```

## API Endpoints

### Health Check

`GET /api/health`

Returns application health status and database connectivity.

Response:

```json
{
  "status": "ok",
  "timestamp": "2024-10-25T12:00:00.000Z",
  "database": "connected"
}
```

## Database Schema

### `stories`

Main story records with metadata and processing status.

Key fields:

- `id`: Auto-incrementing primary key
- `email_id`: Unique identifier from source email
- `title`, `author`: Story metadata
- `status`: `pending` | `processing` | `chunked` | `sent` | `failed`
- `word_count`: Total word count
- `received_at`: When story was received
- `processed_at`: When chunking completed

### `story_chunks`

Individual chunks of stories ready for delivery.

Key fields:

- `id`: Auto-incrementing primary key
- `story_id`: Foreign key to stories (CASCADE delete)
- `chunk_number`, `total_chunks`: Position in sequence
- `chunk_text`: Full text content
- `storage_path`: Path in Supabase Storage for EPUB file
- `sent_to_kindle_at`: Delivery timestamp (NULL if not sent)

## Storage

EPUB files are stored in the Supabase Storage bucket named `epubs`.

File naming convention: `{sanitized-title}_part{n}.epub`

Storage paths are stored in the `story_chunks.storage_path` field.

## Production Deployment

### 1. Create Supabase Project

Go to [supabase.com](https://supabase.com) and create a new project.

### 2. Link Local Project

```bash
supabase link --project-ref your-project-ref
```

### 3. Push Migrations

```bash
supabase db push
```

### 4. Create Storage Bucket

In Supabase dashboard:

- Go to Storage
- Create bucket named `epubs`
- Set to public access

### 5. Deploy to Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel
```

Set environment variables in Vercel dashboard:

- `NEXT_PUBLIC_SUPABASE_URL` (from Supabase project settings)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` (from Supabase project settings)
- `SUPABASE_SERVICE_ROLE_KEY` (from Supabase project settings)

### 6. Verify Deployment

Visit `https://your-app.vercel.app/api/health`

Should return:

```json
{
  "status": "ok",
  "database": "connected"
}
```

## Development Tips

### Viewing Database

Use Supabase Studio (local):

```bash
# Studio URL is shown when you run: supabase start
# Usually: http://localhost:54323
```

### Resetting Database

```bash
# Drop all tables and recreate from migrations
supabase db reset
```

### Viewing Logs

```bash
# Supabase logs
supabase logs

# NextJS dev logs
# Shown in terminal where you ran 'npm run dev'
```

### Stopping Supabase

```bash
supabase stop
```

## Troubleshooting

### "Missing Supabase environment variables"

Make sure `.env.local` exists and contains valid keys from `supabase start`.

### "Failed to connect to database"

- Check that Supabase is running: `supabase status`
- Verify environment variables are correct
- Try restarting Supabase: `supabase stop && supabase start`

### "Table does not exist"

Run migrations:

```bash
supabase db reset
```

### "Storage bucket 'epubs' not found"

Create the bucket in Supabase Studio or using the CLI.

## Next Steps

After completing Tasks 1 & 2, proceed with:

- Task 3: Modal Python API Service
- Task 4: Brevo Email Integration
- Task 5: Story Processing Pipeline
- Task 6: Daily Delivery System
- Task 7: Logging & Notification System
- Task 8: Admin API Endpoints
- Task 9: Web UI Dashboard

See `MIGRATION_PLAN.md` for full roadmap.
