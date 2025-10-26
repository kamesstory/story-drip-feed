#!/bin/bash
#
# Check the latest story (most recent)
#
# Usage:
#   ./check-latest.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/db.sh"

section "Latest Story"

# Get latest story ID
latest_id=$(get_latest_story_id)

if [ -z "$latest_id" ]; then
  warning "No stories found in database"
  exit 1
fi

info "Latest story ID: $latest_id"
echo ""

# Use check-story.sh to display details
"$SCRIPT_DIR/check-story.sh" "$latest_id"

