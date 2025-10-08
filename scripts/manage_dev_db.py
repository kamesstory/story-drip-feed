#!/usr/bin/env python3
"""
CLI management tool for dev database.

Usage:
    modal run scripts/manage_dev_db.py::list_stories
    modal run scripts/manage_dev_db.py::delete_story --story-id 1
    modal run scripts/manage_dev_db.py::clear_all
    modal run scripts/manage_dev_db.py::view_chunk --chunk-id 1
"""
import modal
from src.database import Database, StoryStatus

app = modal.App("manage-dev-db")

# Use dev volume
volume = modal.Volume.from_name("story-data-dev", create_if_missing=True)

image = (
    modal.Image.debian_slim()
    .pip_install("python-dateutil")
    .add_local_file("src/database.py", "/root/src/database.py")
    .add_local_file("src/file_storage.py", "/root/src/file_storage.py")
)


@app.function(
    image=image,
    volumes={"/data": volume},
)
def list_stories():
    """List all stories in dev database with details."""
    db = Database("/data/stories-dev.db")

    print("\n" + "="*80)
    print("DEV DATABASE - ALL STORIES")
    print("="*80)

    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT id, title, author, status, word_count, received_at,
                   (SELECT COUNT(*) FROM story_chunks WHERE story_id = stories.id) as total_chunks,
                   (SELECT COUNT(*) FROM story_chunks WHERE story_id = stories.id AND sent_to_kindle_at IS NOT NULL) as sent_chunks
            FROM stories
            ORDER BY received_at DESC
        """)
        stories = cursor.fetchall()

    if not stories:
        print("\n📭 No stories in database")
        print("="*80 + "\n")
        return

    print(f"\n📚 Total Stories: {len(stories)}\n")

    for story in stories:
        story_id, title, author, status, word_count, received_at, total_chunks, sent_chunks = story
        print(f"Story ID: {story_id}")
        print(f"  Title: {title}")
        print(f"  Author: {author}")
        print(f"  Status: {status}")
        print(f"  Words: {word_count}")
        print(f"  Chunks: {sent_chunks}/{total_chunks} sent")
        print(f"  Received: {received_at}")
        print()

    # Show next to send
    next_chunk = db.get_next_unsent_chunk()
    if next_chunk:
        print("📬 NEXT CHUNK TO SEND:")
        print(f"  Story: {next_chunk['title']}")
        print(f"  Part: {next_chunk['chunk_number']}/{next_chunk['total_chunks']}")
        print(f"  Words: {next_chunk['word_count']}")
    else:
        print("✨ All chunks sent!")

    print("="*80 + "\n")


@app.function(
    image=image,
    volumes={"/data": volume},
)
def delete_story(story_id: int):
    """Delete a story and all its chunks from dev database."""
    from src.file_storage import FileStorage

    db = Database("/data/stories-dev.db")
    storage = FileStorage("/data")

    # Get story details first
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT title, author FROM stories WHERE id = ?", (story_id,))
        story = cursor.fetchone()

    if not story:
        print(f"❌ Story ID {story_id} not found")
        return

    title, author = story
    print(f"\n🗑️  Deleting Story ID {story_id}: {title} by {author}")

    # Delete chunks
    with db.get_connection() as conn:
        cursor = conn.execute("DELETE FROM story_chunks WHERE story_id = ?", (story_id,))
        deleted_chunks = cursor.rowcount
        print(f"   Deleted {deleted_chunks} chunks from database")

        # Delete story
        conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))
        print(f"   Deleted story from database")

    # Delete files
    try:
        import shutil
        story_id_str = f"{story_id:06d}"

        # Delete raw files
        raw_path = f"/data/raw/story_{story_id_str}"
        if storage.get_absolute_path(raw_path).exists():
            shutil.rmtree(raw_path)
            print(f"   Deleted raw files")

        # Delete chunks
        chunks_path = f"/data/chunks/story_{story_id_str}"
        if storage.get_absolute_path(chunks_path).exists():
            shutil.rmtree(chunks_path)
            print(f"   Deleted chunk files")

        # Delete EPUBs
        epub_pattern = f"/data/epubs/story_{story_id_str}_chunk_*.epub"
        import glob
        for epub_file in glob.glob(epub_pattern):
            storage.get_absolute_path(epub_file).unlink()
        print(f"   Deleted EPUB files")

    except Exception as e:
        print(f"   ⚠️  Warning: Could not delete some files: {e}")

    volume.commit()
    print(f"✅ Story {story_id} deleted successfully\n")


@app.function(
    image=image,
    volumes={"/data": volume},
)
def clear_all():
    """Delete ALL stories and data from dev database. USE WITH CAUTION!"""
    db = Database("/data/stories-dev.db")

    # Count stories first
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM stories")
        count = cursor.fetchone()[0]

    if count == 0:
        print("\n📭 Database is already empty\n")
        return

    print(f"\n⚠️  WARNING: About to delete {count} stories and ALL associated data!")
    print("   This will DELETE:")
    print("   - All database records")
    print("   - All story files")
    print("   - All chunk files")
    print("   - All EPUB files")
    print("\n🗑️  Clearing database...")

    # Delete all from database
    with db.get_connection() as conn:
        conn.execute("DELETE FROM story_chunks")
        conn.execute("DELETE FROM stories")
        print(f"   ✅ Deleted {count} stories from database")

    # Delete all files
    try:
        from src.file_storage import FileStorage
        import shutil

        storage = FileStorage("/data")

        # Clear directories
        for dir_name in ["raw", "chunks", "epubs"]:
            dir_path = storage.get_absolute_path(f"/{dir_name}")
            if dir_path.exists():
                shutil.rmtree(dir_path)
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"   ✅ Cleared {dir_name}/ directory")

    except Exception as e:
        print(f"   ⚠️  Warning: Could not delete some files: {e}")

    volume.commit()
    print(f"\n✨ Dev database cleared successfully!\n")


@app.function(
    image=image,
    volumes={"/data": volume},
)
def view_chunk(chunk_id: int):
    """View the full text of a specific chunk."""
    db = Database("/data/stories-dev.db")

    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT sc.chunk_text, sc.chunk_number, sc.total_chunks, sc.word_count,
                   s.title, s.author
            FROM story_chunks sc
            JOIN stories s ON sc.story_id = s.id
            WHERE sc.id = ?
        """, (chunk_id,))
        chunk = cursor.fetchone()

    if not chunk:
        print(f"❌ Chunk ID {chunk_id} not found")
        return

    chunk_text, chunk_number, total_chunks, word_count, title, author = chunk

    print("\n" + "="*80)
    print(f"CHUNK {chunk_number}/{total_chunks}: {title}")
    print(f"By {author} | {word_count} words")
    print("="*80)
    print(chunk_text)
    print("="*80 + "\n")


