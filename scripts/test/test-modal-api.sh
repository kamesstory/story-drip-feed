#!/bin/bash
#
# Test Modal API endpoints
# Tests health, extract-content, and chunk-story endpoints
#
# Usage:
#   ./test-modal-api.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/http.sh"

section "Testing Modal API Endpoints"

# Check for required environment variables
if ! check_required_env MODAL_API_URL MODAL_API_KEY; then
    info "Please set MODAL_API_URL and MODAL_API_KEY"
    info "Example: export MODAL_API_URL=https://your-app-id.modal.run"
    exit 1
fi

log "API URL: $MODAL_API_URL"
echo ""

# Test 1: Health Check
subsection "Test 1: Health Check"

if check_endpoint_health "$MODAL_API_URL/health" "Modal API"; then
    success "Health check passed"
else
    error "Health check failed"
    exit 1
fi
echo ""

# Test 2: Extract Content (with authentication)
subsection "Test 2: Extract Content"

STORAGE_ID="test-$(timestamp)"
log "Storage ID: $STORAGE_ID"

# Sample email data
EMAIL_DATA="{
  \"email_data\": {
    \"email_id\": \"$STORAGE_ID\",
    \"text\": \"Chapter 27\n\nMaryam was not having a good time.\n\nThe morning had started poorly, and things had only gotten worse from there. She had overslept, missed breakfast, and now found herself late for the most important meeting of her life.\n\nAs she hurried through the crowded streets, dodging vendors and pedestrians, she couldn't shake the feeling that someone was following her. Every time she glanced over her shoulder, though, there was nothing but the usual chaos of the marketplace.\n\n'You're being paranoid,' she muttered to herself, quickening her pace.\n\nBut paranoia, she would soon learn, wasn't always a bad thing.\",
    \"html\": \"\",
    \"subject\": \"Test Story - Chapter 27\",
    \"from\": \"Test Author <test@example.com>\"
  },
  \"storage_id\": \"$STORAGE_ID\"
}"

response=$(http_post_auth "$MODAL_API_URL/extract-content" "$EMAIL_DATA" "$MODAL_API_KEY" "Extract Content" 2)
http_code=$(echo "$response" | head -n1)
body=$(echo "$response" | tail -n+2)

if [ "$http_code" = "200" ]; then
    EXTRACT_STATUS=$(parse_json_field "$body" "status")
    if [ "$EXTRACT_STATUS" = "success" ]; then
        success "Content extraction passed"
        CONTENT_URL=$(parse_json_field "$body" "content_url")
        WORD_COUNT=$(parse_json_nested "$body" "metadata.word_count")
        info "Content URL: $CONTENT_URL"
        info "Word count: $WORD_COUNT"
    else
        error "Content extraction failed"
        exit 1
    fi
else
    error "Content extraction failed (HTTP $http_code)"
    exit 1
fi
echo ""

# Test 3: Chunk Story
subsection "Test 3: Chunk Story"

log "Using content from: $CONTENT_URL"

CHUNK_DATA="{
  \"content_url\": \"$CONTENT_URL\",
  \"storage_id\": \"$STORAGE_ID\",
  \"target_words\": 5000
}"

response=$(http_post_auth "$MODAL_API_URL/chunk-story" "$CHUNK_DATA" "$MODAL_API_KEY" "Chunk Story" 2)
http_code=$(echo "$response" | head -n1)
body=$(echo "$response" | tail -n+2)

if [ "$http_code" = "200" ]; then
    CHUNK_STATUS=$(parse_json_field "$body" "status")
    if [ "$CHUNK_STATUS" = "success" ]; then
        success "Chunking passed"
        TOTAL_CHUNKS=$(parse_json_field "$body" "total_chunks")
        TOTAL_WORDS=$(parse_json_field "$body" "total_words")
        STRATEGY=$(parse_json_field "$body" "chunking_strategy")
        info "Total chunks: $TOTAL_CHUNKS"
        info "Total words: $TOTAL_WORDS"
        info "Strategy: $STRATEGY"
    else
        error "Chunking failed"
        exit 1
    fi
else
    error "Chunking failed (HTTP $http_code)"
    exit 1
fi
echo ""

# Test 4: Authentication (should fail with wrong key)
echo "=================================================="
echo "Test 4: Authentication Test (Invalid Key)"
echo "=================================================="
echo "POST $EXTRACT_URL (with invalid key)"
echo ""

AUTH_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$EXTRACT_URL" \
  -H "Authorization: Bearer invalid-key-12345" \
  -H "Content-Type: application/json" \
  -d "$EMAIL_DATA")

HTTP_CODE=$(echo "$AUTH_RESPONSE" | tail -n1)
if [ "$HTTP_CODE" == "401" ]; then
    echo -e "${GREEN}✅ Authentication test passed (correctly rejected)${NC}"
else
    echo -e "${RED}❌ Authentication test failed (should return 401)${NC}"
    echo "Got HTTP code: $HTTP_CODE"
fi
echo ""

# Test 5: Missing Parameters
echo "=================================================="
echo "Test 5: Missing Parameters Test"
echo "=================================================="
echo "POST $EXTRACT_URL (missing storage_id)"
echo ""

MISSING_DATA='{
  "email_data": {
    "text": "Test",
    "subject": "Test",
    "from": "test@example.com"
  }
}'

MISSING_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$EXTRACT_URL" \
  -H "Authorization: Bearer $MODAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$MISSING_DATA")

HTTP_CODE=$(echo "$MISSING_RESPONSE" | tail -n1)
if [ "$HTTP_CODE" == "400" ]; then
    echo -e "${GREEN}✅ Missing parameters test passed (correctly rejected)${NC}"
else
    echo -e "${RED}❌ Missing parameters test failed (should return 400)${NC}"
    echo "Got HTTP code: $HTTP_CODE"
fi
echo ""

# Summary
section "✅ All Modal API Tests Passed"

info "Endpoints tested:"
echo "  ✅ GET /health"
echo "  ✅ POST /extract-content (valid request)"
echo "  ✅ POST /chunk-story (valid request)"
echo "  ✅ POST /extract-content (invalid auth)"
echo "  ✅ POST /extract-content (missing params)"
echo ""

info "Test storage ID: $STORAGE_ID"
echo ""

info "To verify files in Supabase Storage:"
echo "  - story-content/$STORAGE_ID/content.txt"
echo "  - story-chunks/$STORAGE_ID/chunk_001.txt"
echo "  - story-metadata/$STORAGE_ID/metadata.json"
echo ""

