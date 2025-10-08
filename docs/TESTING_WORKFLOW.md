# Complete Testing Workflow Guide

Step-by-step guide for testing a story from submission to cleanup.

---

## Prerequisites

```bash
# Ensure Modal is authenticated
poetry run modal token new

# Ensure .env is configured
cp .env.example .env
# Edit .env with your settings
```

---

## Step 1: Start Development Server

```bash
# Start the dev server (keep this running in Terminal 1)
poetry run modal serve main_local.py
```

**Expected output:**
```
✓ Created web function submit_url => https://you--nighttime-story-prep-dev-submit-url-dev.modal.run
✓ Created web function webhook => https://you--nighttime-story-prep-dev-webhook-dev.modal.run
⚡️ Serving... hit Ctrl-C to stop!
```

**Copy the `submit_url` for the next step!**

---

## Step 2: Submit a Story URL

Open a **new terminal** (Terminal 2) and submit your story:

```bash
# Replace YOUR_SUBMIT_URL with the URL from step 1
curl -X POST 'YOUR_SUBMIT_URL' \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://wanderinginn.com/2025/09/19/halfseekers-pt-6/",
    "title": "Halfseekers Pt. 6",
    "author": "pirateaba"
  }'
```

**Example with actual URL:**
```bash
curl -X POST 'https://kamesstory--nighttime-story-prep-dev-submit-url-dev.modal.run' \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://wanderinginn.com/2025/09/19/halfseekers-pt-6/",
    "title": "Halfseekers Pt. 6",
    "author": "pirateaba"
  }'
```

**Expected response:**
```json
{
  "status": "accepted",
  "message": "Processing story from URL: https://wanderinginn.com/...",
  "call_id": "fc-...",
  "url": "https://wanderinginn.com/..."
}
```

**Watch Terminal 1** - You'll see processing logs:
```
Attempting agent-based content extraction...
Using traditional EmailParser strategies...
Found content using selector: article .entry-content
✅ Saved story files
Using Agent chunker with target 5000 words
✅ Created 5 chunks for story 2
```

---

## Step 3: Verify Story Was Processed

### List All Stories

```bash
poetry run modal run scripts/manage_dev_db.py::list_stories
```

**Expected output:**
```
================================================================================
DEV DATABASE - ALL STORIES
================================================================================

📚 Total Stories: 1

Story ID: 1
  Title: Halfseekers Pt. 6
  Author: pirateaba
  Status: chunked
  Words: 24694
  Chunks: 0/5 sent
  Received: 2025-10-08 05:46:19

📬 NEXT CHUNK TO SEND:
  Story: Halfseekers Pt. 6
  Part: 1/5
  Words: 5496
================================================================================
```

**✅ Verify:**
- Status is "chunked" (not "failed" or "processing")
- Chunks count looks correct (e.g., "0/5 sent")
- Word count is reasonable

---

## Step 4: Inspect Story Details

### View Full Story with All Chunks

```bash
poetry run modal run scripts/manage_dev_db.py::view_story --story-id 1
```

**Expected output:**
```
================================================================================
STORY ID 1: Halfseekers Pt. 6
================================================================================
Author: pirateaba
Status: chunked
Total Words: 24694
Received: 2025-10-08 05:46:19
Extraction Method: fallback
Content Path: raw/story_000001/content.txt

Chunks: 5 total
--------------------------------------------------------------------------------
  Chunk 1: Part 1/5 | 5496 words | ⏳ PENDING
    Preview: This was Jelaqua Ivirith's tale, but like a candy bar...

  Chunk 2: Part 2/5 | 5447 words | ⏳ PENDING
    Preview: Look, he's from the inn—they're crazy over there...

  Chunk 3: Part 3/5 | 5485 words | ⏳ PENDING
    Preview: At this point, Emessa had come out of her own smithy...

  Chunk 4: Part 4/5 | 5469 words | ⏳ PENDING
    Preview: All of it either told Rhaldon this was an amazing fake...

  Chunk 5: Part 5/5 | 2797 words | ⏳ PENDING
    Preview: Dude, this is why I had to have someone who knew mechanics...
================================================================================
```

**✅ Verify:**
- All chunks are present (1/5, 2/5, 3/5, etc.)
- Word counts are balanced (~5000 words each, last chunk can be smaller)
- Previews show actual story content (not metadata)
- All chunks are "⏳ PENDING" (not sent yet)

---

## Step 5: Read Full Chunk Content

### View Complete Chunk Text

```bash
# View the first chunk (replace chunk-id with actual ID from previous step)
poetry run modal run scripts/manage_dev_db.py::view_chunk --chunk-id 1
```

