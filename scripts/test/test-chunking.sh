#!/bin/bash
#
# Test chunking with example files
#
# Usage:
#   ./test-chunking.sh [--example <filename>] [--target-words N]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/http.sh"

# Defaults
EXAMPLE_FILE="pale-lights-example-1.txt"
TARGET_WORDS=5000

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --example)
      EXAMPLE_FILE="$2"
      shift 2
      ;;
    --target-words)
      TARGET_WORDS="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

section "Chunking Test"

# Check required env vars
if ! check_required_env MODAL_API_URL MODAL_API_KEY; then
    error "MODAL_API_URL and MODAL_API_KEY must be set"
    exit 1
fi

info "This test requires content to be already extracted"
info "Run test-extraction.sh first if you haven't already"
echo ""

# Find example file
EXAMPLE_PATH="$SCRIPT_DIR/../../examples/inputs/$EXAMPLE_FILE"

if [ ! -f "$EXAMPLE_PATH" ]; then
    error "Example file not found: $EXAMPLE_PATH"
    exit 1
fi

info "Using example: $EXAMPLE_FILE"
info "Target words per chunk: $TARGET_WORDS"
echo ""

# Generate test ID (same as extraction would use)
STORAGE_ID="test-$(timestamp)-$(basename "$EXAMPLE_FILE" .txt)"

log "Storage ID: $STORAGE_ID"
echo ""

# First, extract content
subsection "Step 1: Extract content"

STORY_CONTENT=$(cat "$EXAMPLE_PATH")

EMAIL_DATA=$(cat <<EOF
{
  "email_data": {
    "email_id": "$STORAGE_ID",
    "from": "test@example.com",
    "subject": "Test: $EXAMPLE_FILE",
    "text": $(echo "$STORY_CONTENT" | jq -Rs .),
    "html": ""
  },
  "storage_id": "$STORAGE_ID"
}
EOF
)

response=$(http_post_auth "$MODAL_API_URL/extract-content" "$EMAIL_DATA" "$MODAL_API_KEY" "Extract Content" 2)
http_code=$(echo "$response" | head -n1)
body=$(echo "$response" | tail -n+2)

if [ "$http_code" != "200" ]; then
    error "Extraction failed (HTTP $http_code)"
    exit 1
fi

content_url=$(parse_json_field "$body" "content_url")
success "Content extracted: $content_url"
echo ""

# Now chunk the content
subsection "Step 2: Chunk content"

CHUNK_DATA="{
  \"content_url\": \"$content_url\",
  \"storage_id\": \"$STORAGE_ID\",
  \"target_words\": $TARGET_WORDS
}"

response=$(http_post_auth "$MODAL_API_URL/chunk-story" "$CHUNK_DATA" "$MODAL_API_KEY" "Chunk Story" 2)
http_code=$(echo "$response" | head -n1)
body=$(echo "$response" | tail -n+2)

if [ "$http_code" != "200" ]; then
    error "Chunking failed (HTTP $http_code)"
    print_json "$body"
    exit 1
fi

# Parse response
status=$(parse_json_field "$body" "status")

if [ "$status" != "success" ]; then
    error "Chunking failed: $status"
    exit 1
fi

# Get results
total_chunks=$(parse_json_field "$body" "total_chunks")
total_words=$(parse_json_field "$body" "total_words")
strategy=$(parse_json_field "$body" "chunking_strategy")

echo ""
success "Story chunked successfully!"
echo ""

info "Results:"
echo "  Total chunks: $total_chunks"
echo "  Total words: $total_words"
echo "  Chunking strategy: $strategy"
echo "  Target words: $TARGET_WORDS"
echo "  Storage ID: $STORAGE_ID"
echo ""

# Show chunk details
if command -v jq &> /dev/null; then
    info "Chunk details:"
    echo "$body" | jq -r '.chunks[] | "  Chunk \(.chunk_number): \(.word_count) words - \(.url)"'
    echo ""
fi

section "✅ Chunking Test Passed"

info "To verify storage files:"
echo "  ./scripts/verify/check-storage.sh --story-id $STORAGE_ID"

