#!/bin/bash
#
# Demo script showcasing the testing infrastructure
#
# This script demonstrates how to use the various testing and verification tools
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

section "Testing Infrastructure Demo"

info "This demo showcases the testing and verification tools"
echo ""

# Step 1: Show available tests
subsection "Step 1: Available Test Scripts"
echo ""
echo "Health & Component Tests:"
echo "  ./scripts/test/test-health.sh           - Check service health"
echo "  ./scripts/test/test-database.sh         - Test database operations"
echo "  ./scripts/test/test-storage.sh          - Test storage operations"
echo "  ./scripts/test/test-modal-api.sh        - Test Modal API endpoints"
echo ""
echo "Feature Tests:"
echo "  ./scripts/test/test-extraction.sh       - Test content extraction"
echo "  ./scripts/test/test-chunking.sh         - Test story chunking"
echo ""
echo "E2E Tests:"
echo "  ./scripts/test/test-email-webhook.sh    - Test email webhook"
echo "  ./scripts/test/test-ingest-e2e.sh       - Test full pipeline"
echo ""
echo "Master Runner:"
echo "  ./scripts/test/test-all.sh              - Run all tests"
echo "  ./scripts/test/test-all.sh --quick      - Skip E2E tests"
echo "  ./scripts/test/test-all.sh --component  - Only component tests"
echo ""

read -p "Press Enter to continue..."

# Step 2: Show verification tools
subsection "Step 2: Verification Tools (Autonomous Inspection)"
echo ""
echo "Story Inspection:"
echo "  ./scripts/verify/check-story.sh <id>    - Check specific story"
echo "  ./scripts/verify/check-latest.sh        - Check latest story"
echo "  ./scripts/verify/check-chunks.sh <id>   - Check story chunks"
echo ""
echo "Listing & Queries:"
echo "  ./scripts/verify/list-stories.sh        - List recent stories"
echo "  ./scripts/verify/list-stories.sh --test-only"
echo "  ./scripts/verify/query-db.sh \"<SQL>\"    - Run custom query"
echo ""
echo "Storage:"
echo "  ./scripts/verify/check-storage.sh       - Check storage files"
echo "  ./scripts/verify/check-storage.sh --story-id <id>"
echo ""

read -p "Press Enter to continue..."

# Step 3: Show example workflows
subsection "Step 3: Example Workflows"
echo ""
echo "Workflow 1: Test with example data"
echo "  $ ./scripts/test/test-extraction.sh --example pale-lights-example-1.txt"
echo "  $ ./scripts/verify/check-latest.sh"
echo ""
echo "Workflow 2: Debug a failing story"
echo "  $ ./scripts/verify/list-stories.sh --limit 20"
echo "  $ ./scripts/verify/check-story.sh 42"
echo "  $ ./scripts/verify/check-storage.sh --story-id 42"
echo ""
echo "Workflow 3: Run full test suite"
echo "  $ ./scripts/test/test-all.sh --verbose"
echo ""

read -p "Press Enter to continue..."

# Step 4: Show library functions
subsection "Step 4: Shared Libraries (for custom scripts)"
echo ""
echo "common.sh - Logging & Utilities:"
echo "  log \"message\"       - Timestamped log"
echo "  success \"message\"   - Green success message"
echo "  error \"message\"     - Red error message"
echo "  section \"title\"     - Section header"
echo "  print_json \"\$data\"  - Format JSON prettily"
echo ""
echo "http.sh - HTTP Helpers:"
echo "  http_get \"<url>\" \"description\""
echo "  http_post \"<url>\" \"\$data\" \"description\""
echo "  http_post_auth \"<url>\" \"\$data\" \"\$token\""
echo "  parse_json_field \"\$json\" \"field\""
echo ""
echo "db.sh - Database Queries:"
echo "  query_db \"SELECT ...\""
echo "  get_story <id>"
echo "  verify_story_status <id> \"expected\""
echo "  wait_for_story_status <id> \"status\" <timeout>"
echo ""

read -p "Press Enter to continue..."

# Step 5: Show how to check environment
subsection "Step 5: Environment Check"
echo ""

if [ -n "$NEXT_PUBLIC_BASE_URL" ]; then
    success "NEXT_PUBLIC_BASE_URL is set: $NEXT_PUBLIC_BASE_URL"
else
    warning "NEXT_PUBLIC_BASE_URL not set (needed for NextJS tests)"
fi

if [ -n "$DATABASE_URL" ]; then
    success "DATABASE_URL is set"
else
    warning "DATABASE_URL not set (needed for database tests)"
fi

if [ -n "$MODAL_API_URL" ]; then
    success "MODAL_API_URL is set: $MODAL_API_URL"
else
    info "MODAL_API_URL not set (optional for Modal tests)"
fi

if [ -n "$MODAL_API_KEY" ]; then
    success "MODAL_API_KEY is set"
else
    info "MODAL_API_KEY not set (optional for Modal tests)"
fi

echo ""

read -p "Press Enter to continue..."

# Step 6: Show quick test
subsection "Step 6: Quick Test (if services are running)"
echo ""

if [ -n "$NEXT_PUBLIC_BASE_URL" ]; then
    log "Testing NextJS health..."
    if curl -sf "$NEXT_PUBLIC_BASE_URL/api/health" > /dev/null 2>&1; then
        success "NextJS is responding!"
    else
        warning "NextJS is not responding (is it running?)"
        info "Start with: cd nextjs-app && npm run dev"
    fi
else
    info "Skipping health check (NEXT_PUBLIC_BASE_URL not set)"
fi

echo ""

section "Demo Complete!"

info "Next steps:"
echo "  1. Read full documentation: ./scripts/TEST_README.md"
echo "  2. Check implementation summary: ./TESTING_IMPLEMENTATION_SUMMARY.md"
echo "  3. Try a test: ./scripts/test/test-health.sh"
echo "  4. Run all tests: ./scripts/test/test-all.sh --quick"
echo ""

success "Testing infrastructure is ready to use!"

