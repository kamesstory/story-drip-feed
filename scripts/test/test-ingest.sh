#!/bin/bash

#
# Story Ingestion Pipeline Test Script
#
# Tests the complete story processing pipeline with detailed logging
# at each step to make debugging and verification easy.
#
# Usage:
#   ./test-ingest.sh              # Run component tests
#   ./test-ingest.sh --brevo       # Run Brevo integration test
#   ./test-ingest.sh --clean       # Clean test data first
#   ./test-ingest.sh --verbose     # Extra verbose output
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${NEXT_PUBLIC_BASE_URL:-http://localhost:3000}"
LOG_FILE="/tmp/test-ingest-$(date +%Y%m%d-%H%M%S).log"
VERBOSE=false
CLEAN=false
BREVO_MODE=false

# Parse arguments
for arg in "$@"; do
  case $arg in
    --verbose)
      VERBOSE=true
      shift
      ;;
    --clean)
      CLEAN=true
      shift
      ;;
    --brevo|--brevo-integration)
      BREVO_MODE=true
      shift
      ;;
    *)
      ;;
  esac
done

# Utility functions
log() {
  echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
  echo -e "${GREEN}✅ $1${NC}" | tee -a "$LOG_FILE"
}

error() {
  echo -e "${RED}❌ $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
  echo -e "${YELLOW}⚠️  $1${NC}" | tee -a "$LOG_FILE"
}

info() {
  echo -e "${BLUE}ℹ️  $1${NC}" | tee -a "$LOG_FILE"
}

section() {
  echo "" | tee -a "$LOG_FILE"
  echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}" | tee -a "$LOG_FILE"
  echo -e "${CYAN}$1${NC}" | tee -a "$LOG_FILE"
  echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}" | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
}

subsection() {
  echo "" | tee -a "$LOG_FILE"
  echo -e "${YELLOW}─── $1 ───${NC}" | tee -a "$LOG_FILE"
}

# Pretty print JSON
print_json() {
  if command -v jq &> /dev/null; then
    echo "$1" | jq '.' | tee -a "$LOG_FILE"
  else
    echo "$1" | tee -a "$LOG_FILE"
  fi
}

# Make HTTP request with logging
http_request() {
  local method=$1
  local url=$2
  local data=$3
  local description=$4
  
  subsection "$description"
  log "Request: $method $url"
  
  if [ -n "$data" ]; then
    if [ "$VERBOSE" = true ]; then
      info "Request body:"
      print_json "$data"
    fi
  fi
  
  local response
  local http_code
  
  if [ -n "$data" ]; then
    response=$(curl -s -w "\n%{http_code}" -X "$method" \
      -H "Content-Type: application/json" \
      -d "$data" \
      "$url" 2>&1)
  else
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" 2>&1)
  fi
  
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')
  
  log "HTTP Status: $http_code"
  
  if [ "$VERBOSE" = true ] || [ "$http_code" -ge 400 ]; then
    info "Response body:"
    print_json "$body"
  fi
  
  # Return both code and body
  echo "$http_code"
  echo "$body"
}

# Wait for service to be ready
wait_for_service() {
  local url=$1
  local service_name=$2
  local max_attempts=30
  local attempt=1
  
  log "Waiting for $service_name to be ready..."
  
  while [ $attempt -le $max_attempts ]; do
    if curl -s "$url" > /dev/null 2>&1; then
      success "$service_name is ready"
      return 0
    fi
    
    if [ $attempt -eq $max_attempts ]; then
      error "$service_name did not become ready after $max_attempts attempts"
      return 1
    fi
    
    sleep 1
    attempt=$((attempt + 1))
  done
}

# Clean test data
clean_test_data() {
  subsection "Cleaning test data"
  
  # This would need to be implemented based on your needs
  # For now, just log that we would clean
  warning "Clean functionality not yet implemented"
  warning "You may want to manually clean test stories from the database"
}

