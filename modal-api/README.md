# Modal API - Story Processing Service

Stateless HTTP API service for AI-powered content extraction and story chunking. Uses Supabase Storage for all file operations.

## Architecture

- **Stateless**: No database access; all data stored in Supabase
- **Storage**: Uses Supabase Storage buckets for content and chunks
- **AI/Agent Operations**: Content extraction and intelligent chunking
- **Authentication**: Bearer token authentication

## Endpoints

### POST `/extract-content`

Extract story content from email data and save to Supabase Storage.

**Request:**

```json
{
  "email_data": {
    "text": "Email text content...",
    "html": "Email HTML content...",
    "subject": "Chapter 27 - Story Title",
    "from": "Author Name <author@example.com>"
  },
  "storage_id": "unique-id-123"
}
```

**Response:**

```json
{
  "status": "success",
  "content_url": "story-content/unique-id-123/content.txt",
  "metadata": {
    "title": "Chapter 27 - Story Title",
    "author": "Author Name",
    "extraction_method": "agent",
    "word_count": 12500
  }
}
```

### POST `/chunk-story`

Chunk story content into reading-sized segments.

**Request:**

```json
{
  "content_url": "story-content/unique-id-123/content.txt",
  "storage_id": "unique-id-123",
  "target_words": 5000,
  "strategy": "agent"
}
```

**Strategies:**

- `agent` - Claude Agent SDK (default, most intelligent)
- `llm` - Claude API (fallback to simple)
- `simple` - Paragraph-based chunking

**Response:**

```json
{
  "status": "success",
  "chunks": [
    {
      "chunk_number": 1,
      "url": "story-chunks/unique-id-123/chunk_001.txt",
      "word_count": 4998
    },
    {
      "chunk_number": 2,
      "url": "story-chunks/unique-id-123/chunk_002.txt",
      "word_count": 5103
    }
  ],
  "total_chunks": 2,
  "total_words": 10101,
  "chunking_strategy": "AgentChunker"
}
```

### GET `/health`

Health check endpoint to verify service status.

**Response:**

```json
{
  "status": "healthy",
  "services": {
    "anthropic_api": "ok",
    "supabase_storage": "ok"
  }
}
```

## Setup

### 1. Install Modal CLI

```bash
pip install modal
modal setup
```

### 2. Configure Secrets

Create Modal secrets with required credentials:

**story-prep-secrets:**

```bash
modal secret create story-prep-secrets \
  ANTHROPIC_API_KEY=<your-key> \
  MODAL_API_KEY=<generate-secure-key> \
  USE_AGENT_EXTRACTION=true \
  USE_AGENT_CHUNKER=true
```

**supabase-secrets:**

```bash
modal secret create supabase-secrets \
  SUPABASE_URL=<your-supabase-url> \
  SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
```

### 3. Create Supabase Storage Bucket

In your Supabase project, create a storage bucket:

- Bucket name: `story-storage`
- Public: No (use service role key for access)

### 4. Deploy

**Development:**

```bash
cd modal-api
modal deploy main.py
```

**Production:**

```bash
MODAL_ENVIRONMENT=prod modal deploy main.py
```

This creates:

- Dev: `nighttime-story-prep-api-dev`
- Prod: `nighttime-story-prep-api`

### 5. Get API URL

After deployment, Modal will display the webhook URLs:

```
✓ Created web function extract-content-endpoint => https://[app-id]--extract-content-endpoint.modal.run
✓ Created web function chunk-story-endpoint => https://[app-id]--chunk-story-endpoint.modal.run
✓ Created web function health-endpoint => https://[app-id]--health-endpoint.modal.run
```

Add the base URL to your NextJS environment:

```env
MODAL_API_URL=https://[app-id].modal.run
MODAL_API_KEY=<same-key-from-secrets>
```

## Testing

Run the test script to verify all endpoints:

```bash
../scripts/test/test-modal-api.sh
```

Or test manually with curl:

```bash
# Health check
curl https://[app-id]--health-endpoint.modal.run

# Extract content
curl -X POST https://[app-id]--extract-content-endpoint.modal.run \
  -H "Authorization: Bearer <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "email_data": {
      "text": "Story content...",
      "subject": "Test Story",
      "from": "Test Author <test@example.com>"
    },
    "storage_id": "test-123"
  }'
```

## Storage Structure

Files are organized in Supabase Storage:

```
story-storage/
├── story-content/
│   └── {storage_id}/
│       ├── content.txt
│       └── original_email.txt
├── story-chunks/
│   └── {storage_id}/
│       ├── chunk_001.txt
│       ├── chunk_002.txt
│       └── ...
└── story-metadata/
    └── {storage_id}/
        └── metadata.json
```

## Development

### Local Testing

```bash
modal run main.py
```

### View Logs

```bash
modal app logs nighttime-story-prep-api-dev
```

### Update Deployment

After making changes:

```bash
modal deploy main.py
```

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200` - Success
- `400` - Bad Request (missing parameters)
- `401` - Unauthorized (invalid/missing API key)
- `422` - Unprocessable Entity (extraction/chunking failed)
- `500` - Internal Server Error
- `503` - Service Unavailable (health check failed)

## Environment Variables

- `MODAL_ENVIRONMENT` - Set to `prod` for production deployment
- `USE_AGENT_EXTRACTION` - Enable/disable agent-based extraction (default: true)
- `USE_AGENT_CHUNKER` - Enable/disable agent-based chunking (default: true)

## Security

- API key authentication required for all POST endpoints
- Service role key for Supabase (keep secret)
- No database access (stateless design)
- All file operations through Supabase Storage

## Dependencies

See `requirements.txt` for Python dependencies. Main libraries:

- `modal` - Modal platform SDK
- `anthropic` - Claude API
- `claude-agent-sdk` - Agent capabilities
- `supabase` - Supabase client
- `beautifulsoup4`, `lxml` - HTML parsing
- `requests` - HTTP client
