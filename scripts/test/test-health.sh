#!/bin/bash
set -e

echo "=== Health Endpoint Test ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if NextJS is running
if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${RED}❌ NextJS dev server is not running on port 3000${NC}"
    echo "Please start it with: cd nextjs-app && npm run dev"
    exit 1
fi

echo "Testing health endpoint..."
RESPONSE=$(curl -s http://localhost:3000/api/health)

# Check if we got a response
if [ -z "$RESPONSE" ]; then
    echo -e "${RED}❌ No response from health endpoint${NC}"
    exit 1
fi

# Parse response using grep and cut (works without jq)
STATUS=$(echo $RESPONSE | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

if [ "$STATUS" = "ok" ]; then
    echo -e "${GREEN}✅ Health check passed${NC}"
    echo ""
    echo "Response:"
    echo $RESPONSE | python3 -m json.tool 2>/dev/null || echo $RESPONSE
    echo ""
    exit 0
else
    echo -e "${RED}❌ Health check failed${NC}"
    echo "Response: $RESPONSE"
    exit 1
fi

