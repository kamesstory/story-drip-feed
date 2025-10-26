#!/bin/bash
#
# Run custom SQL query on database
#
# Usage:
#   ./query-db.sh "SELECT COUNT(*) FROM stories"
#   ./query-db.sh "SELECT * FROM stories WHERE status='pending'" --formatted
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/db.sh"

# Parse arguments
SQL=$1
FORMATTED=${2:-false}

if [ -z "$SQL" ]; then
  error "Usage: $0 \"<SQL query>\" [--formatted]"
  echo ""
  echo "Examples:"
  echo "  $0 \"SELECT COUNT(*) FROM stories\""
  echo "  $0 \"SELECT * FROM stories LIMIT 5\" --formatted"
  exit 1
fi

if [ "$2" = "--formatted" ] || [ "$2" = "-f" ]; then
  FORMATTED=true
fi

section "Database Query"

info "SQL: $SQL"
echo ""

if [ "$FORMATTED" = "true" ]; then
  query_db_formatted "$SQL"
else
  query_db "$SQL"
fi

echo ""
success "Query complete"

