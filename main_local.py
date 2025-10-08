"""
Local Modal development server.

Run with: modal serve main_local.py

This creates a local development environment with:
- Separate dev database and files (won't affect production)
- Live webhook endpoint for testing
- Manual story submission endpoint
- All the same processing as production
"""

import modal
import os
import uuid
from typing import Dict, Any

from src.database import Database, StoryStatus
from src.content_extraction_agent import extract_content
from src.chunker import AgentChunker, SimpleChunker
from src.epub_generator import EPUBGenerator
from src.kindle_sender import KindleSender
from src.file_storage import FileStorage

# Create Modal app for LOCAL DEVELOPMENT
app = modal.App("nighttime-story-prep-dev")

# Create DEV volume (separate from production)
volume = modal.Volume.from_name("story-data-dev", create_if_missing=True)

# Same image as production
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
    .add_local_file("src/database.py", "/root/src/database.py")
    .add_local_file("src/email_parser.py", "/root/src/email_parser.py")
    .add_local_file("src/chunker.py", "/root/src/chunker.py")
    .add_local_file("src/content_extraction_agent.py", "/root/src/content_extraction_agent.py")
    .add_local_file("src/epub_generator.py", "/root/src/epub_generator.py")
    .add_local_file("src/kindle_sender.py", "/root/src/kindle_sender.py")
    .add_local_file("src/file_storage.py", "/root/src/file_storage.py")
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
    Process incoming story (same as production).

    Uses /data-dev/ for storage to keep separate from production.
    """
    db = Database("/data/stories-dev.db")
    storage = FileStorage("/data")
    email_id = email_data.get("message-id", email_data.get("Message-ID", "unknown"))

    story_id = None
    try:
        # Check for duplicate
        existing = db.get_story_by_email_id(email_id)
        if existing:
            return {
                "status": "duplicate",
                "message": f"Story already processed: {existing['title']}",
                "story_id": existing["id"],
            }

        # Create story record
        story_id = db.create_story(email_id, title="Processing...")
        db.update_story_status(story_id, StoryStatus.PROCESSING)

        # Extract content and save to files
        result = extract_content(email_data, story_id, storage)

        if not result:
            db.update_story_status(story_id, StoryStatus.FAILED, "Could not extract story content from email")
            return {
                "status": "error",
                "message": "Could not extract story content from email",
                "story_id": story_id,
            }

        content_path, metadata_path, original_email_path = result
        metadata = storage.read_metadata(metadata_path)

        # Update story with file paths and metadata
        db.update_story_paths(
            story_id,
            content_path=content_path,
            metadata_path=metadata_path
        )
        db.update_story_metadata(
            story_id,
            title=metadata.get('title'),
            author=metadata.get('author'),
            extraction_method=metadata.get('extraction_method')
        )

        # Chunk the story
        use_agent = os.environ.get("USE_AGENT_CHUNKER", "true").lower() == "true"
        target_words = int(os.environ.get("TARGET_WORDS", "8000"))

        if use_agent:
            print(f"Using Agent chunker with target {target_words} words")
            chunker = AgentChunker(target_words=target_words, fallback_to_simple=True)
        else:
            print(f"Using simple chunker with target {target_words} words")
            chunker = SimpleChunker(target_words=target_words)

        # Chunk from file and save chunks
        chunk_manifest_path = chunker.chunk_story_from_file(story_id, content_path, storage)
        db.update_story_paths(story_id, chunk_manifest_path=chunk_manifest_path)

        # Read chunks and create database records
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
            "message": f"Successfully processed and chunked: {metadata['title']}. {chunk_manifest['total_chunks']} chunk(s) ready.",
            "story_id": story_id,
            "chunks": chunk_manifest["total_chunks"],
            "total_words": total_words,
            "title": metadata['title'],
            "author": metadata['author'],
        }

    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()

        try:
            if story_id:
                db.update_story_status(story_id, StoryStatus.FAILED, error_msg)
                db.increment_retry_count(story_id)
                volume.commit()
        except Exception as db_error:
            print(f"Failed to update database: {db_error}")

        return {
            "status": "error",
            "message": error_msg,
            "story_id": story_id if story_id else None,
        }


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("story-prep-secrets")],
)
@modal.web_endpoint(method="POST")
def webhook(data: Dict[str, Any]):
    """
    Webhook endpoint for receiving parsed emails.

    POST email data here from your email client.

    Example:
    curl -X POST https://your-dev-url/webhook \\
      -H "Content-Type: application/json" \\
      -d '{
        "message-id": "test-123",
        "subject": "Story Title",
        "from": "author@example.com",
        "text": "story content...",
        "send_immediately": false
      }'

    Set "send_immediately": true to process AND send the first chunk right away.
    """
    send_immediately = data.get("send_immediately", False)

    if send_immediately:
        # Process synchronously and send first chunk
        result = process_story.remote(data)

        if result.get("status") == "success":
            # Send first chunk immediately
            send_result = send_next_chunk.remote()
            return {
                "status": "success",
                "message": f"Processed and sent first chunk",
                "process_result": result,
                "send_result": send_result,
            }
        else:
            return result
    else:
        # Process async (default behavior)
        result = process_story.spawn(data)
        return {
            "status": "accepted",
            "message": "Story processing started",
            "call_id": str(result.object_id),
        }


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("story-prep-secrets")],
)
@modal.web_endpoint(method="POST")
def submit_url(data: Dict[str, Any]):
    """
    Manual endpoint for submitting a story URL.

    POST a URL (optionally with password) to extract and process.

    Example:
    curl -X POST https://your-dev-url/submit_url \\
      -H "Content-Type: application/json" \\
      -d '{
        "url": "https://example.com/story",
        "password": "optional-password",
        "title": "Story Title (optional)",
        "author": "Author Name (optional)",
        "send_immediately": false
      }'

    Set "send_immediately": true to process AND send the first chunk right away.
    """
    url = data.get("url")
    if not url:
        return {"status": "error", "message": "Missing 'url' field"}

    password = data.get("password", "")
    title = data.get("title", "Story from URL")
    author = data.get("author", "Unknown Author")
    send_immediately = data.get("send_immediately", False)

    # Create email-like data structure
    email_data = {
        "message-id": f"url-{uuid.uuid4()}",
        "subject": title,
        "from": f"{author} <url@manual.com>",
        "text": f"{url}\nPassword: {password}" if password else url,
        "html": "",
    }

    # Process it
    if send_immediately:
        # Process synchronously and send first chunk
        result = process_story.remote(email_data)

        if result.get("status") == "success":
            # Send first chunk immediately
            send_result = send_next_chunk.remote()
            return {
                "status": "success",
                "message": f"Processed and sent first chunk: {url}",
                "process_result": result,
                "send_result": send_result,
                "url": url,
            }
        else:
            return result
    else:
        # Process async (default behavior)
        result = process_story.spawn(email_data)
        return {
            "status": "accepted",
            "message": f"Processing story from URL: {url}",
            "call_id": str(result.object_id),
            "url": url,
        }


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("story-prep-secrets")],
)
def send_next_chunk():
    """
    Manually send the next chunk (for testing).

    Call this to simulate the daily send without waiting for schedule.
    """
    db = Database("/data/stories-dev.db")
    next_chunk = db.get_next_unsent_chunk()

    if not next_chunk:
        print("No unsent chunks found")
        return {"status": "no_chunks", "message": "No unsent chunks in queue"}

    print(f"📤 Sending chunk {next_chunk['chunk_number']}/{next_chunk['total_chunks']}: {next_chunk['title']}")

    try:
        # Generate EPUB
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
            # Mark as sent
            db.mark_chunk_sent(next_chunk["id"])

            # Check if all chunks sent
            all_chunks = db.get_story_chunks(next_chunk["story_id"])
            all_sent = all([chunk["sent_to_kindle_at"] for chunk in all_chunks])

            if all_sent:
                db.update_story_status(next_chunk["story_id"], StoryStatus.SENT)

            volume.commit()

            return {
                "status": "success",
                "message": f"Sent chunk {next_chunk['chunk_number']}/{next_chunk['total_chunks']}",
                "story_id": next_chunk["story_id"],
                "chunk_number": next_chunk["chunk_number"],
                "total_chunks": next_chunk["total_chunks"],
                "all_sent": all_sent,
            }
        else:
            return {
                "status": "error",
                "message": "Failed to send to Kindle",
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@app.local_entrypoint()
def main():
    """
    Local test entrypoint (same as production).

    Run with: modal run main_local.py
    """
    # Generate unique email ID
    unique_id = str(uuid.uuid4())

    # Read test story
    import os
    test_file_modal = "/root/examples/inputs/pale-lights-example-1.txt"
    test_file_local = os.path.join(os.path.dirname(__file__), "examples", "inputs", "pale-lights-example-1.txt")
    test_file = test_file_modal if os.path.exists(test_file_modal) else test_file_local

    if os.path.exists(test_file):
        with open(test_file, "r") as f:
            test_content = f.read()
        story_title = "Pale Lights - Test Chapter"
        story_author = "ErraticErrata"
    else:
        test_content = "This is a test story.\n\n" * 500
        story_title = "Test Story"
        story_author = "Test Author"

    # Create test email
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
