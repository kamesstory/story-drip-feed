# Production Deployment Guide

Complete step-by-step guide to deploy the Nighttime Story Prep system to production.

## Overview

The system consists of:

1. **Supabase** - PostgreSQL database and storage
2. **Modal API** - Python service for AI-powered content extraction and chunking
3. **Next.js App** - Web application deployed on Vercel
4. **Brevo Email** - Email ingestion and SMTP delivery
5. **Vercel Crons** - Scheduled daily delivery

## Prerequisites

Install required tools:

```bash
# Node.js 20.9.0+
node --version

# Supabase CLI
npm install -g supabase

# Modal CLI
pip install modal

# Vercel CLI
npm install -g vercel
```

## Part 1: Supabase Production Setup

### Step 1.1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Click "New Project"
3. Choose organization and project name (e.g., `nighttime-story-prep-prod`)
4. Set a strong database password
5. Choose a region close to your users
6. Wait for project to provision (~2 minutes)

### Step 1.2: Get Supabase Credentials

From your Supabase dashboard:

1. Go to **Settings** → **API**
2. Copy these values (you'll need them later):
   - **Project URL** (e.g., `https://xxxxx.supabase.co`)
   - **anon/public key** (starts with `eyJ...`)
   - **service_role key** (starts with `eyJ...`)

⚠️ **Keep the service_role key secret** - it has full database access!

### Step 1.3: Create Storage Buckets

In your Supabase dashboard:

1. Go to **Storage**
2. Create first bucket:
   - Name: `story-storage`
   - Public: **No** (private)
   - Click "Create bucket"
3. Create second bucket:
   - Name: `epubs`
   - Public: **Yes** (for public access to EPUB files)
   - Click "Create bucket"

### Step 1.4: Apply Database Migrations

From your project root:

```bash
cd nextjs-app

# Link to your production project
supabase link --project-ref your-project-ref

# Push migrations to production
supabase db push
```

Your project ref is the subdomain from your Supabase URL (e.g., if URL is `https://abc123.supabase.co`, the ref is `abc123`).

✅ **Verify**: Go to **Table Editor** in Supabase dashboard - you should see `stories` and `story_chunks` tables.

---

## Part 2: Modal API Production Deployment

### Step 2.1: Install and Authenticate Modal

```bash
# Install Modal CLI (if not already installed)
pip install modal

# Authenticate
modal setup
```

This will open a browser to authenticate with Modal.

### Step 2.2: Create Modal Secrets

**Important**: We use separate secrets for dev and production to ensure complete environment isolation.

#### Create Development Secrets (for testing)

```bash
# Generate dev API key
DEV_API_KEY=$(openssl rand -hex 32)
echo "Dev API Key: $DEV_API_KEY"

# Create story-prep-secrets-dev
modal secret create story-prep-secrets-dev \
  ANTHROPIC_API_KEY=sk-ant-api03-xxxxxx \
  MODAL_API_KEY=$DEV_API_KEY \
  USE_AGENT_EXTRACTION=true \
  USE_AGENT_CHUNKER=true \
  TARGET_WORDS=8000

# Create supabase-secrets-dev (can use local or dev Supabase)
modal secret create supabase-secrets-dev \
  SUPABASE_URL=https://your-dev-project.supabase.co \
  SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

#### Create Production Secrets

```bash
# Generate production API key (DIFFERENT from dev!)
PROD_API_KEY=$(openssl rand -hex 32)
echo "Prod API Key: $PROD_API_KEY"

# Create story-prep-secrets-prod
modal secret create story-prep-secrets-prod \
  ANTHROPIC_API_KEY=sk-ant-api03-xxxxxx \
  MODAL_API_KEY=$PROD_API_KEY \
  USE_AGENT_EXTRACTION=true \
  USE_AGENT_CHUNKER=true \
  TARGET_WORDS=8000

# Create supabase-secrets-prod
modal secret create supabase-secrets-prod \
  SUPABASE_URL=https://your-prod-project.supabase.co \
  SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

**Important**: Save both API keys! You'll need:

- `DEV_API_KEY` for local testing
- `PROD_API_KEY` for your production Next.js app

Use the Supabase credentials from Step 1.2 for production.

#### Verify secrets

```bash
modal secret list
```

You should see:

- `story-prep-secrets-dev`
- `supabase-secrets-dev`
- `story-prep-secrets-prod`
- `supabase-secrets-prod`

### Step 2.3: Deploy Modal API to Production

```bash
cd modal-api

# Deploy to production (set environment variable first)
export APP_ENV=prod
modal deploy main.py

# Or in one line:
env APP_ENV=prod poetry run modal deploy main.py
```

This creates the production app: `nighttime-story-prep-api` (without `-dev` suffix).

**Note**: The `APP_ENV` environment variable tells the Python code which secrets to use. It's read when the app initializes.

### Step 2.4: Note Modal Endpoint URL

Modal will output a URL like:

```
✓ Created web function fastapi_app => https://username--nighttime-story-prep-api-fastapi-app.modal.run
```

The **base URL** is: `https://username--nighttime-story-prep-api-fastapi-app.modal.run`

This single ASGI endpoint serves all routes:

- `GET /health` - Health check
- `POST /extract-content` - Content extraction
- `POST /chunk-story` - Story chunking

**Save this complete URL** - you'll need it for Next.js configuration (use it as `MODAL_API_URL`).

### Step 2.5: Test Modal API

```bash
# Test health endpoint (no auth required)
curl https://username--nighttime-story-prep-api-fastapi-app.modal.run/health

# Expected response:
# {"status":"healthy","services":{"anthropic_api":"ok","supabase_storage":"ok"}}
```

Or run the full test suite:

```bash
cd ..
export MODAL_API_URL="https://username--nighttime-story-prep-api-fastapi-app.modal.run"
export MODAL_API_KEY="$PROD_API_KEY"  # Use the production API key
./scripts/test/test-modal-api.sh
```

✅ **Success**: You should see "All Modal API tests completed successfully!"

**Note**: The Modal API automatically uses the correct secrets based on the `APP_ENV` variable:

- Default (no env var): Uses `story-prep-secrets-dev` and `supabase-secrets-dev`
- `APP_ENV=prod`: Uses `story-prep-secrets-prod` and `supabase-secrets-prod`

---

## Part 3: Brevo Email Setup

### Step 3.1: Create Brevo Account

1. Go to [brevo.com](https://www.brevo.com) (formerly Sendinblue)
2. Sign up for a free account
3. Verify your email address

### Step 3.2: Set Up SMTP Credentials

1. Go to **Settings** → **SMTP & API**
2. Click **SMTP** tab
3. Note your SMTP credentials:
   - **Host**: `smtp-relay.brevo.com`
   - **Port**: `587`
   - **Username**: (shown on page)
   - **Password**: Click "Generate a new SMTP key" if needed

### Step 3.3: Verify Sender Email

1. Go to **Settings** → **Senders & IP**
2. Click **Add a sender**
3. Enter your email address (e.g., `you@yourdomain.com`)
4. Verify via the confirmation email
5. This will be your `FROM_EMAIL` for sending to Kindle

### Step 3.4: Set Up Inbound Email (Optional - for webhook)

If you want to receive stories via email webhook:

1. Go to **Settings** → **Inbound Parsing**
2. Add your domain (e.g., `reply.yourdomain.com`)
3. Configure DNS MX records as shown
4. Set webhook URL to your Vercel deployment URL + `/api/webhooks/email`
   - Example: `https://your-app.vercel.app/api/webhooks/email`
5. Test by sending an email to your inbound address

---

## Part 4: Next.js on Vercel Deployment

### Step 4.1: Prepare Environment Variables

Create a file to track your production environment variables (don't commit this!):

```bash
# Create a local file for reference
cat > nextjs-app/.env.production.local << 'EOF'
# Supabase Production
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Modal API Production
MODAL_API_URL=https://your-username--nighttime-story-prep-api
MODAL_API_KEY=your-modal-api-key

# Brevo SMTP
BREVO_SMTP_HOST=smtp-relay.brevo.com
BREVO_SMTP_PORT=587
BREVO_SMTP_USER=your-brevo-smtp-user
BREVO_SMTP_PASSWORD=your-brevo-smtp-password

# Email Configuration
KINDLE_EMAIL=your-kindle-email@kindle.com
FROM_EMAIL=verified-sender@yourdomain.com
ADMIN_EMAIL=your-email@example.com

# App Configuration
TARGET_WORDS=8000
NODE_ENV=production
TEST_MODE=false

# Vercel Cron Secret (generate below)
CRON_SECRET=<generate-secure-random-string>
EOF
```

Generate the `CRON_SECRET`:

```bash
openssl rand -hex 32
```

⚠️ **Add `.env.production.local` to `.gitignore`** - never commit secrets!

### Step 4.2: Deploy to Vercel

```bash
cd nextjs-app

# Login to Vercel (first time only)
vercel login

# Deploy to production
vercel --prod
```

Follow the prompts:

- Set up and deploy: **Yes**
- Which scope: Choose your account
- Link to existing project: **No** (or Yes if you already created one)
- Project name: `nighttime-story-prep` (or your preferred name)
- Directory: `./` (current directory)
- Override settings: **No**

Vercel will:

1. Build your Next.js app
2. Deploy to production
3. Give you a production URL (e.g., `https://nighttime-story-prep.vercel.app`)

### Step 4.3: Configure Environment Variables in Vercel

You have two options:

#### Option A: Via Vercel Dashboard (Recommended)

1. Go to [vercel.com/dashboard](https://vercel.com/dashboard)
2. Select your project
3. Go to **Settings** → **Environment Variables**
4. Add each variable from your `.env.production.local` file:
   - Click **Add New**
   - Enter key and value
   - Select "Production" environment
   - Click **Save**
5. Repeat for all variables

#### Option B: Via Vercel CLI

```bash
# Set each variable individually
vercel env add NEXT_PUBLIC_SUPABASE_URL production
# Paste the value when prompted

# Or use the pull/push commands (Vercel v28+)
vercel env pull .env.vercel.local
# Edit .env.vercel.local
vercel env push .env.vercel.local production
```

### Step 4.4: Redeploy with Environment Variables

After adding environment variables:

```bash
# Trigger a new deployment to use the new env vars
vercel --prod
```

Or in the Vercel dashboard:

- Go to **Deployments**
- Click the three dots on the latest deployment
- Click **Redeploy**

### Step 4.5: Verify Deployment

Test the health endpoint:

```bash
curl https://your-app.vercel.app/api/health
```

Expected response:

```json
{
  "status": "ok",
  "timestamp": "2024-10-27T...",
  "database": "connected"
}
```

✅ **Success**: Your Next.js app is live!

---

## Part 5: Configure Scheduled Delivery

### Step 5.1: Understand the Cron Setup

The file `nextjs-app/vercel.json` already configures a cron job:

```json
{
  "crons": [
    {
      "path": "/api/delivery/send-next",
      "schedule": "0 20 * * *"
    }
  ]
}
```

This runs at **20:00 UTC** (8pm UTC) daily, which sends the next chunk to your Kindle.

### Step 5.2: Verify Cron Secret

Ensure `CRON_SECRET` is set in your Vercel environment variables (from Step 4.3).

The cron endpoint uses this secret to authenticate Vercel's cron runner.

### Step 5.3: Test Manual Delivery

Test the delivery endpoint manually:

```bash
# Replace with your actual CRON_SECRET
curl -X POST https://your-app.vercel.app/api/delivery/send-next \
  -H "Authorization: Bearer your-cron-secret" \
  -H "Content-Type: application/json"
```

Expected response (if chunks are available):

```json
{
  "status": "success",
  "delivered": true,
  "chunks_sent": 1,
  "details": { ... }
}
```

Or if no chunks to send:

```json
{
  "status": "success",
  "delivered": false,
  "message": "No chunks ready for delivery"
}
```

### Step 5.4: Monitor Cron Executions

In Vercel dashboard:

1. Go to your project
2. Click **Settings** → **Crons**
3. You should see your cron job listed
4. Check **Logs** tab to see execution history

---

## Part 6: Configure Kindle Email

### Step 6.1: Find Your Kindle Email

1. Go to [amazon.com/mycd](https://www.amazon.com/mycd) (or your regional Amazon site)
2. Go to **Preferences** → **Personal Document Settings**
3. Find your Kindle email (e.g., `username@kindle.com`)
4. This is your `KINDLE_EMAIL` value

### Step 6.2: Approve Sender Email

In the same Amazon page:

1. Scroll to **Approved Personal Document E-mail List**
2. Click **Add a new approved e-mail address**
3. Enter your `FROM_EMAIL` (the verified Brevo sender from Part 3)
4. Click **Add Address**

⚠️ **Important**: Amazon will only accept EPUBs from approved email addresses!

### Step 6.3: Test Kindle Delivery

Run a full end-to-end test:

```bash
cd scripts/test
./test-delivery.sh
```

This will:

1. Create a test story
2. Chunk it
3. Generate an EPUB
4. Send to your Kindle email

Check your Kindle device/app - the EPUB should appear in a few minutes.

---

## Part 7: End-to-End Testing

### Step 7.1: Test Story Ingestion

```bash
cd scripts/test
./test-ingest-e2e.sh
```

This tests the full pipeline:

1. Ingest story via API
2. Extract content (Modal API)
3. Chunk story (Modal API)
4. Store in database
5. Generate EPUB

### Step 7.2: Test Email Webhook

```bash
./test-email-webhook.sh
```

This simulates an incoming email to the webhook endpoint.

### Step 7.3: Test Delivery

```bash
./test-delivery.sh
```

This tests the daily delivery cron job.

### Step 7.4: Run All Tests

```bash
./test-all.sh
```

Runs all test suites in sequence.

---

## Part 8: Production Checklist

### Security

- [ ] All secrets stored in Modal Secrets (not in code)
- [ ] `CRON_SECRET` set and secure (32+ hex characters)
- [ ] `MODAL_API_KEY` set and secure (32+ hex characters)
- [ ] Supabase `service_role_key` is secret (not the anon key)
- [ ] `.env.production.local` is in `.gitignore`
- [ ] Supabase `story-storage` bucket is **private**
- [ ] Supabase `epubs` bucket is **public**

### Configuration

- [ ] Supabase production project created
- [ ] Storage buckets created (`story-storage`, `epubs`)
- [ ] Database migrations applied
- [ ] Modal API deployed to production (`MODAL_ENVIRONMENT=prod`)
- [ ] Vercel app deployed with all environment variables
- [ ] Brevo SMTP configured and sender verified
- [ ] Kindle email approved in Amazon settings
- [ ] `TEST_MODE=false` in production

### Testing

- [ ] Modal API health check passes
- [ ] Next.js health check passes
- [ ] Story ingestion works
- [ ] Content extraction works (Modal API)
- [ ] Chunking works (Modal API)
- [ ] EPUB generation works
- [ ] Email delivery to Kindle works
- [ ] Cron job tested manually
- [ ] All test scripts pass

### Monitoring

- [ ] Modal logs accessible (`modal app logs nighttime-story-prep-api`)
- [ ] Vercel logs accessible (dashboard → Logs)
- [ ] Supabase logs accessible (dashboard → Logs)
- [ ] Cron job executions visible in Vercel
- [ ] Admin email configured for notifications

---

## Part 9: Ongoing Operations

### Viewing Logs

**Modal API logs:**

```bash
# View recent logs
modal app logs nighttime-story-prep-api

# Follow live logs
modal app logs nighttime-story-prep-api --follow

# Logs for specific function
modal app logs nighttime-story-prep-api.extract_content_endpoint
```

**Vercel logs:**

- Dashboard → Your Project → Logs
- Or use CLI: `vercel logs`

**Supabase logs:**

- Dashboard → Logs Explorer
- Query logs with SQL

### Database Management

**View stories:**

```bash
# Use Supabase dashboard
# Go to: Table Editor → stories

# Or use SQL Editor:
SELECT id, title, author, status, word_count, received_at
FROM stories
ORDER BY received_at DESC
LIMIT 10;
```

**Check pending chunks:**

```bash
SELECT s.title, sc.chunk_number, sc.total_chunks
FROM story_chunks sc
JOIN stories s ON sc.story_id = s.id
WHERE sc.sent_to_kindle_at IS NULL
ORDER BY s.received_at, sc.chunk_number;
```

### Updating Code

**Modal API:**

```bash
cd modal-api
# Make changes
MODAL_ENVIRONMENT=prod modal deploy main.py
```

**Next.js App:**

```bash
cd nextjs-app
# Make changes
git push  # If using Git integration

# Or manual deploy:
vercel --prod
```

### Troubleshooting

**Delivery not working:**

1. Check Vercel cron logs
2. Verify `CRON_SECRET` is correct
3. Check `KINDLE_EMAIL` and `FROM_EMAIL` are correct
4. Verify sender is approved in Amazon settings
5. Check Brevo SMTP credentials

**Modal API failing:**

1. Check Modal logs: `modal app logs nighttime-story-prep-api`
2. Verify secrets: `modal secret list`
3. Test health endpoint
4. Check Supabase connectivity

**Database issues:**

1. Verify Supabase credentials in Vercel env vars
2. Check Supabase dashboard for connection limits
3. Review database logs in Supabase dashboard

**Storage issues:**

1. Verify buckets exist: `story-storage` and `epubs`
2. Check bucket permissions (private vs public)
3. Verify Supabase service role key is correct

---

## Part 10: Cost Estimation

### Supabase

- **Free tier**: 500MB database, 1GB storage, 2GB bandwidth
- **Pro tier**: $25/month - 8GB database, 100GB storage
- Estimate: Free tier sufficient for testing, Pro for production with heavy use

### Modal

- **Free tier**: $30/month credit
- **Compute**: ~$0.0001/second for CPU
- **Chunking**: ~10-30 seconds per story = $0.001-$0.003 per story
- Estimate: $5-20/month for moderate use (10-50 stories/month)

### Vercel

- **Hobby tier**: Free for personal projects
- **Pro tier**: $20/month per team member
- Estimate: Free tier sufficient unless you need team features

### Brevo

- **Free tier**: 300 emails/day
- **Lite tier**: $25/month - 10k emails/month
- Estimate: Free tier sufficient for personal use

### Anthropic (Claude API)

- **Claude 3.5 Sonnet**: ~$3 per million tokens (input), $15 per million tokens (output)
- **Per story**: ~50k tokens input, ~5k tokens output = $0.15-$0.30 per story
- Estimate: $5-15/month for moderate use (10-50 stories/month)

**Total estimated cost**: $5-80/month depending on usage and tiers.

---

## Quick Reference

### Important URLs

| Service            | URL                            | Purpose                     |
| ------------------ | ------------------------------ | --------------------------- |
| Supabase Dashboard | https://supabase.com/dashboard | Manage database and storage |
| Modal Dashboard    | https://modal.com/apps         | View apps and logs          |
| Vercel Dashboard   | https://vercel.com/dashboard   | Manage deployments          |
| Brevo Dashboard    | https://app.brevo.com          | Email configuration         |
| Amazon Kindle      | https://amazon.com/mycd        | Kindle settings             |

### Key Commands

```bash
# Modal
modal deploy main.py                                    # Deploy
modal app logs nighttime-story-prep-api --follow       # View logs
modal secret list                                       # List secrets

# Vercel
vercel --prod                                           # Deploy
vercel logs                                             # View logs
vercel env ls                                           # List env vars

# Supabase
supabase db push                                        # Apply migrations
supabase db reset                                       # Reset local DB
supabase link --project-ref XXX                         # Link to project

# Testing
./scripts/test/test-all.sh                              # Run all tests
./scripts/test/test-delivery.sh                         # Test delivery
./scripts/test/test-modal-api.sh                        # Test Modal API
```

---

## Support and Resources

### Documentation

- [Modal Docs](https://modal.com/docs)
- [Vercel Docs](https://vercel.com/docs)
- [Supabase Docs](https://supabase.com/docs)
- [Next.js Docs](https://nextjs.org/docs)
- [Brevo Docs](https://developers.brevo.com)

### Project Documentation

- `modal-api/DEPLOYMENT.md` - Detailed Modal deployment guide
- `nextjs-app/README.md` - Next.js setup and development
- `MIGRATION_PLAN.md` - System architecture and design
- `scripts/TEST_README.md` - Testing documentation

### Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review the relevant logs (Modal, Vercel, Supabase)
3. Verify all environment variables are set correctly
4. Run the test scripts to isolate the issue
5. Check the project's GitHub issues (if applicable)

---

**Congratulations!** 🎉 Your Nighttime Story Prep system is now deployed to production!

You should now be able to:

- Receive stories via email webhook
- Process them with AI-powered extraction and chunking
- Automatically deliver one chunk per day to your Kindle
- Monitor and manage everything through the respective dashboards
