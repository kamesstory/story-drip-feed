"""
Test chunking with a real story example.
"""

from src.file_storage import LocalFileStorage
from src.database import Database, StoryStatus
from src.content_extraction_agent import extract_content
from src.chunker import AgentChunker, SimpleChunker
import os
import shutil

def test_real_story_chunking(story_file: str, use_agent: bool = True):
    """Test chunking on a real story."""

    # Clean up test data
    if os.path.exists("./local_data"):
        shutil.rmtree("./local_data")
    if os.path.exists("./test_stories.db"):
        os.remove("./test_stories.db")

    # Initialize components
    storage = LocalFileStorage("./local_data")
    db = Database("./test_stories.db")

    # Read story from file
    with open(story_file, 'r') as f:
        story_content = f.read()

    story_title = os.path.basename(story_file).replace('.txt', '')

    # Create test email with the story content
    test_email = {
        "message-id": f"test-{story_title}",
        "subject": f"{story_title} - Chapter 1",
        "from": "Test Author <test@example.com>",
        "text": story_content,
        "html": ""
    }

    print("=" * 80)
    print(f"Testing Real Story Chunking: {story_title}")
    print("=" * 80)
    print(f"Story length: {len(story_content.split())} words")
    print(f"Using {'Agent' if use_agent else 'Simple'} chunker with 8000 word target")
    print()

    # Step 1: Create story record
    print("1. Creating story record...")
    story_id = db.create_story(
        email_id=test_email["message-id"],
        title=test_email["subject"]
    )

    # Step 2: Extract content (skip agent, use fallback)
    print("\n2. Extracting content...")
    os.environ["USE_AGENT_EXTRACTION"] = "false"
    result = extract_content(test_email, story_id, storage)

    if not result:
        print("   ❌ Content extraction failed!")
        return False

    content_path, metadata_path, original_email_path = result
    db.update_story_paths(story_id, content_path=content_path, metadata_path=metadata_path)

    metadata = storage.read_metadata(metadata_path)
    print(f"   ✅ Title: {metadata['title']}")

    # Step 3: Chunk the story
    print("\n3. Chunking story...")
    if use_agent:
        chunker = AgentChunker(target_words=8000, fallback_to_simple=True)
    else:
        chunker = SimpleChunker(target_words=8000)

    chunk_manifest_path = chunker.chunk_story_from_file(story_id, content_path, storage)
    db.update_story_paths(story_id, chunk_manifest_path=chunk_manifest_path)

    # Step 4: Read chunks and show details
    print("\n4. Chunk details:")
    chunk_manifest = storage.read_chunk_manifest(chunk_manifest_path)

    print(f"   Total chunks: {chunk_manifest['total_chunks']}")
    print(f"   Chunking strategy: {chunk_manifest['chunking_strategy']}")
    print()

    total_words = 0
    for i, chunk_info in enumerate(chunk_manifest["chunks"], 1):
        chunk_path = chunk_info["chunk_path"]
        chunk_text = storage.read_chunk(chunk_path)

        # Check for recap
        has_recap = "Previously:" in chunk_text
        recap_indicator = " (with recap)" if has_recap else ""

        print(f"   Chunk {i}/{chunk_manifest['total_chunks']}: {chunk_info['word_count']} words{recap_indicator}")

        # Show recap if present
        if has_recap:
            recap_section = chunk_text.split("───────────────────────────────────────")[1]
            recap_text = recap_section.replace("*Previously:*", "").replace(">", "").strip()
            print(f"      Recap: {recap_text[:150]}..." if len(recap_text) > 150 else f"      Recap: {recap_text}")

        # Show first few lines of actual content
        content_start = chunk_text.split("───────────────────────────────────────")[-1].strip()[:200]
        print(f"      Starts: {content_start}...")
        print()

        total_words += chunk_info["word_count"]

    print(f"   Total words (including recaps): {total_words}")

    # Create database records
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

    db.update_word_count(story_id, total_words)
    db.update_story_status(story_id, StoryStatus.CHUNKED)

    print("\n" + "=" * 80)
    print("✅ Real story chunking test PASSED!")
    print("=" * 80)

    return True

if __name__ == "__main__":
    import sys

    # Default to pale-lights example
    story_file = "examples/inputs/pale-lights-example-1.txt"
    use_agent = True

    if len(sys.argv) > 1:
        story_file = sys.argv[1]

    if len(sys.argv) > 2:
        use_agent = sys.argv[2].lower() in ["true", "1", "agent"]

    print(f"Testing with: {story_file}")
    print(f"Chunker: {'Agent' if use_agent else 'Simple'}")
    print()

    success = test_real_story_chunking(story_file, use_agent)
    exit(0 if success else 1)
