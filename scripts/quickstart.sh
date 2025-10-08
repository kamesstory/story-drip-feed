#!/bin/bash
# Quick start script for local testing

set -e

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                    Story Prep Pipeline - Quick Start                      ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo ""
    echo "🔧 Please edit .env and add your ANTHROPIC_API_KEY"
    echo "   (Required for AI-powered extraction and chunking)"
    echo ""
    read -p "Press Enter when ready to continue..."
    echo ""
fi

# Check for ANTHROPIC_API_KEY
source .env
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your-anthropic-key" ]; then
    echo "⚠️  ANTHROPIC_API_KEY not set in .env"
    echo "   You can still test with simple chunking, but AI features won't work"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    echo ""
fi

echo "🧪 Running tests..."
echo ""

# Clean up old test data
echo "🗑️  Cleaning up old test data..."
rm -rf ./local_data ./test_stories.db
echo ""

# Run quick test
echo "📝 Test 1: Single Story Test"
echo "════════════════════════════════════════════════════════════════════════════"
./test_story.sh examples/inputs/pale-lights-example-1.txt
echo ""
echo "Press Enter to continue to full pipeline test..."
read

# Clean up again
rm -rf ./local_data ./test_stories.db

echo ""
echo "📦 Test 2: Full Pipeline Test (with EPUB generation)"
echo "════════════════════════════════════════════════════════════════════════════"
poetry run python test_full_pipeline.py
echo ""

echo "════════════════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Quick start complete!"
echo ""
echo "📊 Check the results:"
echo "   • Files: tree local_data/"
echo "   • Database: sqlite3 test_stories.db"
echo "   • Chunks: cat local_data/chunks/story_*/chunk_*.txt"
echo "   • EPUB: ls -lh local_data/epubs/"
echo ""
echo "🚀 Next steps:"
echo "   1. Test with your own story:"
echo "      cp your-story.txt examples/inputs/"
echo "      ./test_story.sh examples/inputs/your-story.txt"
echo ""
echo "   2. Deploy to Modal:"
echo "      poetry run modal deploy main.py"
echo ""
echo "   3. See full documentation:"
echo "      cat LOCAL_TESTING.md"
echo "      cat PIPELINE_COMPLETE.md"
echo ""
