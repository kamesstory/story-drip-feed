import modal
import os
import uuid
from typing import Dict, Any

from database import Database, StoryStatus
from email_parser import EmailParser
from chunker import chunk_story, LLMChunker, SimpleChunker
from epub_generator import EPUBGenerator
from kindle_sender import KindleSender

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
    )
    .add_local_file("database.py", "/root/database.py")
    .add_local_file("email_parser.py", "/root/email_parser.py")
    .add_local_file("chunker.py", "/root/chunker.py")
    .add_local_file("epub_generator.py", "/root/epub_generator.py")
    .add_local_file("kindle_sender.py", "/root/kindle_sender.py")
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
    email_id = email_data.get("message-id", email_data.get("Message-ID", "unknown"))

    try:
        # Check if we've already processed this email
        existing = db.get_story_by_email_id(email_id)
        if existing:
            return {
                "status": "duplicate",
                "message": f"Story already processed: {existing['title']}",
                "story_id": existing["id"],
            }

        # Parse email to extract story
        parser = EmailParser()
        story_data = parser.parse_email(email_data)

        if not story_data:
            # Create failed record
            story_id = db.create_story(email_id, title="Failed to parse")
            db.update_story_status(story_id, StoryStatus.FAILED, "Could not extract story content from email")
            return {
                "status": "error",
                "message": "Could not extract story content from email",
                "story_id": story_id,
            }

        # Create story record
        story_id = db.create_story(
            email_id=email_id,
            title=story_data["title"],
            author=story_data["author"],
            raw_content=story_data["text"],
        )

        # Update status to processing
        db.update_story_status(story_id, StoryStatus.PROCESSING)

        # Chunk the story - use LLM chunker if enabled
        use_llm = os.environ.get("USE_LLM_CHUNKER", "false").lower() == "true"
        target_words = int(os.environ.get("TARGET_WORDS", "5000"))

        if use_llm:
            print(f"Using LLM chunker with target {target_words} words")
            chunker = LLMChunker(target_words=target_words)
            chunks = chunker.chunk_text(story_data["text"])
        else:
            print(f"Using simple chunker with target {target_words} words")
            chunks = chunk_story(story_data["text"], target_words=target_words)

        total_words = sum(word_count for _, word_count in chunks)
        db.update_word_count(story_id, total_words)

        # Save chunk records to database (EPUBs will be generated on-demand when sending)
        total_chunks = len(chunks)
        for i, (chunk_text, word_count) in enumerate(chunks, start=1):
            db.create_chunk(
                story_id=story_id,
                chunk_number=i,
                total_chunks=total_chunks,
                chunk_text=chunk_text,
                word_count=word_count,
            )

        db.update_story_status(story_id, StoryStatus.CHUNKED)
        volume.commit()

        return {
            "status": "success",
            "message": f"Successfully processed and chunked: {story_data['title']}. Chunks will be sent daily.",
            "story_id": story_id,
            "chunks": len(chunks),
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
    failed_stories = db.get_failed_stories(max_retries=3)

    print(f"Found {len(failed_stories)} failed stories to retry")

    for story in failed_stories:
        print(f"Retrying story: {story['title']} (ID: {story['id']})")

        # Reconstruct email data from stored content
        email_data = {
            "message-id": story["email_id"],
            "text": story["raw_content"] or "",
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

    print(f"Sending chunk {next_chunk['chunk_number']}/{next_chunk['total_chunks']} of story: {next_chunk['title']}")

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
                print(f"All chunks sent for story: {next_chunk['title']}")

            volume.commit()
            print(f"Successfully sent chunk {next_chunk['chunk_number']}/{next_chunk['total_chunks']}")
        else:
            print(f"Failed to send chunk {next_chunk['chunk_number']}/{next_chunk['total_chunks']}")

    except Exception as e:
        print(f"Error sending chunk: {e}")


@app.local_entrypoint()
def main():
    """
    Local testing entrypoint.

    Run with: modal run main.py

    Generates a test story with a unique email ID to avoid duplicate detection.
    """
    # Generate unique email ID for each test run
    unique_id = str(uuid.uuid4())

    # Example test data
    test_email = {
        "message-id": f"test-{unique_id}",
        "subject": "Test Story",
        "from": "Test Author <test@example.com>",
        "text": """
        This is a test story with some content.

        It has multiple paragraphs to demonstrate the chunking functionality.

        """ * 500,  # Repeat to get enough words for chunking
    }

    print(f"Testing with email ID: test-{unique_id}")
    result = process_story.remote(test_email)
    print(f"Result: {result}")
