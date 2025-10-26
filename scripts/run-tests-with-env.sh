#!/bin/bash
#
# Helper script to load environment and run tests
#
# Usage:
#   ./scripts/run-tests-with-env.sh [test-name]
#   ./scripts/run-tests-with-env.sh health
#   ./scripts/run-tests-with-env.sh all --quick
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load environment from nextjs-app/.env.local
ENV_FILE="$SCRIPT_DIR/../nextjs-app/.env.local"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE not found"
    echo ""
    echo "Create it from the example:"
    echo "  cp nextjs-app/env.example nextjs-app/.env.local"
    exit 1
fi

echo "📦 Loading environment from nextjs-app/.env.local..."
set -a  # Export all variables
source "$ENV_FILE"
set +a

# Also set DATABASE_URL from Supabase URL if not set
if [ -z "$DATABASE_URL" ] && [ -n "$NEXT_PUBLIC_SUPABASE_URL" ]; then
    # Extract project ref from Supabase URL
    # Format: https://xxx.supabase.co -> postgresql://postgres:pass@db.xxx.supabase.co:5432/postgres
    echo "⚠️  DATABASE_URL not set, you'll need to set it manually for database tests"
fi

echo "✅ Environment loaded"
echo ""

# Show what's available
echo "Available services:"
[ -n "$MODAL_API_URL" ] && echo "  ✅ MODAL_API_URL: $MODAL_API_URL" || echo "  ❌ MODAL_API_URL not set"
[ -n "$MODAL_API_KEY" ] && echo "  ✅ MODAL_API_KEY: Set (hidden)" || echo "  ❌ MODAL_API_KEY not set"
[ -n "$DATABASE_URL" ] && echo "  ✅ DATABASE_URL: Set (hidden)" || echo "  ❌ DATABASE_URL not set"
echo ""

# Run the requested test
if [ $# -eq 0 ]; then
    echo "Usage: $0 [test-name] [args]"
    echo ""
    echo "Examples:"
    echo "  $0 health"
    echo "  $0 modal-api"
    echo "  $0 extraction --example dragons-example-1.txt"
    echo "  $0 all --quick"
    echo ""
    exit 0
fi

TEST_NAME=$1
shift  # Remove first arg, keep the rest

TEST_SCRIPT="$SCRIPT_DIR/test/test-${TEST_NAME}.sh"

if [ ! -f "$TEST_SCRIPT" ]; then
    echo "❌ Test not found: $TEST_SCRIPT"
    echo ""
    echo "Available tests:"
    ls -1 "$SCRIPT_DIR/test/"*.sh | xargs -n1 basename | sed 's/test-/  • /' | sed 's/.sh//'
    exit 1
fi

echo "🧪 Running test: $TEST_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run the test with any additional args
"$TEST_SCRIPT" "$@"

