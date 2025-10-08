#!/bin/bash
# Test script for story chunking
# Usage: ./test_story.sh [story_file] [agent|simple]

set -e

STORY_FILE="${1:-examples/inputs/pale-lights-example-1.txt}"
CHUNKER_TYPE="${2:-agent}"

# Check if file exists
if [ ! -f "$STORY_FILE" ]; then
    echo "❌ Error: Story file not found: $STORY_FILE"
    echo ""
    echo "Available examples:"
    ls -1 examples/inputs/*.txt | sed 's/^/  - /'
    exit 1
fi

# Get word count
WORD_COUNT=$(wc -w < "$STORY_FILE")
STORY_NAME=$(basename "$STORY_FILE" .txt)

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                         STORY CHUNKING TEST                                ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📖 Story: $STORY_NAME"
echo "📊 Length: $WORD_COUNT words"
echo "🤖 Chunker: $CHUNKER_TYPE"
echo "🎯 Target: 8000 words/chunk (±15%)"
echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Run the test
poetry run python test_real_story.py "$STORY_FILE" "$CHUNKER_TYPE"

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
echo "💡 Tips:"
echo "  - Stories under ~7,000 words typically become 1 chunk"
echo "  - Stories 14,000-18,000 words typically become 2 chunks"
echo "  - Agent chunker respects scene breaks (---, * * *)"
echo "  - Chunks include 'Previously:' recaps (except first chunk)"
echo ""
echo "📁 Test artifacts saved to:"
echo "  - ./local_data/         (story and chunk files)"
echo "  - ./test_stories.db     (SQLite database)"
echo ""
