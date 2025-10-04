import modal
import os
from typing import Dict, Any

from database import Database, StoryStatus
from email_parser import EmailParser
from chunker import chunk_story
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

        # Chunk the story
        chunks = chunk_story(story_data["text"], target_words=10000)
        total_words = sum(word_count for _, word_count in chunks)
        db.update_word_count(story_id, total_words)

        # Generate EPUBs
        epub_gen = EPUBGenerator("/data/epubs")
        epub_paths = epub_gen.create_multipart_epubs(
            chunks=chunks,
            title=story_data["title"],
            author=story_data["author"],
        )

        # Save chunk records
        for i, (epub_path, (_, word_count)) in enumerate(zip(epub_paths, chunks), start=1):
            db.create_chunk(
                story_id=story_id,
                chunk_number=i,
                word_count=word_count,
                epub_path=epub_path,
            )

        db.update_story_status(story_id, StoryStatus.CHUNKED)

        # Send to Kindle
        kindle_sender = KindleSender.from_env()
        success = kindle_sender.send_epubs(
            epub_paths=epub_paths,
            title=story_data["title"],
            subject=f"Story: {story_data['title']}",
        )

        if success:
            db.update_story_status(story_id, StoryStatus.SENT)
            # Mark chunks as sent
            chunk_records = db.get_story_chunks(story_id)
            for chunk in chunk_records:
                db.mark_chunk_sent(chunk["id"])

            volume.commit()

            return {
                "status": "success",
                "message": f"Successfully processed and sent: {story_data['title']}",
                "story_id": story_id,
                "chunks": len(chunks),
                "total_words": total_words,
            }
        else:
            db.update_story_status(story_id, StoryStatus.FAILED, "Failed to send to Kindle")
            volume.commit()

            return {
                "status": "error",
                "message": "Failed to send to Kindle",
                "story_id": story_id,
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


@app.local_entrypoint()
def main():
    """
    Local testing entrypoint.

    Run with: modal run main.py
    """
    # Example test data
    test_email = {
        "message-id": "test-123",
        "subject": "Test Story",
        "from": "Test Author <test@example.com>",
        "text": """
        This is a test story with some content.

        It has multiple paragraphs to demonstrate the chunking functionality.

        """ * 500,  # Repeat to get enough words for chunking
    }

    result = process_story.remote(test_email)
    print(f"Result: {result}")
