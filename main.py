import modal
import os
import uuid
from typing import Dict, Any

from database import Database, StoryStatus
from email_parser import EmailParser
from chunker import chunk_story, LLMChunker, SimpleChunker, AgentChunker
from content_extraction_agent import extract_content
from epub_generator import EPUBGenerator
from kindle_sender import KindleSender
from file_storage import FileStorage

# Create Modal app
app = modal.App("nighttime-story-prep")

# Create persistent volume for database and EPUBs
volume = modal.Volume.from_name("story-data", create_if_missing=True)

# Define image with dependencies and local Python files
image = (
    modal.Image.debian_slim()
    .pip_install(
        "ebooklib",
        "beautifulsoup4",
        "lxml",
        "python-dateutil",
        "requests",
        "anthropic",
        "pyyaml",
    )
    .add_local_file("database.py", "/root/database.py")
    .add_local_file("email_parser.py", "/root/email_parser.py")
    .add_local_file("chunker.py", "/root/chunker.py")
    .add_local_file("content_extraction_agent.py", "/root/content_extraction_agent.py")
    .add_local_file("epub_generator.py", "/root/epub_generator.py")
    .add_local_file("kindle_sender.py", "/root/kindle_sender.py")
    .add_local_file("file_storage.py", "/root/file_storage.py")
    .add_local_file("examples/inputs/pale-lights-example-1.txt", "/root/examples/inputs/pale-lights-example-1.txt")
)


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("story-prep-secrets")],
    timeout=600,
)
def process_story(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main processing function for incoming stories.

    Args:
        email_data: Dict with email contents (html, text, subject, from, message-id)

    Returns:
        Dict with processing status and details
    """
    db = Database("/data/stories.db")
    storage = FileStorage("/data")
    email_id = email_data.get("message-id", email_data.get("Message-ID", "unknown"))

    story_id = None
    try:
        # Check if we've already processed this email
        existing = db.get_story_by_email_id(email_id)
        if existing:
            return {
                "status": "duplicate",
                "message": f"Story already processed: {existing['title']}",
                "story_id": existing["id"],
            }

        # Create placeholder story record to get ID
        story_id = db.create_story(email_id, title="Processing...")

        # Update status to processing
        db.update_story_status(story_id, StoryStatus.PROCESSING)

        # Extract story content and save to files (agent-first approach)
        result = extract_content(email_data, story_id, storage)

        if not result:
            # Extraction failed
            db.update_story_status(story_id, StoryStatus.FAILED, "Could not extract story content from email")
            return {
                "status": "error",
                "message": "Could not extract story content from email",
                "story_id": story_id,
            }

        content_path, metadata_path, original_email_path = result

        # Read metadata to get title, author, extraction method
        metadata = storage.read_metadata(metadata_path)

        # Update story record with file paths and metadata
        db.update_story_paths(
            story_id,
            content_path=content_path,
            metadata_path=metadata_path
        )

        # Chunk the story - use Agent chunker by default with fallback to SimpleChunker
        use_agent = os.environ.get("USE_AGENT_CHUNKER", "true").lower() == "true"
        target_words = int(os.environ.get("TARGET_WORDS", "8000"))

        if use_agent:
            print(f"Using Agent chunker with target {target_words} words")
            chunker = AgentChunker(target_words=target_words, fallback_to_simple=True)
        else:
            print(f"Using simple chunker with target {target_words} words")
            chunker = SimpleChunker(target_words=target_words)

        # Chunk from file and save chunk files
        chunk_manifest_path = chunker.chunk_story_from_file(story_id, content_path, storage)

        # Update story with chunk manifest path
        db.update_story_paths(story_id, chunk_manifest_path=chunk_manifest_path)

        # Read chunk manifest and create database records
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

        db.update_word_count(story_id, total_words)
        db.update_story_status(story_id, StoryStatus.CHUNKED)
        volume.commit()

        return {
            "status": "success",
            "message": f"Successfully processed and chunked: {metadata['title']}. Chunks will be sent daily.",
            "story_id": story_id,
            "chunks": chunk_manifest["total_chunks"],
            "total_words": total_words,
        }

    except Exception as e:
        # Log error and update status
        error_msg = f"Processing error: {str(e)}"
        print(error_msg)

        try:
            db.update_story_status(story_id, StoryStatus.FAILED, error_msg)
            db.increment_retry_count(story_id)
            volume.commit()
        except Exception as db_error:
            print(f"Failed to update database: {db_error}")

        return {
            "status": "error",
            "message": error_msg,
            "story_id": story_id if 'story_id' in locals() else None,
        }


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("story-prep-secrets")],
)
@modal.fastapi_endpoint(method="POST")
def webhook(data: Dict[str, Any]):
    """
    Webhook endpoint for receiving parsed emails.

    Accepts POST requests with email data and triggers processing.
    """
    # Spawn async processing
    process_story.spawn(data)

    return {
        "status": "accepted",
        "message": "Story processing started",
    }


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("story-prep-secrets")],
    schedule=modal.Cron("0 */6 * * *"),  # Every 6 hours
)
def retry_failed_stories():
    """
    Scheduled function to retry failed stories.

    Runs every 6 hours to retry stories that failed processing.
    """
    db = Database("/data/stories.db")
    storage = FileStorage("/data")
    failed_stories = db.get_failed_stories(max_retries=3)

    print(f"Found {len(failed_stories)} failed stories to retry")

    for story in failed_stories:
        print(f"Retrying story: {story['title']} (ID: {story['id']})")

        # Try to reconstruct email data from original_email_path if available
        if story.get("original_email_path"):
            try:
                full_path = storage.get_absolute_path(story["original_email_path"])
                original_email = full_path.read_text()
                # Split back into text and html
                parts = original_email.split("\n\n--- HTML ---\n\n", 1)
                text = parts[0]
                html = parts[1] if len(parts) > 1 else ""
            except Exception as e:
                print(f"Could not read original email: {e}")
                text = ""
                html = ""
        else:
            # Fallback - read content if available
            if story.get("content_path"):
                try:
                    text = storage.read_story_content(story["content_path"])
                except Exception:
                    text = ""
            else:
                text = ""
            html = ""

        email_data = {
            "message-id": story["email_id"],
            "text": text,
            "html": html,
            "subject": story["title"],
            "from": story["author"],
        }

        try:
            result = process_story.remote(email_data)
            print(f"Retry result: {result}")
        except Exception as e:
            print(f"Retry failed: {e}")
            db.increment_retry_count(story["id"])

    volume.commit()


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("story-prep-secrets")],
    schedule=modal.Cron("0 8 * * *"),  # Every day at 8am UTC
)
def send_daily_chunk():
    """
    Scheduled function to send one chunk per day to Kindle.

    Runs every day at 8am UTC to send the next unsent chunk.
    """
    db = Database("/data/stories.db")
    next_chunk = db.get_next_unsent_chunk()

    if not next_chunk:
        print("No unsent chunks found")
        return

    print(f"📤 Sending chunk {next_chunk['chunk_number']}/{next_chunk['total_chunks']} from Story ID {next_chunk['story_id']}: {next_chunk['title']} by {next_chunk['author']}")
    print(f"   Chunk ID: {next_chunk['id']}, Words: {next_chunk['word_count']}")

    try:
        # Generate EPUB for this chunk
        epub_gen = EPUBGenerator("/data/epubs")
        epub_path = epub_gen.create_epub(
            text=next_chunk["chunk_text"],
            title=next_chunk["title"],
            author=next_chunk["author"],
            chunk_number=next_chunk["chunk_number"],
            total_chunks=next_chunk["total_chunks"],
        )

        # Send to Kindle
        kindle_sender = KindleSender.from_env()
        success = kindle_sender.send_epubs(
            epub_paths=[epub_path],
            title=next_chunk["title"],
            subject=f"{next_chunk['title']} - Part {next_chunk['chunk_number']}/{next_chunk['total_chunks']}",
        )

        if success:
            # Mark chunk as sent
            db.mark_chunk_sent(next_chunk["id"])

            # Check if all chunks for this story have been sent
            all_chunks = db.get_story_chunks(next_chunk["story_id"])
            all_sent = all([chunk["sent_to_kindle_at"] for chunk in all_chunks])

            if all_sent:
                db.update_story_status(next_chunk["story_id"], StoryStatus.SENT)
                print(f"✅ All chunks sent for Story ID {next_chunk['story_id']}: {next_chunk['title']}")
            else:
                remaining = sum(1 for chunk in all_chunks if not chunk["sent_to_kindle_at"])
                print(f"✅ Successfully sent chunk {next_chunk['chunk_number']}/{next_chunk['total_chunks']} from Story ID {next_chunk['story_id']}")
                print(f"   {remaining} chunk(s) remaining for this story")

            volume.commit()
        else:
            print(f"❌ Failed to send chunk {next_chunk['chunk_number']}/{next_chunk['total_chunks']} from Story ID {next_chunk['story_id']}")

    except Exception as e:
        print(f"❌ Error sending chunk from Story ID {next_chunk.get('story_id', 'unknown')}: {e}")


@app.local_entrypoint()
def main():
    """
    Local testing entrypoint.

    Run with: modal run main.py

    Uses Pale Lights example 1 as test story with a unique email ID to avoid duplicate detection.
    """
    # Generate unique email ID for each test run
    unique_id = str(uuid.uuid4())

    # Read test story from file
    import os
    # Try Modal path first, then local path
    test_file_modal = "/root/examples/inputs/pale-lights-example-1.txt"
    test_file_local = os.path.join(os.path.dirname(__file__), "examples", "inputs", "pale-lights-example-1.txt")

    test_file = test_file_modal if os.path.exists(test_file_modal) else test_file_local

    if os.path.exists(test_file):
        with open(test_file, "r") as f:
            test_content = f.read()
        story_title = "Pale Lights - Test Chapter"
        story_author = "ErraticErrata"
    else:
        # Fallback to simple test if file doesn't exist
        test_content = "This is a test story with some content.\n\nIt has multiple paragraphs to demonstrate the chunking functionality.\n\n" * 500
        story_title = "Test Story"
        story_author = "Test Author"

    # Example test data
    test_email = {
        "message-id": f"test-{unique_id}",
        "subject": story_title,
        "from": f"{story_author} <test@example.com>",
        "text": test_content,
    }

    print(f"Testing with email ID: test-{unique_id}")
    print(f"Story: {story_title} by {story_author}")
    result = process_story.remote(test_email)
    print(f"Result: {result}")
