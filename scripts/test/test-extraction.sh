#!/bin/bash
#
# Test content extraction with example files
#
# Usage:
#   ./test-extraction.sh [--example <filename>]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/http.sh"

# Default example
EXAMPLE_FILE="pale-lights-example-1.txt"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --example)
      EXAMPLE_FILE="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

section "Content Extraction Test"

# Check required env vars
if ! check_required_env MODAL_API_URL MODAL_API_KEY; then
    error "MODAL_API_URL and MODAL_API_KEY must be set"
    exit 1
fi

# Find example file
EXAMPLE_PATH="$SCRIPT_DIR/../../examples/inputs/$EXAMPLE_FILE"

if [ ! -f "$EXAMPLE_PATH" ]; then
    error "Example file not found: $EXAMPLE_PATH"
    info "Available examples:"
    ls "$SCRIPT_DIR/../../examples/inputs/"
    exit 1
fi

info "Using example: $EXAMPLE_FILE"
log "Reading file: $EXAMPLE_PATH"
echo ""

# Read example content
STORY_CONTENT=$(cat "$EXAMPLE_PATH")
WORD_COUNT=$(echo "$STORY_CONTENT" | wc -w | tr -d ' ')

info "Story length: $WORD_COUNT words"
echo ""

# Generate test ID
STORAGE_ID="test-$(timestamp)-$(basename "$EXAMPLE_FILE" .txt)"

log "Storage ID: $STORAGE_ID"
echo ""

# Create email payload
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

# Call extraction endpoint
subsection "Calling Modal API /extract-content"

response=$(http_post_auth "$MODAL_API_URL/extract-content" "$EMAIL_DATA" "$MODAL_API_KEY" "Extract Content" 2)
http_code=$(echo "$response" | head -n1)
body=$(echo "$response" | tail -n+2)

if [ "$http_code" != "200" ]; then
    error "Extraction failed (HTTP $http_code)"
    print_json "$body"
    exit 1
fi

# Parse response
status=$(parse_json_field "$body" "status")

if [ "$status" != "success" ]; then
    error "Extraction failed: $status"
    exit 1
fi

# Get results
content_url=$(parse_json_field "$body" "content_url")
extracted_word_count=$(parse_json_nested "$body" "metadata.word_count")
extraction_method=$(parse_json_nested "$body" "metadata.extraction_method")
title=$(parse_json_nested "$body" "metadata.title")

echo ""
success "Content extracted successfully!"
echo ""

info "Results:"
echo "  Title: $title"
echo "  Extraction method: $extraction_method"
echo "  Word count: $extracted_word_count"
echo "  Content URL: $content_url"
echo "  Storage ID: $STORAGE_ID"
echo ""

section "✅ Extraction Test Passed"

info "To verify storage files:"
echo "  ./scripts/verify/check-storage.sh --story-id $STORAGE_ID"

