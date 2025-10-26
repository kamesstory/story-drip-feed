#!/bin/bash
#
# Check chunks for a story
#
# Usage:
#   ./check-chunks.sh <story-id>
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/db.sh"

# Parse arguments
STORY_ID=$1

if [ -z "$STORY_ID" ]; then
  error "Usage: $0 <story-id>"
  exit 1
fi

section "Chunks for Story ID: $STORY_ID"

# Check if story exists
if ! story_exists "$STORY_ID"; then
  error "Story ID $STORY_ID not found"
  exit 1
fi

# Get story title
story_title=$(get_story_title "$STORY_ID")
info "Story: $story_title"
echo ""

# Get chunks
chunk_count=$(count_story_chunks "$STORY_ID")

if [ "$chunk_count" -gt 0 ]; then
  get_story_chunks "$STORY_ID"
  echo ""
  success "$chunk_count chunk(s) found"
else
  warning "No chunks found for this story"
  exit 1
fi

