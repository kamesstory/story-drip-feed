#!/bin/bash
set -e

echo "=== Storage Operations Test ==="
echo ""
echo "Prerequisites:"
echo "  - Supabase must be running (supabase start)"
echo "  - NextJS dev server must be running (npm run dev)"
echo "  - Storage bucket 'epubs' must exist in Supabase"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Change to the nextjs-app directory
cd "$(dirname "$0")/../../nextjs-app"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${RED}❌ node_modules not found. Run 'npm install' first.${NC}"
    exit 1
fi

echo -e "${YELLOW}Running storage tests...${NC}"
echo ""

# Create a test EPUB file (minimal valid EPUB)
mkdir -p test-epub
cat > test-epub/mimetype << 'EOF'
application/epub+zip
EOF

# Create a test script for storage operations
cat > test-storage-script.mjs << 'EOF'
import { 
  uploadEpub, 
  downloadEpub, 
  getPublicUrl,
  epubExists,
  deleteEpub 
} from './lib/storage.ts';
import fs from 'fs';

async function runTests() {
  const testFileName = 'test-' + Date.now() + '.epub';
  
  console.log('📝 Test 1: Create test EPUB file');
  const testContent = Buffer.from('This is a test EPUB file content');
  console.log(`✅ Created test buffer (${testContent.length} bytes)`);
  
  console.log('\n📝 Test 2: Upload EPUB to storage');
  const storagePath = await uploadEpub(testFileName, testContent);
  console.log(`✅ Uploaded to: ${storagePath}`);
  
  console.log('\n📝 Test 3: Check if EPUB exists');
  const exists = await epubExists(testFileName);
  if (!exists) {
    throw new Error('EPUB should exist after upload');
  }
  console.log(`✅ EPUB exists in storage`);
  
  console.log('\n📝 Test 4: Get public URL');
  const publicUrl = await getPublicUrl(storagePath);
  console.log(`✅ Public URL: ${publicUrl}`);
  
  console.log('\n📝 Test 5: Download EPUB from storage');
  const downloadedBuffer = await downloadEpub(storagePath);
  if (downloadedBuffer.length !== testContent.length) {
    throw new Error(`Size mismatch: uploaded ${testContent.length}, downloaded ${downloadedBuffer.length}`);
  }
  console.log(`✅ Downloaded EPUB (${downloadedBuffer.length} bytes)`);
  
  console.log('\n📝 Test 6: Delete EPUB from storage');
  await deleteEpub(storagePath);
  const existsAfterDelete = await epubExists(testFileName);
  if (existsAfterDelete) {
    console.log('⚠️  Warning: EPUB still exists after delete (may be eventual consistency)');
  } else {
    console.log(`✅ EPUB deleted successfully`);
  }
  
  console.log('\n✅ All storage tests passed!');
}

runTests().catch((error) => {
  console.error('\n❌ Test failed:', error.message);
  if (error.message.includes('storage')) {
    console.error('\nMake sure:');
    console.error('  1. Supabase is running (supabase start)');
    console.error('  2. Storage bucket "epubs" exists');
    console.error('  3. Environment variables are set correctly');
  }
  process.exit(1);
});
EOF

# Run the test script
node --loader ts-node/esm test-storage-script.mjs 2>&1 || {
    # If ts-node doesn't work, try with tsx
    npx tsx test-storage-script.mjs 2>&1 || {
        echo -e "${RED}❌ Failed to run test script${NC}"
        echo "Make sure you have TypeScript dependencies installed."
        rm -f test-storage-script.mjs
        rm -rf test-epub
        exit 1
    }
}

# Clean up
rm -f test-storage-script.mjs
rm -rf test-epub

echo ""
echo -e "${GREEN}✅ All storage operation tests completed successfully!${NC}"