**Expected output:**
```
================================================================================
CHUNK 1/5: Halfseekers Pt. 6
By pirateaba | 5496 words
================================================================================
<div class="entry-content">
<p>This was Jelaqua Ivirith's tale, but like a candy bar, it sometimes
revolved around one of its ingredients.

Much like a peanut, Kevin found a way to make it about himself.</p>

<p>He missed candy bars.</p>

<p>Dead gods, he missed <em>Snickers.</em> You couldn't have paid him...
[full chunk content]
================================================================================
```

**✅ Verify:**
- Content is clean HTML with `<p>` tags
- Story text is present and readable
- No metadata pollution (no "Chapter X", dates, "View in app" buttons, etc.)
- Content starts and ends at reasonable points
- If not first chunk, check for "Previously:" recap section

### Check Database Statistics

```bash
poetry run modal run scripts/manage_dev_db.py::stats
```

**Expected output:**
```
================================================================================
DEV DATABASE STATISTICS
================================================================================

📊 Stories by Status:
  chunked: 1

📚 Chunks:
  Total: 5
  Sent: 0
  Pending: 5

📝 Total Words: 24,694
================================================================================
```

---

## Step 6: Test EPUB Generation & Sending

### Send Next Chunk (TEST MODE)

```bash
poetry run modal run main_local.py::send_next_chunk
```

**Expected output:**
```
📤 Sending chunk 1/5: Halfseekers Pt. 6

================================================================================
TEST MODE - Email would be sent with the following details:
================================================================================
From: your-email@gmail.com
To: your-kindle@kindle.com
Subject: Halfseekers Pt. 6 - Part 1/5
Title: Halfseekers Pt. 6
Number of attachments: 1

Attachments:
  1. Halfseekers_Pt._6_part1.epub (13.5 KB)
================================================================================
```

**✅ Verify:**
- EPUB was generated (check file size is reasonable, e.g., 10-20 KB)
- Subject line is correct
- In TEST_MODE, email is NOT actually sent (just simulated)

### Verify Chunk Was Marked as Sent

```bash
poetry run modal run scripts/manage_dev_db.py::view_story --story-id 1
```

**Expected output:**
```
  Chunk 1: Part 1/5 | 5496 words | ✅ SENT
    Sent: 2025-10-08 05:50:23
  Chunk 2: Part 2/5 | 5447 words | ⏳ PENDING
  ...
```

---

## Step 7: Download & Inspect Locally (Optional)

### Download Database

```bash
# Download dev database to local file
poetry run modal volume get story-data-dev stories-dev.db ./test-review.db
```

### Query with SQLite

```bash
# View all stories
sqlite3 ./test-review.db "SELECT id, title, status, word_count FROM stories;"

# View all chunks for story 1
sqlite3 ./test-review.db "
  SELECT chunk_number, word_count,
         CASE WHEN sent_to_kindle_at IS NULL THEN 'PENDING' ELSE 'SENT' END as status
  FROM story_chunks
  WHERE story_id = 1
  ORDER BY chunk_number;
"

# View chunk text (first 500 characters)
sqlite3 ./test-review.db "
  SELECT substr(chunk_text, 1, 500)
  FROM story_chunks
  WHERE story_id = 1 AND chunk_number = 1;
"
```

### Download Raw Files

```bash
# Download extracted story content
poetry run modal volume get story-data-dev /data/raw/story_000001/content.txt ./story-content.txt
cat ./story-content.txt

# Download metadata
poetry run modal volume get story-data-dev /data/raw/story_000001/metadata.yaml ./metadata.yaml
cat ./metadata.yaml
```

---

## Step 8: Clean Up Test Data

### Option A: Delete Specific Story

```bash
# Delete the story you just tested
poetry run modal run scripts/manage_dev_db.py::delete_story --story-id 1
```

**Expected output:**
```
🗑️  Deleting Story ID 1: Halfseekers Pt. 6 by pirateaba
   Deleted 5 chunks from database
   Deleted story from database
   Deleted raw files
   Deleted chunk files
   Deleted EPUB files
✅ Story 1 deleted successfully
```

**Verify it's gone:**
```bash
poetry run modal run scripts/manage_dev_db.py::list_stories
```

**Expected:**
```
📭 No stories in database
```

### Option B: Clear All Dev Data

```bash
# Nuclear option - deletes EVERYTHING in dev database
poetry run modal run scripts/manage_dev_db.py::clear_all
```

**Expected output:**
```
⚠️  WARNING: About to delete 1 stories and ALL associated data!
   This will DELETE:
   - All database records
   - All story files
   - All chunk files
   - All EPUB files

🗑️  Clearing database...
   ✅ Deleted 1 stories from database
   ✅ Cleared raw/ directory
   ✅ Cleared chunks/ directory
   ✅ Cleared epubs/ directory

✨ Dev database cleared successfully!
```

