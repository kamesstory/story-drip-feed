"""
Test the complete end-to-end pipeline from email ingestion to Kindle sending.
"""

import os
import shutil
from file_storage import LocalFileStorage
from database import Database, StoryStatus
from content_extraction_agent import extract_content
from chunker import AgentChunker, SimpleChunker
from epub_generator import EPUBGenerator
from kindle_sender import KindleSender

def test_full_pipeline():
    """Test complete workflow: email → extract → chunk → EPUB → (simulate) Kindle send"""

    print("=" * 80)
    print("FULL PIPELINE TEST: Email → Extract → Chunk → EPUB → Kindle")
    print("=" * 80)
    print()

    # Clean up
    if os.path.exists("./local_data"):
        shutil.rmtree("./local_data")
    if os.path.exists("./test_stories.db"):
        os.remove("./test_stories.db")

    # Initialize
    storage = LocalFileStorage("./local_data")
    db = Database("./test_stories.db")

    # Read real story
    with open("examples/inputs/pale-lights-example-1.txt", 'r') as f:
        story_content = f.read()

    # Simulate email webhook
    email_data = {
        "message-id": "test-full-pipeline-001",
        "subject": "Pale Lights - Chapter 27",
        "from": "ErraticErrata <author@patreon.com>",
        "text": story_content,
        "html": ""
    }

    print("📧 STEP 1: Email Ingestion")
    print("-" * 80)
    print(f"Subject: {email_data['subject']}")
    print(f"From: {email_data['from']}")
    print(f"Length: {len(story_content.split())} words")
    print()

    # Check for duplicate
    existing = db.get_story_by_email_id(email_data["message-id"])
    if existing:
        print("❌ Story already processed (duplicate detection working)")
        return False

    # Create story record
    story_id = db.create_story(
        email_id=email_data["message-id"],
        title=email_data["subject"]
    )
    db.update_story_status(story_id, StoryStatus.PROCESSING)

    print("📄 STEP 2: Content Extraction")
    print("-" * 80)

    # Extract content with agent for metadata cleaning
    os.environ["USE_AGENT_EXTRACTION"] = "true"
    result = extract_content(email_data, story_id, storage)

    if not result:
        print("❌ Extraction failed")
        return False

    content_path, metadata_path, original_email_path = result
    metadata = storage.read_metadata(metadata_path)

    print(f"✅ Title: {metadata['title']}")
    print(f"✅ Author: {metadata['author']}")
    print(f"✅ Files saved:")
    print(f"   - {content_path}")
    print(f"   - {metadata_path}")
    print(f"   - {original_email_path}")
    print()

    # Update story
    db.update_story_paths(story_id, content_path=content_path, metadata_path=metadata_path)

    print("✂️  STEP 3: Chunking")
    print("-" * 80)

    # Chunk (use simple for speed)
    chunker = SimpleChunker(target_words=8000)
    chunk_manifest_path = chunker.chunk_story_from_file(story_id, content_path, storage)
    chunk_manifest = storage.read_chunk_manifest(chunk_manifest_path)

    print(f"✅ Created {chunk_manifest['total_chunks']} chunk(s)")
    print(f"✅ Manifest: {chunk_manifest_path}")

    # Save chunks to database
    db.update_story_paths(story_id, chunk_manifest_path=chunk_manifest_path)

    total_words = 0
    for chunk_info in chunk_manifest["chunks"]:
        chunk_path = chunk_info["chunk_path"]
        chunk_text = storage.read_chunk(chunk_path)

        chunk_id = db.create_chunk(
            story_id=story_id,
            chunk_number=chunk_info["chunk_number"],
            total_chunks=chunk_manifest["total_chunks"],
            chunk_text=chunk_text,
            word_count=chunk_info["word_count"],
        )
        total_words += chunk_info["word_count"]

        print(f"   • Chunk {chunk_info['chunk_number']}/{chunk_manifest['total_chunks']}: "
              f"{chunk_info['word_count']} words (DB ID: {chunk_id})")

    db.update_word_count(story_id, total_words)
    db.update_story_status(story_id, StoryStatus.CHUNKED)

    print()
    print("📚 STEP 4: EPUB Generation")
    print("-" * 80)

    # Get next unsent chunk (should be first chunk)
    next_chunk = db.get_next_unsent_chunk()

    if not next_chunk:
        print("❌ No unsent chunks found")
        return False

    print(f"✅ Next chunk to send: {next_chunk['chunk_number']}/{next_chunk['total_chunks']}")
    print(f"   Title: {next_chunk['title']}")
    print(f"   Words: {next_chunk['word_count']}")
    print(f"   Has chunk_text: {'chunk_text' in next_chunk and next_chunk['chunk_text']}")

    # Generate EPUB
    epub_gen = EPUBGenerator("./local_data/epubs")
    epub_path = epub_gen.create_epub(
        text=next_chunk["chunk_text"],
        title=next_chunk["title"],
        author=next_chunk["author"],
        chunk_number=next_chunk["chunk_number"],
        total_chunks=next_chunk["total_chunks"],
    )

    print(f"✅ EPUB created: {epub_path}")

    # Verify EPUB exists
    if not os.path.exists(epub_path):
        print(f"❌ EPUB file not found: {epub_path}")
        return False

    epub_size = os.path.getsize(epub_path)
    print(f"✅ EPUB size: {epub_size:,} bytes")
    print()

    print("📮 STEP 5: Kindle Sending (Simulation)")
    print("-" * 80)

    # Set test mode
    os.environ["TEST_MODE"] = "true"
    os.environ["KINDLE_EMAIL"] = "test@kindle.com"
    os.environ["SMTP_HOST"] = "smtp.gmail.com"
    os.environ["SMTP_PORT"] = "587"
    os.environ["SMTP_USER"] = "test@gmail.com"
    os.environ["SMTP_PASSWORD"] = "test-password"

    try:
        kindle_sender = KindleSender.from_env()

        # In TEST_MODE, this will just log instead of sending
        success = kindle_sender.send_epubs(
            epub_paths=[epub_path],
            title=next_chunk["title"],
            subject=f"{next_chunk['title']} - Part {next_chunk['chunk_number']}/{next_chunk['total_chunks']}",
        )

        if success:
            print(f"✅ Would send to: {os.environ['KINDLE_EMAIL']}")
            print(f"✅ Subject: {next_chunk['title']} - Part {next_chunk['chunk_number']}/{next_chunk['total_chunks']}")
            print(f"✅ Attachment: {os.path.basename(epub_path)}")

            # Mark as sent in database
            db.mark_chunk_sent(next_chunk["id"])
            print(f"✅ Chunk marked as sent in database")

            # Check if all chunks sent
            all_chunks = db.get_story_chunks(story_id)
            all_sent = all([chunk["sent_to_kindle_at"] for chunk in all_chunks])

            if all_sent:
                db.update_story_status(story_id, StoryStatus.SENT)
                print(f"✅ All chunks sent, story marked as SENT")
            else:
                remaining = sum(1 for chunk in all_chunks if not chunk["sent_to_kindle_at"])
                print(f"📊 {remaining} chunk(s) remaining to send")
        else:
            print(f"❌ Sending failed")
            return False

    except Exception as e:
        print(f"❌ Error during send: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()
    print("=" * 80)
    print("✅ FULL PIPELINE TEST PASSED!")
    print("=" * 80)
    print()
    print("SUMMARY:")
    print(f"  ✅ Story extracted from email")
    print(f"  ✅ Content cleaned (metadata removed)")
    print(f"  ✅ Story chunked into {chunk_manifest['total_chunks']} part(s)")
    print(f"  ✅ EPUB generated ({epub_size:,} bytes)")
    print(f"  ✅ Chunk marked for Kindle delivery")
    print(f"  ✅ Database tracking working")
    print()
    print("NEXT STEPS:")
    print(f"  • Deploy to Modal: poetry run modal deploy main.py")
    print(f"  • Set up email webhook pointing to Modal endpoint")
    print(f"  • Daily sends happen automatically at 8am UTC")
    print(f"  • Check status: poetry run modal run inspect_db.py")
    print()

    return True

if __name__ == "__main__":
    success = test_full_pipeline()
    exit(0 if success else 1)
