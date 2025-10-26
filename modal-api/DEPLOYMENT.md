# Modal API Deployment Guide

This guide walks through deploying the Modal API service step-by-step.

## Prerequisites

1. Modal CLI installed and configured:

   ```bash
   pip install modal
   modal setup
   ```

2. Supabase project with Storage bucket created
3. Anthropic API key for Claude
4. Generated secure API key for authentication

## Step 1: Create Supabase Storage Bucket

In your Supabase project dashboard:

1. Go to Storage
2. Create a new bucket named `story-storage`
3. Set it to **Private** (not public)
4. Note your Supabase URL and Service Role Key from Settings > API

## Step 2: Configure Modal Secrets

### Create story-prep-secrets

```bash
modal secret create story-prep-secrets \
  ANTHROPIC_API_KEY=sk-ant-api03-xxx \
  MODAL_API_KEY=$(openssl rand -hex 32) \
  USE_AGENT_EXTRACTION=true \
  USE_AGENT_CHUNKER=true
```

**Note:** Save the `MODAL_API_KEY` value - you'll need it for NextJS configuration.

### Create supabase-secrets

```bash
modal secret create supabase-secrets \
  SUPABASE_URL=https://your-project.supabase.co \
  SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Security Note:** The service role key has full access to your Supabase project. Keep it secret!

## Step 3: Deploy to Modal (Development)

From the project root:

```bash
cd modal-api
modal deploy main.py
```

This will:

- Build the Docker image with dependencies
- Deploy as `nighttime-story-prep-api-dev`
- Create three web endpoints

## Step 4: Note the Endpoint URLs

After deployment, Modal displays URLs like:

```
✓ Created web function extract-content-endpoint => https://username--nighttime-story-prep-api-dev-extract-content-endpoint.modal.run
✓ Created web function chunk-story-endpoint => https://username--nighttime-story-prep-api-dev-chunk-story-endpoint.modal.run
✓ Created web function health-endpoint => https://username--nighttime-story-prep-api-dev-health-endpoint.modal.run
```

The base URL format is: `https://username--nighttime-story-prep-api-dev`

## Step 5: Test the Deployment

Set environment variables:

```bash
export MODAL_API_URL="https://username--nighttime-story-prep-api-dev"
export MODAL_API_KEY="your-api-key-from-step-2"
```

Run the test script:

```bash
cd ..
./scripts/test/test-modal-api.sh
```

Expected output:

```
✅ All Modal API tests completed successfully!
```

## Step 6: Configure NextJS

Add to `nextjs-app/.env.local`:

```env
MODAL_API_URL=https://username--nighttime-story-prep-api-dev
MODAL_API_KEY=your-api-key-from-step-2
```

## Production Deployment

For production deployment:

```bash
MODAL_ENVIRONMENT=prod modal deploy main.py
```

This creates `nighttime-story-prep-api` (without `-dev` suffix).

Use separate Modal secrets for production:

- Different API keys
- Production Supabase credentials
- More restrictive settings

## Monitoring and Debugging

### View Logs

```bash
# Development logs
modal app logs nighttime-story-prep-api-dev

# Follow live logs
modal app logs nighttime-story-prep-api-dev --follow
```

### Check Status

```bash
curl https://your-url--health-endpoint.modal.run
```

### Test Individual Endpoints

```bash
# Health check (no auth required)
curl https://your-url--health-endpoint.modal.run

# Extract content
curl -X POST https://your-url--extract-content-endpoint.modal.run \
  -H "Authorization: Bearer $MODAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- << EOF
{
  "email_data": {
    "text": "Your story content here...",
    "subject": "Test Story",
    "from": "Test Author <test@example.com>"
  },
  "storage_id": "test-$(date +%s)"
}
EOF
```

## Updating the Deployment

After making code changes:

```bash
cd modal-api
modal deploy main.py
```

Modal will:

- Rebuild the image
- Deploy the new version
- Update endpoints (URLs stay the same)

## Troubleshooting

### "Secret not found" error

Create the required secrets:

```bash
modal secret list
```

If missing, follow Step 2 above.

### "Supabase connection failed"

Check:

1. Supabase URL is correct (no trailing slash)
2. Service role key is correct (not anon key)
3. Storage bucket `story-storage` exists

### "Authentication failed"

Verify:

1. `MODAL_API_KEY` matches between Modal secret and client
2. Using `Bearer` prefix in Authorization header
3. No extra spaces in the API key

### Import errors

Ensure all files are in correct locations:

```
modal-api/
├── main.py
├── src/
│   ├── __init__.py
│   ├── supabase_storage.py
│   ├── content_extraction_agent.py
│   ├── chunker.py
│   └── email_parser.py
```

## Cost Optimization

Modal charges based on:

- Compute time (per second)
- Memory usage
- Storage (for built images)

Tips:

- Use appropriate timeout values (don't set too high)
- Consider downgrading to smaller instances if possible
- Monitor usage in Modal dashboard

## Security Checklist

- [ ] Secrets are configured in Modal (not in code)
- [ ] API key is randomly generated (32+ characters)
- [ ] Supabase service role key is kept secret
- [ ] Storage bucket is private (not public)
- [ ] Production uses separate secrets from development
- [ ] API key authentication is tested and working

## Next Steps

After successful deployment:

1. Update NextJS environment variables
2. Test the full pipeline (NextJS → Modal API → Supabase)
3. Monitor logs for errors
4. Set up alerts for failures (if using Modal Pro)
5. Document the API URLs for your team
