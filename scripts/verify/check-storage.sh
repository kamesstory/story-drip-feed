#!/bin/bash
#
# Check Supabase Storage files
#
# Usage:
#   ./check-storage.sh [--story-id ID]
#   ./check-storage.sh --list-buckets
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"

# Check required env vars
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
  error "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"
  exit 1
fi

STORY_ID=""
LIST_BUCKETS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --story-id)
      STORY_ID="$2"
      shift 2
      ;;
    --list-buckets)
      LIST_BUCKETS=true
      shift
      ;;
    *)
      shift
      ;;
  esac
done

section "Supabase Storage Check"

# List buckets
if [ "$LIST_BUCKETS" = "true" ]; then
  info "Listing storage buckets..."
  echo ""
  
  curl -s -X GET "$SUPABASE_URL/storage/v1/bucket" \
    -H "apikey: $SUPABASE_SERVICE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" | print_json
  
  echo ""
  success "Bucket list complete"
  exit 0
fi

# Check files for specific story
if [ -n "$STORY_ID" ]; then
  info "Checking storage for story ID: $STORY_ID"
  echo ""
  
  # Check email data
  echo "Email Data:"
  curl -s -X POST "$SUPABASE_URL/storage/v1/object/list/epubs" \
    -H "apikey: $SUPABASE_SERVICE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"prefix\": \"email-data/\", \"limit\": 100}" | \
    grep -o "\"name\":\"[^\"]*\"" | sed 's/"name":"\([^"]*\)"/\1/' | grep -i "$STORY_ID" || echo "  (none found)"
  
  echo ""
  echo "Story Content:"
  curl -s -X POST "$SUPABASE_URL/storage/v1/object/list/epubs" \
    -H "apikey: $SUPABASE_SERVICE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"prefix\": \"story-content/\", \"limit\": 100}" | \
    grep -o "\"name\":\"[^\"]*\"" | sed 's/"name":"\([^"]*\)"/\1/' | grep -i "$STORY_ID" || echo "  (none found)"
  
  echo ""
  echo "Story Chunks:"
  curl -s -X POST "$SUPABASE_URL/storage/v1/object/list/epubs" \
    -H "apikey: $SUPABASE_SERVICE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"prefix\": \"story-chunks/\", \"limit\": 100}" | \
    grep -o "\"name\":\"[^\"]*\"" | sed 's/"name":"\([^"]*\)"/\1/' | grep -i "$STORY_ID" || echo "  (none found)"
  
  echo ""
  echo "EPUBs:"
  curl -s -X POST "$SUPABASE_URL/storage/v1/object/list/epubs" \
    -H "apikey: $SUPABASE_SERVICE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"prefix\": \"epubs/\", \"limit\": 100}" | \
    grep -o "\"name\":\"[^\"]*\"" | sed 's/"name":"\([^"]*\)"/\1/' | grep -i "$STORY_ID" || echo "  (none found)"
  
  echo ""
  success "Storage check complete"
  exit 0
fi

# Default: show general storage info
info "Use --story-id <ID> to check files for a specific story"
info "Use --list-buckets to list all storage buckets"
echo ""

# Show recent files in epubs bucket
echo "Recent files in 'epubs' bucket (last 10):"
curl -s -X POST "$SUPABASE_URL/storage/v1/object/list/epubs" \
  -H "apikey: $SUPABASE_SERVICE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "sortBy": {"column": "created_at", "order": "desc"}}' | \
  print_json

echo ""
success "Storage check complete"