# Test 1: Health checks
test_health_checks() {
  section "TEST 1: Health Checks"
  
  # NextJS health
  subsection "Checking NextJS health"
  log "Request: GET $BASE_URL/api/health"
  
  http_response=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/health")
  http_code=$(echo "$http_response" | tail -n1)
  body=$(echo "$http_response" | sed '$d')
  
  log "HTTP Status: $http_code"
  
  if [ "$VERBOSE" = true ]; then
    info "Response body:"
    print_json "$body"
  fi
  
  if [ "$http_code" = "200" ]; then
    success "NextJS is healthy"
  else
    error "NextJS health check failed (HTTP $http_code)"
    return 1
  fi
  
  # Modal API health
  subsection "Checking Modal API health"
  modal_url="${MODAL_API_URL}"
  
  if [ -z "$modal_url" ]; then
    warning "MODAL_API_URL not set, skipping Modal health check"
  else
    log "Request: GET ${modal_url}/health"
    
    http_response=$(curl -s -w "\n%{http_code}" "${modal_url}/health")
    http_code=$(echo "$http_response" | tail -n1)
    body=$(echo "$http_response" | sed '$d')
    
    log "HTTP Status: $http_code"
    
    if [ "$VERBOSE" = true ]; then
      info "Response body:"
      print_json "$body"
    fi
    
    if [ "$http_code" = "200" ]; then
      success "Modal API is healthy"
    else
      error "Modal API health check failed (HTTP $http_code)"
      return 1
    fi
  fi
  
  success "All health checks passed"
}

