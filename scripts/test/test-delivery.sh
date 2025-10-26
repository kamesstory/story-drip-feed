#!/usr/bin/env bash
#
# Test script for daily delivery endpoint
# Tests both successful delivery and empty queue scenarios
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common utilities
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/http.sh"
source "$SCRIPT_DIR/../lib/db.sh"

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:3000}"
DELIVERY_ENDPOINT="$API_BASE_URL/api/delivery/send-next"

print_header "Daily Delivery Endpoint Tests"

#################
# Test 1: Health check - endpoint exists
#################
print_test "Test 1: Verify delivery endpoint is accessible"

response=$(curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  "$DELIVERY_ENDPOINT" || echo "000")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [[ "$http_code" == "200" ]] || [[ "$http_code" == "401" ]]; then
  print_success "Endpoint is accessible (HTTP $http_code)"
else
  print_error "Endpoint not accessible (HTTP $http_code)"
  echo "$body"
  exit 1
fi

#################
# Test 2: Test with CRON_SECRET if configured
#################
print_test "Test 2: Test authentication with CRON_SECRET"

if [[ -n "${CRON_SECRET:-}" ]]; then
  print_info "CRON_SECRET is set, testing authentication..."
  
  # Test without auth header (should fail)
  response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    "$DELIVERY_ENDPOINT" || echo "000")
  
  http_code=$(echo "$response" | tail -n1)
  
  if [[ "$http_code" == "401" ]]; then
    print_success "Correctly rejected request without auth header"
  else
    print_error "Expected 401 without auth header, got $http_code"
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
    print_success "Successfully authenticated with CRON_SECRET"
  else
    print_error "Failed to authenticate with valid CRON_SECRET (HTTP $http_code)"
    echo "$body"
    exit 1
  fi
else
  print_info "CRON_SECRET not set, skipping auth tests"
fi

#################
# Test 3: Test empty queue scenario
#################
print_test "Test 3: Test delivery with empty queue"

# Clear all chunks to ensure empty queue
print_info "Ensuring queue is empty..."
db_query "UPDATE story_chunks SET sent_to_kindle_at = NOW()" > /dev/null 2>&1 || true

# Build auth header if needed
AUTH_HEADER=""
if [[ -n "${CRON_SECRET:-}" ]]; then
  AUTH_HEADER="-H \"Authorization: Bearer $CRON_SECRET\""
fi

# Make request
response=$(eval curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  $AUTH_HEADER \
  "$DELIVERY_ENDPOINT" || echo "000")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [[ "$http_code" == "200" ]]; then
  # Check for queueEmpty flag in response
  if echo "$body" | grep -q '"queueEmpty".*true'; then
    print_success "Empty queue handled correctly"
    print_info "Response: $body"
  else
    print_error "Expected queueEmpty flag in response"
    echo "$body"
    exit 1
  fi
else
  print_error "Expected 200 for empty queue, got $http_code"
  echo "$body"
  exit 1
fi

#################
# Test 4: Test successful delivery (if chunks exist)
#################
print_test "Test 4: Test delivery with available chunk"

# Check if there are any chunks we can reset for testing
chunk_count=$(db_query "SELECT COUNT(*) FROM story_chunks" 2>/dev/null | tail -1 || echo "0")

if [[ "$chunk_count" == "0" ]]; then
  print_warning "No chunks in database - skipping delivery test"
  print_info "Run test-ingest-e2e.sh first to create test chunks"
else
  print_info "Found $chunk_count chunks in database"
  
  # Reset the first chunk to unsent status
  print_info "Resetting first chunk to unsent status..."
  db_query "UPDATE story_chunks SET sent_to_kindle_at = NULL WHERE id = (SELECT MIN(id) FROM story_chunks)" > /dev/null
  
  # Get the chunk ID we're about to send
  chunk_id=$(db_query "SELECT id FROM story_chunks WHERE sent_to_kindle_at IS NULL ORDER BY created_at, chunk_number LIMIT 1" 2>/dev/null | tail -1 || echo "")
  
  if [[ -z "$chunk_id" ]]; then
    print_error "Failed to find unsent chunk after reset"
    exit 1
  fi
  
  print_info "Will attempt to deliver chunk ID: $chunk_id"
  
  # Make delivery request
  response=$(eval curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    $AUTH_HEADER \
    "$DELIVERY_ENDPOINT" || echo "000")
  
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')
  
  if [[ "$http_code" == "200" ]]; then
    if echo "$body" | grep -q '"success".*true'; then
      print_success "Delivery completed successfully"
      
      # Verify chunk was marked as sent
      sent_at=$(db_query "SELECT sent_to_kindle_at FROM story_chunks WHERE id = $chunk_id" 2>/dev/null | tail -1 || echo "")
      
      if [[ -n "$sent_at" ]] && [[ "$sent_at" != "sent_to_kindle_at" ]]; then
        print_success "Chunk marked as sent in database"
      else
        print_error "Chunk was not marked as sent in database"
        exit 1
      fi
      
      # Display delivery details
      print_info "Delivery details:"
      echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
    else
      print_error "Response missing success flag"
      echo "$body"
      exit 1
    fi
  else
    print_error "Delivery failed (HTTP $http_code)"
    echo "$body"
    exit 1
  fi
fi

#################
# Test 5: Verify TEST_MODE behavior
#################
print_test "Test 5: Verify TEST_MODE behavior"

if [[ "${TEST_MODE:-false}" == "true" ]]; then
  print_success "TEST_MODE is enabled - emails will not actually send"
  print_info "Check logs for '[TEST_MODE]' indicators"
else
  print_warning "TEST_MODE is disabled - emails are being sent for real!"
  print_info "Set TEST_MODE=true to prevent actual email sends during testing"
fi

#################
# Summary
#################
print_header "Test Summary"
print_success "All delivery endpoint tests passed!"

echo ""
print_info "Next steps:"
echo "  1. Deploy to Vercel to test cron job"
echo "  2. Check Vercel logs for cron execution at 12pm PT daily"
echo "  3. Verify Kindle receives daily chunks"
echo "  4. Monitor admin notification emails"
echo ""
print_info "Manual trigger: curl -X POST $DELIVERY_ENDPOINT"
if [[ -n "${CRON_SECRET:-}" ]]; then
  echo "  (with: -H \"Authorization: Bearer \$CRON_SECRET\")"
fi