### Option C: Delete Entire Volume

```bash
# Complete reset - deletes volume and recreates it
poetry run modal volume delete story-data-dev
poetry run modal volume create story-data-dev
```

**Use this when:**
- You want a completely fresh start
- Database schema has changed
- Volume is corrupted

---

## Step 9: Stop Dev Server

Go back to **Terminal 1** and press `Ctrl+C`:

```
^C
Stopping...
✓ App stopped.
```

---

## Complete Example Session

Here's a complete copy-paste workflow:

```bash
# Terminal 1: Start server
poetry run modal serve main_local.py

# Terminal 2: Submit, test, and cleanup
export SUBMIT_URL="https://your-submit-url-here.modal.run"

# 1. Submit story
curl -X POST "$SUBMIT_URL" -H 'Content-Type: application/json' -d '{
  "url": "https://wanderinginn.com/2025/09/19/halfseekers-pt-6/",
  "title": "Halfseekers Pt. 6",
  "author": "pirateaba"
}'

# 2. Wait 10-30 seconds for processing, then list stories
poetry run modal run scripts/manage_dev_db.py::list_stories

# 3. View story details (replace story-id with actual ID)
poetry run modal run scripts/manage_dev_db.py::view_story --story-id 1

# 4. Read first chunk (replace chunk-id with actual ID)
poetry run modal run scripts/manage_dev_db.py::view_chunk --chunk-id 1

# 5. Test sending
poetry run modal run main_local.py::send_next_chunk

# 6. Verify chunk was marked as sent
poetry run modal run scripts/manage_dev_db.py::view_story --story-id 1

# 7. Clean up
poetry run modal run scripts/manage_dev_db.py::delete_story --story-id 1

# 8. Verify cleanup
poetry run modal run scripts/manage_dev_db.py::list_stories
```

---

## Troubleshooting

### Story Status is "failed"

```bash
# View error message
poetry run modal run scripts/manage_dev_db.py::view_story --story-id 1
```

Check the "Status" field for error details. Common issues:
- URL is not accessible
- Password-protected URL without password
- Website structure changed (selector doesn't match)

### Chunks Look Wrong

**If chunks are too large/small:**
- Check `TARGET_WORDS` in `.env`
- Default is 5000 words

**If chunks have metadata:**
- Content extraction failed
- Check extraction method: should be "agent" or "fallback"
- Agent extraction is better at cleaning metadata

**If chunks cut off mid-sentence:**
- Using SimpleChunker (basic word count)
- Install `claude-agent-sdk` for smarter chunking
- Set `USE_AGENT_CHUNKER=true` in `.env`

### No Stories in Database

**Check processing logs in Terminal 1:**
```
# Look for errors like:
❌ Could not extract story content from email
❌ Processing error: ...
```

**List all stories to check:**
```bash
poetry run modal run scripts/manage_dev_db.py::list_stories
```

### Can't Connect to Modal

```bash
# Re-authenticate
poetry run modal token new

# Check if server is running
# Look for "⚡️ Serving..." in Terminal 1
```

---

## Quick Reference Commands

```bash
# DATABASE INSPECTION
modal run scripts/manage_dev_db.py::list_stories          # List all
modal run scripts/manage_dev_db.py::view_story --story-id N   # View details
modal run scripts/manage_dev_db.py::view_chunk --chunk-id N   # Read chunk
modal run scripts/manage_dev_db.py::stats                 # Statistics

# WORKFLOW
modal serve main_local.py                                 # Start server
modal run main_local.py::send_next_chunk                  # Send next chunk

# CLEANUP
modal run scripts/manage_dev_db.py::delete_story --story-id N  # Delete one
modal run scripts/manage_dev_db.py::clear_all             # Delete all

# DOWNLOAD
modal volume get story-data-dev stories-dev.db ./local.db  # Get database
modal volume ls story-data-dev /data/raw                   # List files
```

---

## Expected Timings

- **Story submission**: < 1 second (returns immediately)
- **Processing**: 10-30 seconds (depends on story length)
- **Chunking**: 5-15 seconds (faster with SimpleChunker)
- **EPUB generation**: 2-5 seconds
- **Database queries**: < 1 second

---

## What Success Looks Like

✅ **Story Status**: "chunked" (not "failed")
✅ **Chunks**: Balanced word counts (~5k words each)
✅ **Content**: Clean HTML, no metadata
✅ **Previews**: Show actual story text
✅ **EPUB**: Generated successfully (10-20 KB)
✅ **Sending**: TEST_MODE shows email details
✅ **Cleanup**: Story deleted, database empty
