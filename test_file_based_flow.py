"""
Test file-based architecture locally.
"""

from file_storage import LocalFileStorage
from database import Database, StoryStatus
from content_extraction_agent import extract_content
from chunker import SimpleChunker
import os
import shutil

def test_file_based_flow():
    """Test the complete file-based workflow locally."""

    # Clean up test data
    if os.path.exists("./local_data"):
        shutil.rmtree("./local_data")
    if os.path.exists("./test_stories.db"):
        os.remove("./test_stories.db")

    # Initialize components
    storage = LocalFileStorage("./local_data")
    db = Database("./test_stories.db")

    # Create test email
    test_email = {
        "message-id": "test-123",
        "subject": "Test Story - Chapter 1",
        "from": "Test Author <test@example.com>",
        "text": """Chapter 1

This is a test story with some content.

It has multiple paragraphs to demonstrate the chunking functionality.

This is the second paragraph. It contains more text to make the story longer.

And here is a third paragraph with even more content to ensure we have enough text for chunking.

""" * 200,  # Make it long enough to chunk
        "html": ""
    }

    print("=" * 80)
    print("Testing File-Based Architecture")
    print("=" * 80)

    # Step 1: Create story record
    print("\n1. Creating story record...")
    story_id = db.create_story(
        email_id=test_email["message-id"],
        title=test_email["subject"]
    )
    print(f"   ✅ Created story ID: {story_id}")

    # Step 2: Extract content and save to files
    print("\n2. Extracting content (using fallback, not agent)...")
    os.environ["USE_AGENT_EXTRACTION"] = "false"  # Skip agent for this test

    result = extract_content(test_email, story_id, storage)
    if not result:
        print("   ❌ Content extraction failed!")
        return False

    content_path, metadata_path, original_email_path = result
    print(f"   ✅ Content saved to: {content_path}")
    print(f"   ✅ Metadata saved to: {metadata_path}")
    print(f"   ✅ Original email saved to: {original_email_path}")

    # Step 3: Update story with paths
    print("\n3. Updating story with file paths...")
    db.update_story_paths(story_id, content_path=content_path, metadata_path=metadata_path)

    # Read metadata
    metadata = storage.read_metadata(metadata_path)
    print(f"   ✅ Title: {metadata['title']}")
    print(f"   ✅ Author: {metadata['author']}")

    # Step 4: Chunk the story
    print("\n4. Chunking story...")
    chunker = SimpleChunker(target_words=500)  # Small chunks for testing
    chunk_manifest_path = chunker.chunk_story_from_file(story_id, content_path, storage)
    print(f"   ✅ Chunk manifest saved to: {chunk_manifest_path}")

    # Update story with manifest
    db.update_story_paths(story_id, chunk_manifest_path=chunk_manifest_path)

    # Step 5: Read chunks and create database records
    print("\n5. Creating database records for chunks...")
    chunk_manifest = storage.read_chunk_manifest(chunk_manifest_path)
    total_words = 0

    for chunk_info in chunk_manifest["chunks"]:
        chunk_path = chunk_info["chunk_path"]
        chunk_text = storage.read_chunk(chunk_path)

        db.create_chunk(
            story_id=story_id,
            chunk_number=chunk_info["chunk_number"],
            total_chunks=chunk_manifest["total_chunks"],
            chunk_text=chunk_text,
            word_count=chunk_info["word_count"],
        )
        total_words += chunk_info["word_count"]
        print(f"   ✅ Chunk {chunk_info['chunk_number']}/{chunk_manifest['total_chunks']}: {chunk_info['word_count']} words")

    db.update_word_count(story_id, total_words)
    db.update_story_status(story_id, StoryStatus.CHUNKED)

    # Step 6: Verify everything
    print("\n6. Verifying file structure...")
    print(f"   📁 Raw directory exists: {storage.raw_path.exists()}")
    print(f"   📁 Chunks directory exists: {storage.chunks_path.exists()}")

    # List files
    story_dir = storage.raw_path / f"story_{story_id:06d}"
    if story_dir.exists():
        print(f"   📄 Story files:")
        for file in sorted(story_dir.iterdir()):
            print(f"      - {file.name}")

    chunks_dir = storage.chunks_path / f"story_{story_id:06d}"
    if chunks_dir.exists():
        print(f"   📄 Chunk files:")
        for file in sorted(chunks_dir.iterdir()):
            print(f"      - {file.name}")

    # Step 7: Verify database
    print("\n7. Verifying database records...")
    story = db.get_story_by_email_id(test_email["message-id"])
    print(f"   ✅ Story status: {story['status']}")
    print(f"   ✅ Total words: {story['word_count']}")
    print(f"   ✅ Content path: {story['content_path']}")
    print(f"   ✅ Metadata path: {story['metadata_path']}")

    chunks = db.get_story_chunks(story_id)
    print(f"   ✅ Chunks in database: {len(chunks)}")

    print("\n" + "=" * 80)
    print("✅ File-based architecture test PASSED!")
    print("=" * 80)

    return True

if __name__ == "__main__":
    success = test_file_based_flow()
    exit(0 if success else 1)