@app.function(
    image=image,
    volumes={"/data": volume},
)
def view_story(story_id: int):
    """View story details and all its chunks."""
    db = Database("/data/stories-dev.db")

    # Get story
    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT id, title, author, status, word_count, received_at,
                   content_path, extraction_method
            FROM stories
            WHERE id = ?
        """, (story_id,))
        story = cursor.fetchone()

    if not story:
        print(f"❌ Story ID {story_id} not found")
        return

    story_id, title, author, status, word_count, received_at, content_path, extraction_method = story

    print("\n" + "="*80)
    print(f"STORY ID {story_id}: {title}")
    print("="*80)
    print(f"Author: {author}")
    print(f"Status: {status}")
    print(f"Total Words: {word_count}")
    print(f"Received: {received_at}")
    print(f"Extraction Method: {extraction_method or 'N/A'}")
    print(f"Content Path: {content_path or 'N/A'}")

    # Get chunks
    chunks = db.get_story_chunks(story_id)
    if chunks:
        print(f"\nChunks: {len(chunks)} total")
        print("-"*80)
        for chunk in chunks:
            sent_status = "✅ SENT" if chunk['sent_to_kindle_at'] else "⏳ PENDING"
            print(f"  Chunk {chunk['id']}: Part {chunk['chunk_number']}/{chunk['total_chunks']} | {chunk['word_count']} words | {sent_status}")
            if chunk['sent_to_kindle_at']:
                print(f"    Sent: {chunk['sent_to_kindle_at']}")
            print(f"    Preview: {chunk['chunk_text'][:100]}...")
            print()
    else:
        print("\n⚠️  No chunks found for this story")

    print("="*80 + "\n")


@app.function(
    image=image,
    volumes={"/data": volume},
)
def stats():
    """Show database statistics."""
    db = Database("/data/stories-dev.db")

    with db.get_connection() as conn:
        # Total stories by status
        cursor = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM stories
            GROUP BY status
        """)
        status_counts = cursor.fetchall()

        # Total chunks
        cursor = conn.execute("SELECT COUNT(*) FROM story_chunks")
        total_chunks = cursor.fetchone()[0]

        # Pending chunks
        cursor = conn.execute("SELECT COUNT(*) FROM story_chunks WHERE sent_to_kindle_at IS NULL")
        pending_chunks = cursor.fetchone()[0]

        # Sent chunks
        sent_chunks = total_chunks - pending_chunks

        # Total words
        cursor = conn.execute("SELECT SUM(word_count) FROM stories")
        total_words = cursor.fetchone()[0] or 0

    print("\n" + "="*80)
    print("DEV DATABASE STATISTICS")
    print("="*80)

    print("\n📊 Stories by Status:")
    if status_counts:
        for status, count in status_counts:
            print(f"  {status}: {count}")
    else:
        print("  (none)")

    print(f"\n📚 Chunks:")
    print(f"  Total: {total_chunks}")
    print(f"  Sent: {sent_chunks}")
    print(f"  Pending: {pending_chunks}")

    print(f"\n📝 Total Words: {total_words:,}")

    print("="*80 + "\n")


@app.local_entrypoint()
def main():
    """Show help."""
    print("""
Dev Database Management Tool

Available commands:
  modal run scripts/manage_dev_db.py::list_stories
  modal run scripts/manage_dev_db.py::view_story --story-id 1
  modal run scripts/manage_dev_db.py::view_chunk --chunk-id 1
  modal run scripts/manage_dev_db.py::delete_story --story-id 1
  modal run scripts/manage_dev_db.py::clear_all
  modal run scripts/manage_dev_db.py::stats

Use 'modal volume ls story-data-dev' to browse files directly.
Use 'modal volume get story-data-dev stories-dev.db ./local.db' to download database.
    """)
