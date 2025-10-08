"""
Test chunking with a longer story that will need multiple chunks.
"""

from src.file_storage import LocalFileStorage
from src.database import Database, StoryStatus
from src.content_extraction_agent import extract_content
from src.chunker import AgentChunker
import os
import shutil

def test_multi_chunk_story():
    """Test chunking on a longer story that needs multiple chunks."""

    # Clean up test data
    if os.path.exists("./local_data"):
        shutil.rmtree("./local_data")
    if os.path.exists("./test_stories.db"):
        os.remove("./test_stories.db")

    # Initialize components
    storage = LocalFileStorage("./local_data")
    db = Database("./test_stories.db")

    # Read and combine multiple stories to create a longer text
    with open("examples/inputs/pale-lights-example-1.txt", 'r') as f:
        part1 = f.read()

    # Create a longer story by repeating with scene breaks
    story_content = part1 + "\n\n───\n\n" + part1 + "\n\n───\n\n" + part1

    # Create test email
    test_email = {
        "message-id": "test-long-story",
        "subject": "Long Story Test - Multiple Chunks",
        "from": "Test Author <test@example.com>",
        "text": story_content,
        "html": ""
    }

    word_count = len(story_content.split())
    expected_chunks = round(word_count / 8000)

    print("=" * 80)
    print("Testing Multi-Chunk Story with Agent Recaps")
    print("=" * 80)
    print(f"Story length: {word_count} words")
    print(f"Expected chunks: ~{expected_chunks} (at 8000 words/chunk)")
    print()

    # Step 1: Create story record
    print("1. Creating story record...")
    story_id = db.create_story(
        email_id=test_email["message-id"],
        title=test_email["subject"]
    )

    # Step 2: Extract content
    print("\n2. Extracting content...")
    os.environ["USE_AGENT_EXTRACTION"] = "false"
    result = extract_content(test_email, story_id, storage)

    if not result:
        print("   ❌ Content extraction failed!")
        return False

    content_path, metadata_path, original_email_path = result
    db.update_story_paths(story_id, content_path=content_path, metadata_path=metadata_path)

    # Step 3: Chunk with agent
    print("\n3. Chunking story with AgentChunker (8000 word target)...")
    chunker = AgentChunker(target_words=8000, fallback_to_simple=True)
    chunk_manifest_path = chunker.chunk_story_from_file(story_id, content_path, storage)

    # Step 4: Show chunk details
    print("\n4. Chunk details:")
    chunk_manifest = storage.read_chunk_manifest(chunk_manifest_path)

    print(f"   Total chunks: {chunk_manifest['total_chunks']}")
    print(f"   Chunking strategy: {chunk_manifest['chunking_strategy']}")
    print()

    for i, chunk_info in enumerate(chunk_manifest["chunks"], 1):
        chunk_path = chunk_info["chunk_path"]
        chunk_text = storage.read_chunk(chunk_path)

        has_recap = "Previously:" in chunk_text
        recap_indicator = " (with recap)" if has_recap else ""

        print(f"   Chunk {i}/{chunk_manifest['total_chunks']}: {chunk_info['word_count']} words{recap_indicator}")

        # Show recap if present
        if has_recap:
            # Extract recap text
            parts = chunk_text.split("───────────────────────────────────────")
            if len(parts) >= 2:
                recap_section = parts[1]
                recap_text = recap_section.replace("*Previously:*", "").replace(">", "").strip()
                print(f"\n      📖 RECAP:")
                print(f"      {recap_text}")
                print()

        # Show beginning of actual content
        content_start = chunk_text.split("───────────────────────────────────────")[-1].strip()[:250]
        print(f"      Starts: {content_start}...")
        print()

    total_words = sum(c["word_count"] for c in chunk_manifest["chunks"])
    print(f"   Total words (including recaps): {total_words}")
    print(f"   Original story: {word_count} words")
    print(f"   Overhead from recaps: {total_words - word_count} words")

    print("\n" + "=" * 80)
    print("✅ Multi-chunk story test PASSED!")
    print("=" * 80)

    return True

if __name__ == "__main__":
    success = test_multi_chunk_story()
    exit(0 if success else 1)
