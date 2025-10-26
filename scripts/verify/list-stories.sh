#!/bin/bash
#
# List recent stories
#
# Usage:
#   ./list-stories.sh [--limit N] [--test-only]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/db.sh"

# Default limit
LIMIT=10
TEST_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --test-only)
      TEST_ONLY=true
      shift
      ;;
    *)
      shift
      ;;
  esac
done

section "Recent Stories (limit: $LIMIT)"

if [ "$TEST_ONLY" = "true" ]; then
  info "Showing test stories only (email_id LIKE 'test-%')"
  echo ""
  list_test_stories "$LIMIT"
else
  list_recent_stories "$LIMIT"
fi

echo ""
success "Story list complete"

