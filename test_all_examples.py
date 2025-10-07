"""
Test chunking across all example stories and show comparison.
"""

import os
import glob
from file_storage import LocalFileStorage
from database import Database, StoryStatus
from content_extraction_agent import extract_content
from chunker import AgentChunker, SimpleChunker
import shutil

def test_story(story_file: str, use_agent: bool = True):
    """Test a single story and return results."""

    # Read story
    with open(story_file, 'r') as f:
        story_content = f.read()

    story_name = os.path.basename(story_file).replace('.txt', '')
    word_count = len(story_content.split())

    # Skip very short stories
    if word_count < 100:
        return {
            'name': story_name,
            'word_count': word_count,
            'chunks': None,
            'error': 'Too short (< 100 words)'
        }

    # Initialize components (fresh each time)
    storage = LocalFileStorage("./local_data")
    db = Database("./test_stories.db")

    # Create test email
    test_email = {
        "message-id": f"test-{story_name}",
        "subject": f"{story_name}",
        "from": "Test Author <test@example.com>",
        "text": story_content,
        "html": ""
    }

    try:
        # Create story record
        story_id = db.create_story(
            email_id=test_email["message-id"],
            title=test_email["subject"]
        )

        # Extract content (skip agent)
        os.environ["USE_AGENT_EXTRACTION"] = "false"
        result = extract_content(test_email, story_id, storage)

        if not result:
            return {
                'name': story_name,
                'word_count': word_count,
                'chunks': None,
                'error': 'Extraction failed'
            }

        content_path, metadata_path, original_email_path = result
        db.update_story_paths(story_id, content_path=content_path, metadata_path=metadata_path)

        # Chunk the story
        if use_agent:
            chunker = AgentChunker(target_words=8000, fallback_to_simple=True)
        else:
            chunker = SimpleChunker(target_words=8000)

        chunk_manifest_path = chunker.chunk_story_from_file(story_id, content_path, storage)
        chunk_manifest = storage.read_chunk_manifest(chunk_manifest_path)

        # Collect chunk info
        chunk_details = []
        for chunk_info in chunk_manifest["chunks"]:
            chunk_path = chunk_info["chunk_path"]
            chunk_text = storage.read_chunk(chunk_path)
            has_recap = "Previously:" in chunk_text

            chunk_details.append({
                'number': chunk_info['chunk_number'],
                'words': chunk_info['word_count'],
                'has_recap': has_recap
            })

        return {
            'name': story_name,
            'word_count': word_count,
            'chunks': chunk_details,
            'total_chunks': len(chunk_details),
            'strategy': chunk_manifest.get('chunking_strategy', 'Unknown'),
            'error': None
        }

    except Exception as e:
        return {
            'name': story_name,
            'word_count': word_count,
            'chunks': None,
            'error': str(e)
        }

def main():
    """Test all example stories and display results."""

    # Clean up
    if os.path.exists("./local_data"):
        shutil.rmtree("./local_data")
    if os.path.exists("./test_stories.db"):
        os.remove("./test_stories.db")

    # Find all example stories
    story_files = sorted(glob.glob("examples/inputs/*.txt"))

    if not story_files:
        print("❌ No example stories found in examples/inputs/")
        return

    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 25 + "CHUNKING TEST SUMMARY" + " " * 32 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    print(f"Testing {len(story_files)} stories with AgentChunker (8000 word target)")
    print()

    results = []

    for i, story_file in enumerate(story_files, 1):
        story_name = os.path.basename(story_file).replace('.txt', '')
        print(f"[{i}/{len(story_files)}] Testing {story_name}...", end=" ", flush=True)

        result = test_story(story_file, use_agent=True)
        results.append(result)

        if result['error']:
            print(f"⚠️  {result['error']}")
        else:
            print(f"✅ {result['total_chunks']} chunk(s)")

    print()
    print("═" * 80)
    print()

    # Display detailed results
    print("DETAILED RESULTS:")
    print()

    for result in results:
        if result['error']:
            print(f"❌ {result['name']}")
            print(f"   Words: {result['word_count']}")
            print(f"   Error: {result['error']}")
            print()
            continue

        print(f"📖 {result['name']}")
        print(f"   Words: {result['word_count']}")
        print(f"   Chunks: {result['total_chunks']}")
        print(f"   Strategy: {result['strategy']}")

        for chunk in result['chunks']:
            recap_indicator = " (with recap)" if chunk['has_recap'] else ""
            print(f"      • Chunk {chunk['number']}: {chunk['words']} words{recap_indicator}")

        total_words = sum(c['words'] for c in result['chunks'])
        overhead = total_words - result['word_count']
        if overhead > 0:
            print(f"   Recap overhead: +{overhead} words ({overhead / result['word_count'] * 100:.1f}%)")

        print()

    print("═" * 80)
    print()

    # Summary stats
    successful = [r for r in results if not r['error']]

    if successful:
        total_stories = len(successful)
        single_chunk = sum(1 for r in successful if r['total_chunks'] == 1)
        multi_chunk = total_stories - single_chunk
        avg_chunk_size = sum(
            sum(c['words'] for c in r['chunks']) / r['total_chunks']
            for r in successful
        ) / total_stories

        print("STATISTICS:")
        print(f"  ✅ Successful: {total_stories}/{len(results)}")
        print(f"  📄 Single-chunk stories: {single_chunk}")
        print(f"  📚 Multi-chunk stories: {multi_chunk}")
        print(f"  📊 Average chunk size: {avg_chunk_size:.0f} words")
        print()

        # Chunk distribution
        chunk_counts = {}
        for r in successful:
            count = r['total_chunks']
            chunk_counts[count] = chunk_counts.get(count, 0) + 1

        print("CHUNK DISTRIBUTION:")
        for count in sorted(chunk_counts.keys()):
            bar = "█" * chunk_counts[count]
            print(f"  {count} chunk(s): {bar} ({chunk_counts[count]} stories)")
        print()

    print("═" * 80)
    print()
    print("💡 Test complete! Check ./local_data/ for generated files.")
    print()

if __name__ == "__main__":
    main()
