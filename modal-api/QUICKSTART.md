# Modal API Quick Start

## TL;DR

```bash
# 1. Setup
pip install modal
modal setup

# 2. Configure secrets (one time)
modal secret create story-prep-secrets \
  ANTHROPIC_API_KEY=<your-key> \
  MODAL_API_KEY=$(openssl rand -hex 32)

modal secret create supabase-secrets \
  SUPABASE_URL=<url> \
  SUPABASE_SERVICE_ROLE_KEY=<key>

# 3. Deploy
cd modal-api
modal deploy main.py

# 4. Test
export MODAL_API_URL="<url-from-deploy-output>"
export MODAL_API_KEY="<key-from-step-2>"
cd ..
./scripts/test/test-modal-api.sh
```

## Common Commands

```bash
# Deploy/Update
cd modal-api && modal deploy main.py

# View logs
modal app logs nighttime-story-prep-api-dev

# Follow live logs
modal app logs nighttime-story-prep-api-dev --follow

# List apps
modal app list

# Check secrets
modal secret list
```

## API Usage

### Extract Content

```bash
curl -X POST $MODAL_API_URL--extract-content-endpoint \
  -H "Authorization: Bearer $MODAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email_data": {
      "text": "Story content...",
      "subject": "Title",
      "from": "author@example.com"
    },
    "storage_id": "unique-123"
  }'
```

### Chunk Story

```bash
curl -X POST $MODAL_API_URL--chunk-story-endpoint \
  -H "Authorization: Bearer $MODAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content_url": "story-content/unique-123/content.txt",
    "storage_id": "unique-123",
    "target_words": 5000
  }'
```

### Health Check

```bash
curl $MODAL_API_URL--health-endpoint
```

## Troubleshooting

**"Secret not found"**

```bash
modal secret list
# If missing, create it (see step 2 above)
```

**"Supabase connection failed"**

- Check bucket exists: `story-storage`
- Verify URL has no trailing slash
- Confirm service role key (not anon key)

**"401 Unauthorized"**

- Verify API key matches
- Check `Bearer` prefix in header
- No extra spaces in key

**View detailed logs**

```bash
modal app logs nighttime-story-prep-api-dev --follow
```

## File Locations

```
modal-api/
├── main.py           # Start here
├── src/              # Source modules
├── README.md         # Full docs
├── DEPLOYMENT.md     # Detailed deployment
└── requirements.txt  # Dependencies
```

## Need Help?

1. Check `README.md` for API details
2. Check `DEPLOYMENT.md` for deployment steps
3. Check `TASK3_SUMMARY.md` for architecture
4. View logs: `modal app logs <app-name> --follow`
