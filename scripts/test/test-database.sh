#!/bin/bash
#
# Test database operations
#
# Usage:
#   ./test-database.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"
source "$SCRIPT_DIR/../lib/db.sh"

# Change to the nextjs-app directory
NEXTJS_DIR="$SCRIPT_DIR/../../nextjs-app"
cd "$NEXTJS_DIR"

section "Database Operations Test"

info "Prerequisites:"
echo "  - Supabase must be running (supabase start)"
echo "  - NextJS dev server must be running (npm run dev)"
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    error "node_modules not found. Run 'npm install' first."
    exit 1
fi

log "Running database tests..."
echo ""

# Create a test script that uses the database utilities
cat > test-db-script.mjs << 'EOF'
import { config } from 'dotenv';
config({ path: '.env.local' });

import { 
  createStory, 
  getStoryById, 
  createChunk, 
  getStoryChunks,
  getNextUnsentChunk,
  markChunkSent,
  deleteStory,
  updateStoryStatus,
  updateStoryMetadata
} from './lib/db.ts';

async function runTests() {
  console.log('📝 Test 1: Create a story');
  const story = await createStory({
    email_id: 'test-' + Date.now() + '@example.com',
    title: 'Test Story',
    author: 'Test Author',
    source: 'test',
  });
  console.log(`✅ Created story with ID: ${story.id}`);
  
  console.log('\n📝 Test 2: Get story by ID');
  const fetchedStory = await getStoryById(story.id);
  if (!fetchedStory || fetchedStory.title !== 'Test Story') {
    throw new Error('Failed to fetch story or data mismatch');
  }
  console.log(`✅ Fetched story: ${fetchedStory.title} by ${fetchedStory.author}`);
  
  console.log('\n📝 Test 3: Update story metadata');
  await updateStoryMetadata(story.id, {
    word_count: 1000,
    extraction_method: 'test_agent',
  });
  const updatedStory = await getStoryById(story.id);
  if (updatedStory?.word_count !== 1000) {
    throw new Error('Failed to update story metadata');
  }
  console.log(`✅ Updated story metadata (word_count: ${updatedStory.word_count})`);
  
  console.log('\n📝 Test 4: Create chunks');
  const chunk1 = await createChunk({
    story_id: story.id,
    chunk_number: 1,
    total_chunks: 2,
    chunk_text: 'This is chunk 1 content',
    word_count: 500,
  });
  const chunk2 = await createChunk({
    story_id: story.id,
    chunk_number: 2,
    total_chunks: 2,
    chunk_text: 'This is chunk 2 content',
    word_count: 500,
  });
  console.log(`✅ Created 2 chunks (IDs: ${chunk1.id}, ${chunk2.id})`);
  
  console.log('\n📝 Test 5: Get story chunks');
  const chunks = await getStoryChunks(story.id);
  if (chunks.length !== 2) {
    throw new Error(`Expected 2 chunks, got ${chunks.length}`);
  }
  console.log(`✅ Fetched ${chunks.length} chunks`);
  
  console.log('\n📝 Test 6: Update story to chunked status');
  await updateStoryStatus(story.id, 'chunked');
  const chunkedStory = await getStoryById(story.id);
  if (chunkedStory?.status !== 'chunked') {
    throw new Error('Failed to update story status');
  }
  console.log(`✅ Story status updated to: ${chunkedStory.status}`);
  
  console.log('\n📝 Test 7: Get next unsent chunk');
  const nextChunk = await getNextUnsentChunk();
  if (!nextChunk || nextChunk.id !== chunk1.id) {
    throw new Error('Failed to get next unsent chunk');
  }
  console.log(`✅ Next unsent chunk: ${nextChunk.chunk_number}/${nextChunk.total_chunks}`);
  
  console.log('\n📝 Test 8: Mark chunk as sent');
  await markChunkSent(chunk1.id);
  const sentChunk = await getNextUnsentChunk();
  if (sentChunk?.id === chunk1.id) {
    throw new Error('Chunk should be marked as sent');
  }
  console.log(`✅ Chunk marked as sent, next unsent: ${sentChunk?.chunk_number || 'none'}`);
  
  console.log('\n📝 Test 9: Delete story (cascades to chunks)');
  await deleteStory(story.id);
  const deletedStory = await getStoryById(story.id);
  if (deletedStory !== null) {
    throw new Error('Story should be deleted');
  }
  const deletedChunks = await getStoryChunks(story.id);
  if (deletedChunks.length !== 0) {
    throw new Error('Chunks should be deleted via cascade');
  }
  console.log(`✅ Story and chunks deleted successfully`);
  
  console.log('\n✅ All database tests passed!');
}

runTests().catch((error) => {
  console.error('\n❌ Test failed:', error.message);
  process.exit(1);
});
EOF

# Run the test script
if npx tsx test-db-script.mjs 2>&1; then
    success "Database operations test completed"
else
    error "Failed to run test script"
    info "Make sure you have TypeScript dependencies installed."
    rm -f test-db-script.mjs
    exit 1
fi

# Clean up
rm -f test-db-script.mjs

echo ""
section "✅ All Database Tests Passed"

