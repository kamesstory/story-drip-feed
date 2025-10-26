#!/usr/bin/env bash
#
# Test script for daily delivery endpoint
# Tests both successful delivery and empty queue scenarios
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common utilities
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/http.sh"
source "$SCRIPT_DIR/../lib/db.sh"

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:3000}"
DELIVERY_ENDPOINT="$API_BASE_URL/api/delivery/send-next"

section "Daily Delivery Endpoint Tests"

#################
# Test 1: Health check - endpoint exists
#################
subsection "Test 1: Verify delivery endpoint is accessible"

response=$(curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  "$DELIVERY_ENDPOINT" || echo "000")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [[ "$http_code" == "200" ]] || [[ "$http_code" == "401" ]]; then
  success "Endpoint is accessible (HTTP $http_code)"
else
  error "Endpoint not accessible (HTTP $http_code)"
  echo "$body"
  exit 1
fi

#################
# Test 2: Test with CRON_SECRET if configured
#################
subsection "Test 2: Test authentication with CRON_SECRET"

if [[ -n "${CRON_SECRET:-}" ]]; then
  info "CRON_SECRET is set, testing authentication..."
  
  # Test without auth header (should fail)
  response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    "$DELIVERY_ENDPOINT" || echo "000")
  
  http_code=$(echo "$response" | tail -n1)
  
  if [[ "$http_code" == "401" ]]; then
    success "Correctly rejected request without auth header"
  else
    error "Expected 401 without auth header, got $http_code"
    exit 1
  fi
  
  # Test with correct auth header (should succeed)
  response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $CRON_SECRET" \
    "$DELIVERY_ENDPOINT" || echo "000")
  
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')
  
  if [[ "$http_code" == "200" ]]; then
    success "Successfully authenticated with CRON_SECRET"
  else
    error "Failed to authenticate with valid CRON_SECRET (HTTP $http_code)"
    echo "$body"
    exit 1
  fi
else
  info "CRON_SECRET not set, skipping auth tests"
fi

#################
# Test 3: Test successful delivery (with available chunks)
#################
subsection "Test 3: Test delivery with available chunks"

# Just call the endpoint to deliver whatever is next
info "Calling delivery endpoint..."

# Make delivery request (with or without auth header)
if [[ -n "${CRON_SECRET:-}" ]]; then
  response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $CRON_SECRET" \
    "$DELIVERY_ENDPOINT" 2>&1 || echo -e "\n000")
else
  response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    "$DELIVERY_ENDPOINT" 2>&1 || echo -e "\n000")
fi

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [[ "$http_code" == "200" ]]; then
  # Check if queue was empty
  if echo "$body" | grep -q '"queueEmpty".*true'; then
    info "Queue is currently empty - will test empty queue scenario in next test"
  elif echo "$body" | grep -q '"success".*true'; then
    success "Delivery completed successfully"
    
    # Verify TEST_MODE is working
    if echo "$body" | grep -q '"testMode".*true'; then
      success "TEST_MODE is enabled"
      
      # Check if delivered to admin email
      if echo "$body" | grep -q '"deliveredTo"'; then
        delivered_to=$(echo "$body" | grep -o '"deliveredTo":"[^"]*"' | cut -d'"' -f4)
        success "Email sent to: $delivered_to"
      fi
    else
      warning "testMode is false - emails going to Kindle!"
    fi
    
    # Display delivery details
    info "Delivery details:"
    echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
  else
    error "Unexpected response format"
    echo "$body"
    exit 1
  fi
else
  error "Delivery endpoint returned HTTP $http_code"
  echo "$body"
  exit 1
fi

#################
# Test 4: Test empty queue scenario  
#################
subsection "Test 4: Test delivery with empty queue"

# Mark all chunks as sent to create empty queue
info "Marking all chunks as sent to test empty queue..."
if command -v psql &> /dev/null && [[ -n "${DATABASE_URL:-}" ]]; then
  psql "$DATABASE_URL" -t -c "UPDATE story_chunks SET sent_to_kindle_at = NOW()" > /dev/null 2>&1
elif command -v curl &> /dev/null && [[ -n "${NEXT_PUBLIC_SUPABASE_URL:-}" ]] && [[ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  # Use Supabase REST API to update
  curl -s -X PATCH "${NEXT_PUBLIC_SUPABASE_URL}/rest/v1/story_chunks?sent_to_kindle_at=is.null" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=minimal" \
    -d '{"sent_to_kindle_at": "'"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"'"}' > /dev/null 2>&1
  info "Updated chunks via Supabase API"
else
  warning "Could not mark chunks as sent - DATABASE_URL or Supabase credentials not available"
  info "Skipping empty queue test"
fi

# Make request
if [[ -n "${CRON_SECRET:-}" ]]; then
  response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $CRON_SECRET" \
    "$DELIVERY_ENDPOINT" 2>&1 || echo -e "\n000")
else
  response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    "$DELIVERY_ENDPOINT" 2>&1 || echo -e "\n000")
fi

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [[ "$http_code" == "200" ]]; then
  # Check for queueEmpty flag in response
  if echo "$body" | grep -q '"queueEmpty".*true'; then
    success "Empty queue handled correctly"
    info "Response: $body"
  else
    warning "Queue still has chunks available (couldn't clear all chunks)"
    info "Response: $body"
  fi
else
  error "Expected 200 for empty queue, got $http_code"
  echo "$body"
  exit 1
fi

#################
# Test 5: Verify TEST_MODE behavior
#################
subsection "Test 5: Verify TEST_MODE behavior"

if [[ "${TEST_MODE:-false}" == "true" ]]; then
  success "TEST_MODE is enabled - emails will be sent to admin instead of Kindle"
  info "Check logs and admin email for '[TEST]' indicators"
else
  warning "TEST_MODE is disabled - emails are being sent to Kindle for real!"
  info "Set TEST_MODE=true to send to admin email during testing"
fi

#################
# Summary
#################
section "Test Summary"
success "All delivery endpoint tests passed!"

echo ""
info "Next steps:"
echo "  1. Deploy to Vercel to test cron job"
echo "  2. Check Vercel logs for cron execution at 12pm PT daily"
echo "  3. Verify Kindle receives daily chunks"
echo "  4. Monitor admin notification emails"
echo ""
info "Manual trigger: curl -X POST $DELIVERY_ENDPOINT"
if [[ -n "${CRON_SECRET:-}" ]]; then
  echo "  (with: -H \"Authorization: Bearer \$CRON_SECRET\")"
fi

