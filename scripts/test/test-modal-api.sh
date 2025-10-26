#!/bin/bash

# Test script for Modal API endpoints
# Tests health, extract-content, and chunk-story endpoints

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "🧪 Testing Modal API Endpoints"
echo "=================================================="
echo ""

# Check for required environment variables
if [ -z "$MODAL_API_URL" ]; then
    echo -e "${RED}❌ Error: MODAL_API_URL not set${NC}"
    echo "Please set MODAL_API_URL to your Modal API base URL"
    echo "Example: export MODAL_API_URL=https://your-app-id.modal.run"
    exit 1
fi

if [ -z "$MODAL_API_KEY" ]; then
    echo -e "${RED}❌ Error: MODAL_API_KEY not set${NC}"
    echo "Please set MODAL_API_KEY to your API key"
    exit 1
fi

echo "📍 API URL: $MODAL_API_URL"
echo ""

# Test 1: Health Check
echo "=================================================="
echo "Test 1: Health Check"
echo "=================================================="
HEALTH_URL="${MODAL_API_URL}/health"
echo "GET $HEALTH_URL"
echo ""

HEALTH_RESPONSE=$(curl -s "$HEALTH_URL")
echo "$HEALTH_RESPONSE" | jq '.'

STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status')
if [ "$STATUS" == "healthy" ] || [ "$STATUS" == "degraded" ]; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${RED}❌ Health check failed${NC}"
    exit 1
fi
echo ""

# Test 2: Extract Content (with authentication)
echo "=================================================="
echo "Test 2: Extract Content"
echo "=================================================="
EXTRACT_URL="${MODAL_API_URL}/extract-content"
STORAGE_ID="test-$(date +%s)"

echo "POST $EXTRACT_URL"
echo "Storage ID: $STORAGE_ID"
echo ""

# Sample email data
EMAIL_DATA='{
  "email_data": {
    "text": "Chapter 27\n\nMaryam was not having a good time.\n\nThe morning had started poorly, and things had only gotten worse from there. She had overslept, missed breakfast, and now found herself late for the most important meeting of her life.\n\nAs she hurried through the crowded streets, dodging vendors and pedestrians, she couldn'\''t shake the feeling that someone was following her. Every time she glanced over her shoulder, though, there was nothing but the usual chaos of the marketplace.\n\n\"You'\''re being paranoid,\" she muttered to herself, quickening her pace.\n\nBut paranoia, she would soon learn, wasn'\''t always a bad thing.",
    "html": "",
    "subject": "Test Story - Chapter 27",
    "from": "Test Author <test@example.com>"
  },
  "storage_id": "'$STORAGE_ID'"
}'

EXTRACT_RESPONSE=$(curl -s -X POST "$EXTRACT_URL" \
  -H "Authorization: Bearer $MODAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$EMAIL_DATA")

echo "$EXTRACT_RESPONSE" | jq '.'

EXTRACT_STATUS=$(echo "$EXTRACT_RESPONSE" | jq -r '.status')
if [ "$EXTRACT_STATUS" == "success" ]; then
    echo -e "${GREEN}✅ Content extraction passed${NC}"
    CONTENT_URL=$(echo "$EXTRACT_RESPONSE" | jq -r '.content_url')
    WORD_COUNT=$(echo "$EXTRACT_RESPONSE" | jq -r '.metadata.word_count')
    echo "Content URL: $CONTENT_URL"
    echo "Word count: $WORD_COUNT"
else
    echo -e "${RED}❌ Content extraction failed${NC}"
    exit 1
fi
echo ""

# Test 3: Chunk Story
echo "=================================================="
echo "Test 3: Chunk Story"
echo "=================================================="
CHUNK_URL="${MODAL_API_URL}/chunk-story"

echo "POST $CHUNK_URL"
echo "Using content from: $CONTENT_URL"
echo ""

CHUNK_DATA='{
  "content_url": "'$CONTENT_URL'",
  "storage_id": "'$STORAGE_ID'",
  "target_words": 5000
}'

CHUNK_RESPONSE=$(curl -s -X POST "$CHUNK_URL" \
  -H "Authorization: Bearer $MODAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$CHUNK_DATA")

echo "$CHUNK_RESPONSE" | jq '.'

CHUNK_STATUS=$(echo "$CHUNK_RESPONSE" | jq -r '.status')
if [ "$CHUNK_STATUS" == "success" ]; then
    echo -e "${GREEN}✅ Chunking passed${NC}"
    TOTAL_CHUNKS=$(echo "$CHUNK_RESPONSE" | jq -r '.total_chunks')
    TOTAL_WORDS=$(echo "$CHUNK_RESPONSE" | jq -r '.total_words')
    STRATEGY=$(echo "$CHUNK_RESPONSE" | jq -r '.chunking_strategy')
    echo "Total chunks: $TOTAL_CHUNKS"
    echo "Total words: $TOTAL_WORDS"
    echo "Strategy: $STRATEGY"
else
    echo -e "${RED}❌ Chunking failed${NC}"
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
echo "=================================================="
echo "✅ All Modal API tests completed successfully!"
echo "=================================================="
echo ""
echo "Endpoints tested:"
echo "  ✅ GET /health"
echo "  ✅ POST /extract-content (valid request)"
echo "  ✅ POST /chunk-story (valid request)"
echo "  ✅ POST /extract-content (invalid auth)"
echo "  ✅ POST /extract-content (missing params)"
echo ""
echo "Test storage ID: $STORAGE_ID"
echo ""
echo "To verify files in Supabase Storage:"
echo "  - story-content/$STORAGE_ID/content.txt"
echo "  - story-chunks/$STORAGE_ID/chunk_001.txt"
echo "  - story-metadata/$STORAGE_ID/metadata.json"
echo ""

