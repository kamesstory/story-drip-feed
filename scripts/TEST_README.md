# Testing Infrastructure

Comprehensive bash-based testing and verification framework for the Nighttime Story Prep system.

## Overview

This testing framework enables:

- **E2E and component-level testing** - Test the full pipeline or individual parts
- **Real endpoint testing** - Test against live services (NextJS, Modal API, Supabase)
- **Example data testing** - Use story examples from `examples/inputs/`
- **Autonomous verification** - Query database and storage directly without manual dashboard checks

## Architecture

```
scripts/
├── lib/                        # Shared utilities
│   ├── common.sh              # Colors, logging, timestamps
│   ├── http.sh                # HTTP request helpers
│   └── db.sh                  # Database query helpers (Supabase)
├── test/                       # Test runners
│   ├── test-health.sh         # Health checks
│   ├── test-database.sh       # Database operations
│   ├── test-storage.sh        # Storage operations
│   ├── test-email-webhook.sh  # Email webhook
│   ├── test-modal-api.sh      # Modal API endpoints
│   ├── test-extraction.sh     # Content extraction
│   ├── test-chunking.sh       # Story chunking
│   ├── test-ingest-e2e.sh     # Full E2E pipeline
│   └── test-all.sh            # Master test orchestrator
└── verify/                     # Verification/inspection tools
    ├── check-story.sh         # Check story details by ID
    ├── check-chunks.sh        # Check chunks for a story
    ├── check-storage.sh       # Check Supabase Storage files
    ├── query-db.sh            # Run custom SQL queries
    ├── list-stories.sh        # List recent stories
    └── check-latest.sh        # Check the latest story
```

## Quick Start

### Prerequisites

Set up environment variables:

```bash
# NextJS (local dev)
export NEXT_PUBLIC_BASE_URL=http://localhost:3000

# Supabase (required for database tests)
export DATABASE_URL="postgresql://..."
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_KEY="your-service-key"

# Modal API (optional, for Modal tests)
export MODAL_API_URL="https://your-app.modal.run"
export MODAL_API_KEY="your-api-key"
```

### Running Tests

```bash
# Run all tests
./scripts/test/test-all.sh

# Run only quick tests (skip E2E)
./scripts/test/test-all.sh --quick

# Run only component tests
./scripts/test/test-all.sh --component

# Run with verbose output
./scripts/test/test-all.sh --verbose

# Run individual tests
./scripts/test/test-health.sh
./scripts/test/test-modal-api.sh
./scripts/test/test-extraction.sh --example pale-lights-example-1.txt
```

## Test Categories

### Health Tests

Check if services are running:

```bash
./scripts/test/test-health.sh
```

Checks:

- NextJS API health endpoint
- Modal API health endpoint (if configured)

### Component Tests

Test individual components:

```bash
# Test Modal API endpoints
./scripts/test/test-modal-api.sh

# Test extraction with example file
./scripts/test/test-extraction.sh --example dragons-example-1.txt

# Test chunking with custom target
./scripts/test/test-chunking.sh --example pale-lights-example-1.txt --target-words 8000

# Test database operations
./scripts/test/test-database.sh

# Test storage operations
./scripts/test/test-storage.sh
```

### E2E Tests

Test the full pipeline:

```bash
# Test email webhook
./scripts/test/test-email-webhook.sh

# Test full ingestion pipeline
./scripts/test/test-ingest-e2e.sh --example wandering-inn-example-1.txt --wait
```

## Verification Tools

Autonomous verification tools to inspect system state:

### Check Story Details

```bash
# Check specific story
./scripts/verify/check-story.sh 42

# Check latest story
./scripts/verify/check-latest.sh

# Check chunks for a story
./scripts/verify/check-chunks.sh 42
```

### List Stories

```bash
# List recent stories (default: 10)
./scripts/verify/list-stories.sh

# List more stories
./scripts/verify/list-stories.sh --limit 50

# List only test stories
./scripts/verify/list-stories.sh --test-only
```

### Query Database

```bash
# Run custom SQL
./scripts/verify/query-db.sh "SELECT COUNT(*) FROM stories"

# Formatted output
./scripts/verify/query-db.sh "SELECT * FROM stories LIMIT 5" --formatted

# Check story status counts
./scripts/verify/query-db.sh "SELECT status, COUNT(*) FROM stories GROUP BY status" --formatted
```

### Check Storage

```bash
# List storage buckets
./scripts/verify/check-storage.sh --list-buckets

# Check files for specific story
./scripts/verify/check-storage.sh --story-id test-1234567890
```

## Shared Libraries

All test scripts use shared libraries for consistency:

### common.sh

Provides:

