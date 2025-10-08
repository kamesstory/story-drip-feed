#!/usr/bin/env python3
"""
Script to inspect the local database and see pending chunks.

Usage:
    poetry run python inspect_db.py
"""
import modal
from src.database import Database, StoryStatus

app = modal.App("inspect-db")

# Use same volume and image as main app
volume = modal.Volume.from_name("story-data", create_if_missing=True)

image = (
    modal.Image.debian_slim()
    .pip_install("python-dateutil")
    .add_local_file("src/database.py", "/root/src/database.py")
)


@app.function(
    image=image,
    volumes={"/data": volume},
)
def inspect_database():
    """Inspect the database and show pending chunks."""
    db = Database("/data/stories.db")

    print("\n" + "="*80)
    print("DATABASE INSPECTION")
    print("="*80)

    # Get all stories
    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT id, title, author, status, word_count,
                   received_at, processed_at, sent_at
            FROM stories
            ORDER BY received_at DESC
        """)
        stories = [dict(row) for row in cursor.fetchall()]

    print(f"\n📚 Total Stories: {len(stories)}")
    print("-"*80)

    for story in stories:
        print(f"\nStory ID: {story['id']}")
        print(f"  Title: {story['title']}")
        print(f"  Author: {story['author']}")
        print(f"  Status: {story['status']}")
        print(f"  Word Count: {story['word_count']}")
        print(f"  Received: {story['received_at']}")

        # Get chunks for this story
        chunks = db.get_story_chunks(story['id'])
        if chunks:
            print(f"\n  Chunks: {len(chunks)} total")
            for chunk in chunks:
                sent_status = "✅ SENT" if chunk['sent_to_kindle_at'] else "⏳ PENDING"
                print(f"    - Part {chunk['chunk_number']}/{chunk['total_chunks']}: {chunk['word_count']} words {sent_status}")
                if chunk['sent_to_kindle_at']:
                    print(f"      Sent: {chunk['sent_to_kindle_at']}")

    # Show next chunk to be sent
    print("\n" + "="*80)
    next_chunk = db.get_next_unsent_chunk()
    if next_chunk:
        print("📬 NEXT CHUNK TO BE SENT:")
        print(f"  Story ID: {next_chunk['story_id']}")
        print(f"  Chunk ID: {next_chunk['id']}")
        print(f"  Title: {next_chunk['title']}")
        print(f"  Author: {next_chunk['author']}")
        print(f"  Part: {next_chunk['chunk_number']}/{next_chunk['total_chunks']}")
        print(f"  Word Count: {next_chunk['word_count']}")
        print(f"  Preview: {next_chunk['chunk_text'][:200]}...")
    else:
        print("✨ No pending chunks - all caught up!")

    print("="*80 + "\n")


@app.local_entrypoint()
def main():
    """Run the inspection."""
    inspect_database.remote()
