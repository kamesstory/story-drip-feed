#!/bin/bash
#
# Test health endpoints for all services
#
# Usage:
#   ./test-health.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/http.sh"

# Configuration
NEXTJS_URL="${NEXT_PUBLIC_BASE_URL:-http://localhost:3000}"
MODAL_API_URL="${MODAL_API_URL:-}"

section "Health Check Tests"

# Test 1: NextJS Health
subsection "Testing NextJS Health"

if ! is_service_running "$NEXTJS_URL"; then
    error "NextJS is not running at $NEXTJS_URL"
    info "Start it with: cd nextjs-app && npm run dev"
    exit 1
fi

if check_endpoint_health "$NEXTJS_URL/api/health" "NextJS"; then
    success "NextJS is healthy"
else
    error "NextJS health check failed"
    exit 1
fi

# Test 2: Modal API Health (if configured)
if [ -n "$MODAL_API_URL" ]; then
    echo ""
    subsection "Testing Modal API Health"
    
    if check_endpoint_health "$MODAL_API_URL/health" "Modal API"; then
        success "Modal API is healthy"
    else
        warning "Modal API health check failed (this is optional)"
    fi
else
    echo ""
    info "MODAL_API_URL not set, skipping Modal API health check"
fi

echo ""
section "✅ All Health Checks Passed"