- **Logging**: `log()`, `success()`, `error()`, `warning()`, `info()`, `debug()`
- **Formatting**: `section()`, `subsection()`, `print_json()`
- **Utilities**: `timestamp()`, `generate_test_id()`, `wait_for_service()`
- **Environment**: `check_env_var()`, `check_required_env()`, `load_env_file()`

### http.sh

Provides:

- **Requests**: `http_get()`, `http_post()`, `http_post_auth()`
- **Parsing**: `parse_json_field()`, `parse_json_nested()`, `json_has_field()`
- **Health**: `check_endpoint_health()`

### db.sh

Provides:

- **Queries**: `query_db()`, `query_db_formatted()`
- **Story ops**: `get_story()`, `get_story_status()`, `story_exists()`
- **Chunk ops**: `get_story_chunks()`, `count_story_chunks()`
- **Verification**: `verify_story_exists()`, `verify_story_status()`, `verify_chunks_created()`
- **Waiting**: `wait_for_story_status()`

## Test Data

All test data uses the `test-` prefix:

```bash
email_id: "test-1234567890-pale-lights"
storage_id: "test-1234567890-dragons"
subject: "[TEST] Pale Lights - Chapter 27"
```

This makes it easy to:

- Identify test data in the database
- Clean up test data after testing
- Avoid mixing test and production data

### Cleanup Test Data

```bash
# Delete all test stories (be careful!)
./scripts/verify/query-db.sh "DELETE FROM stories WHERE email_id LIKE 'test-%'"

# Or use the verification tools to list and manually delete
./scripts/verify/list-stories.sh --test-only
```

## Example Workflows

### Test a new Modal deployment

```bash
# 1. Set Modal API URL
export MODAL_API_URL="https://your-new-deployment.modal.run"

# 2. Test health
./scripts/test/test-health.sh

# 3. Test endpoints
./scripts/test/test-modal-api.sh

# 4. Test with real example
./scripts/test/test-extraction.sh --example pale-lights-example-1.txt
```

### Debug a failing story

```bash
# 1. List recent stories
./scripts/verify/list-stories.sh --limit 20

# 2. Check specific story
./scripts/verify/check-story.sh 42

# 3. Check storage files
./scripts/verify/check-storage.sh --story-id 42

# 4. Check chunks
./scripts/verify/check-chunks.sh 42

# 5. Run custom query
./scripts/verify/query-db.sh "SELECT status, error_message FROM stories WHERE id = 42" --formatted
```

### Test full pipeline with example

```bash
# 1. Run E2E test with specific example
./scripts/test/test-ingest-e2e.sh --example wandering-inn-example-1.txt --wait

# 2. Verify results
./scripts/verify/check-latest.sh

# 3. Check storage
./scripts/verify/check-storage.sh --story-id $(./scripts/verify/query-db.sh "SELECT id FROM stories ORDER BY received_at DESC LIMIT 1")
```

## Troubleshooting

### Database connection issues

```bash
# Check DATABASE_URL is set
echo $DATABASE_URL

# Test connection
psql "$DATABASE_URL" -c "SELECT 1"

# Or use Supabase CLI
supabase db query "SELECT 1"
```

### Modal API issues

```bash
# Check env vars
echo $MODAL_API_URL
echo $MODAL_API_KEY

# Test health manually
curl -s "$MODAL_API_URL/health" | jq .
```

### Test failures

Run with verbose mode:

```bash
./scripts/test/test-all.sh --verbose
```

Or run individual test with verbose:

```bash
VERBOSE=true ./scripts/test/test-extraction.sh
```

## Best Practices

1. **Use verification tools** - Always verify test results using `check-story.sh`, `check-chunks.sh`, etc.

2. **Clean test data** - Periodically clean up test stories to keep database tidy

3. **Test with real examples** - Use the example files in `examples/inputs/` to test with realistic data

4. **Check logs** - When tests fail, check NextJS logs, Modal logs, or Supabase logs for details

5. **Autonomous verification** - These tools enable complete testing without manual dashboard checks

## Adding New Tests

To add a new test:

1. Create test script in `scripts/test/`
2. Source the shared libraries
3. Use consistent formatting (section, subsection, success, error)
4. Add to `test-all.sh` if appropriate

Example template:

```bash
#!/bin/bash
#
# Test description
#
# Usage:
#   ./test-my-feature.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/http.sh"
source "$SCRIPT_DIR/../lib/db.sh"

section "My Feature Test"

# Your test logic here

section "✅ Test Passed"
```

## Contributing

When modifying tests:

- Keep shared utilities in `lib/`
- Keep tests DRY by using library functions
- Add clear success/error messages
- Document new verification tools in this README
