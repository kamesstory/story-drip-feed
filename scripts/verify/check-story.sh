#!/bin/bash
#
# Check story details by ID
#
# Usage:
#   ./check-story.sh <story-id>
#   ./check-story.sh <story-id> --verbose
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/db.sh"

# Parse arguments
STORY_ID=$1
VERBOSE=${2:-false}

if [ -z "$STORY_ID" ]; then
  error "Usage: $0 <story-id> [--verbose]"
  exit 1
fi

if [ "$2" = "--verbose" ] || [ "$2" = "-v" ]; then
  export VERBOSE=true
fi

section "Story Details - ID: $STORY_ID"

# Check if story exists
if ! story_exists "$STORY_ID"; then
  error "Story ID $STORY_ID not found"
  exit 1
fi

# Get story details
echo "Story Information:"
echo "─────────────────────────────────────────────────────────────"
get_story "$STORY_ID"
echo ""

# Get chunks
echo "Chunks:"
echo "─────────────────────────────────────────────────────────────"
chunk_count=$(count_story_chunks "$STORY_ID")

if [ "$chunk_count" -gt 0 ]; then
  get_story_chunks "$STORY_ID"
  echo ""
  info "Total chunks: $chunk_count"
else
  warning "No chunks found for this story"
fi

echo ""
success "Story check complete"