# Test 2: Test email webhook
test_email_webhook() {
  section "TEST 2: Email Webhook"
  
  subsection "Creating test email payload"
  
  # Create a test email payload (Brevo format)
  local test_email_payload=$(cat << 'EOF'
{
  "items": [
    {
      "From": {
        "Address": "test@example.com",
        "Name": "Test Sender"
      },
      "To": [
        {
          "Address": "stories@yourdomain.com",
          "Name": "Story Receiver"
        }
      ],
      "Subject": "Test Story: The Adventure Begins",
      "RawHtmlBody": "<html><body><p>Once upon a time, there was a test story.</p><p>This is a simple test with minimal content to verify the pipeline works.</p></body></html>",
      "RawTextBody": "Once upon a time, there was a test story.\n\nThis is a simple test with minimal content to verify the pipeline works.",
      "MessageId": "test-message-$(date +%s)"
    }
  ]
}
EOF
)
  
  info "Sample email payload (Brevo format):"
  if [ "$VERBOSE" = true ]; then
    print_json "$test_email_payload"
  else
    echo "  From: test@example.com" | tee -a "$LOG_FILE"
    echo "  Subject: Test Story: The Adventure Begins" | tee -a "$LOG_FILE"
  fi
  
  subsection "Sending test email to webhook"
  log "Request: POST $BASE_URL/api/webhooks/email"
  
  http_response=$(curl -s -w "\n%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -d "$test_email_payload" \
    "$BASE_URL/api/webhooks/email")
  
  http_code=$(echo "$http_response" | tail -n1)
  body=$(echo "$http_response" | sed '$d')
  
  log "HTTP Status: $http_code"
  
  if [ "$VERBOSE" = true ]; then
    info "Response body:"
    print_json "$body"
  fi
  
  if [ "$http_code" = "200" ]; then
    success "Email webhook accepted (HTTP 200)"
    
    # Extract email ID from response
    if command -v jq &> /dev/null; then
      email_id=$(echo "$body" | jq -r '.email_ids[0]' 2>/dev/null || echo "unknown")
      info "Email ID: $email_id"
      echo "$email_id" > /tmp/test-ingest-email-id.txt
    fi
    
    info "Response summary:"
    print_json "$body"
  else
    error "Email webhook failed (HTTP $http_code)"
    if [ "$VERBOSE" = false ]; then
      error "Response:"
      print_json "$body"
    fi
    return 1
  fi
  
  success "Email webhook test passed"
}

# Test 3: Monitor processing
monitor_processing() {
  section "TEST 3: Monitor Story Processing"
  
  info "Waiting for story to be processed..."
  info "This may take 30-120 seconds depending on Modal API response time"
  
  local max_wait=180  # 3 minutes
  local elapsed=0
  local check_interval=5
  
  while [ $elapsed -lt $max_wait ]; do
    sleep $check_interval
    elapsed=$((elapsed + check_interval))
    
    # This would query the database to check story status
    # For now, just show progress
    echo -n "." | tee -a "$LOG_FILE"
    
    if [ $((elapsed % 30)) -eq 0 ]; then
      echo "" | tee -a "$LOG_FILE"
      info "Still processing... (${elapsed}s elapsed)"
    fi
  done
  
  echo "" | tee -a "$LOG_FILE"
  warning "Processing monitoring not fully implemented"
  warning "Check the NextJS logs manually to verify processing completed"
  info "You can check logs with: docker logs <container-name> 2>&1 | grep 'STORY PROCESSING'"
}

# Test 4: Verify results
verify_results() {
  section "TEST 4: Verify Results"
  
  subsection "Checking for test story in database"
  warning "Database verification not implemented in this script"
  info "You should manually verify:"
  echo "  1. Story record created in 'stories' table" | tee -a "$LOG_FILE"
  echo "  2. Story status is 'chunked'" | tee -a "$LOG_FILE"
  echo "  3. Chunk records created in 'story_chunks' table" | tee -a "$LOG_FILE"
  echo "  4. EPUBs uploaded to Supabase Storage" | tee -a "$LOG_FILE"
  echo "  5. Email notifications sent" | tee -a "$LOG_FILE"
  
  subsection "Storage paths to check"
  info "Email data: email-data/<storage-id>/email.json"
  info "Extracted content: story-content/<storage-id>/content.txt"
  info "Chunks: story-chunks/<storage-id>/chunk_001.txt, etc."
  info "EPUBs: epubs/<title>_part1.epub, etc."
}

# Main test flow
main() {
  section "Story Ingestion Pipeline Test"
  
  log "Test started at: $(date)"
  log "Base URL: $BASE_URL"
  log "Log file: $LOG_FILE"
  log "Verbose: $VERBOSE"
  log "Clean mode: $CLEAN"
  log "Brevo integration: $BREVO_MODE"
  
  # Clean if requested
  if [ "$CLEAN" = true ]; then
    clean_test_data
  fi
  
  # Run tests
  if [ "$BREVO_MODE" = true ]; then
    section "BREVO INTEGRATION MODE"
    warning "Brevo integration test not yet implemented"
    info "To test with real Brevo emails:"
    echo "  1. Configure Brevo webhook to point to your endpoint" | tee -a "$LOG_FILE"
    echo "  2. Send a test email to your inbound address" | tee -a "$LOG_FILE"
    echo "  3. Watch the logs for processing" | tee -a "$LOG_FILE"
    exit 0
  fi
  
  # Component tests
  test_health_checks || exit 1
  test_email_webhook || exit 1
  monitor_processing
  verify_results
  
  section "TEST SUMMARY"
  success "Component tests completed"
  info "Review the detailed logs at: $LOG_FILE"
  
  echo "" | tee -a "$LOG_FILE"
  info "Next steps:"
  echo "  1. Check NextJS logs for detailed processing output" | tee -a "$LOG_FILE"
  echo "  2. Verify story in database: psql or Supabase dashboard" | tee -a "$LOG_FILE"
  echo "  3. Check Supabase Storage for EPUBs" | tee -a "$LOG_FILE"
  echo "  4. Verify notification emails were sent" | tee -a "$LOG_FILE"
  
  log "Test completed at: $(date)"
}

# Run main
main

