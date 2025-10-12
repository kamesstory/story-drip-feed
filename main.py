import modal
import os
import uuid
from typing import Dict, Any

from src.database import Database, StoryStatus
from src.chunker import AgentChunker, SimpleChunker
from src.content_extraction_agent import extract_content
from src.epub_generator import EPUBGenerator
from src.kindle_sender import KindleSender
from src.file_storage import FileStorage

# Environment detection
# Use MODAL_ENVIRONMENT=prod for production, defaults to dev
IS_DEV = os.environ.get("MODAL_ENVIRONMENT", "dev") != "prod"

# Configure based on environment
APP_NAME = "nighttime-story-prep-dev" if IS_DEV else "nighttime-story-prep"
VOLUME_NAME = "story-data-dev" if IS_DEV else "story-data"
DB_NAME = "stories-dev.db" if IS_DEV else "stories.db"

print(f"🚀 Running in {'DEVELOPMENT' if IS_DEV else 'PRODUCTION'} mode")
print(f"   App: {APP_NAME}")
print(f"   Volume: {VOLUME_NAME}")
print(f"   Database: /data/{DB_NAME}")

# Create Modal app
app = modal.App(APP_NAME)

# Create persistent volume for database and EPUBs
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

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
    Main processing function for incoming stories.

    Args:
        email_data: Dict with email contents (html, text, subject, from, message-id)

    Returns:
        Dict with processing status and details
    """
    db = Database(f"/data/{DB_NAME}")
    storage = FileStorage("/data")
    email_id = email_data.get("message-id", email_data.get("Message-ID", "unknown"))

    print("=" * 80)
    print("🔄 PROCESSING STORY")
    print("=" * 80)
    print(f"Email ID: {email_id}")
    print(f"Subject: {email_data.get('subject', 'N/A')}")
    print(f"From: {email_data.get('from', 'N/A')}")
    print(f"Text content length: {len(email_data.get('text', ''))} chars")
    print(f"HTML content length: {len(email_data.get('html', ''))} chars")

    story_id = None
    try:
        # Check if we've already processed this email
        print(f"\n🔍 Checking for duplicate email ID: {email_id}")
        existing = db.get_story_by_email_id(email_id)
        if existing:
            print(f"⚠️  Duplicate detected: Story ID {existing['id']} already exists")
            print(f"   Title: {existing['title']}")
            print(f"   Status: {existing['status']}")
            return {
                "status": "duplicate",
                "message": f"Story already processed: {existing['title']}",
                "story_id": existing["id"],
            }

        # Create placeholder story record to get ID
        print(f"\n✅ No duplicate found, creating new story record...")
        story_id = db.create_story(email_id, title="Processing...")
        print(f"   Story ID: {story_id}")

        # Update status to processing
        db.update_story_status(story_id, StoryStatus.PROCESSING)
        print(f"   Status: PROCESSING")

        # Extract story content and save to files (agent-first approach)
        print(f"\n📄 STEP 1: Content Extraction")
        print("-" * 80)
        result = extract_content(email_data, story_id, storage)

        if not result:
            # Extraction failed
            error_msg = "Could not extract story content from email"
            print(f"❌ Extraction failed: {error_msg}")
            db.update_story_status(story_id, StoryStatus.FAILED, error_msg)
            volume.commit()
            return {
                "status": "error",
                "message": error_msg,
                "story_id": story_id,
            }

        content_path, metadata_path, original_email_path = result
        print(f"✅ Extraction successful")
        print(f"   Content path: {content_path}")
        print(f"   Metadata path: {metadata_path}")
        print(f"   Original email path: {original_email_path}")

        # Read metadata to get title, author, extraction method
        metadata = storage.read_metadata(metadata_path)
        print(f"\n📋 Story Metadata:")
        print(f"   Title: {metadata.get('title')}")
        print(f"   Author: {metadata.get('author')}")
        print(f"   Extraction method: {metadata.get('extraction_method')}")

        # Update story record with file paths and metadata
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

        # Chunk the story - use Agent chunker by default with fallback to SimpleChunker
        print(f"\n✂️  STEP 2: Chunking Story")
        print("-" * 80)
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
        print(f"✅ Chunk manifest created: {chunk_manifest_path}")

        # Update story with chunk manifest path
        db.update_story_paths(story_id, chunk_manifest_path=chunk_manifest_path)

        # Read chunk manifest and create database records
        print(f"\n💾 STEP 3: Saving Chunks to Database")
        print("-" * 80)
        chunk_manifest = storage.read_chunk_manifest(chunk_manifest_path)
        total_words = 0

        for chunk_info in chunk_manifest["chunks"]:
            chunk_path = chunk_info["chunk_path"]
            chunk_text = storage.read_chunk(chunk_path)

            chunk_id = db.create_chunk(
                story_id=story_id,
                chunk_number=chunk_info["chunk_number"],
                total_chunks=chunk_manifest["total_chunks"],
                chunk_text=chunk_text,
                word_count=chunk_info["word_count"],
            )
            total_words += chunk_info["word_count"]
            print(f"   ✅ Chunk {chunk_info['chunk_number']}/{chunk_manifest['total_chunks']}: "
                  f"{chunk_info['word_count']} words (DB ID: {chunk_id})")

        db.update_word_count(story_id, total_words)
        db.update_story_status(story_id, StoryStatus.CHUNKED)
        volume.commit()

        print(f"\n✅ PROCESSING COMPLETE")
        print(f"   Story ID: {story_id}")
        print(f"   Title: {metadata['title']}")
        print(f"   Total chunks: {chunk_manifest['total_chunks']}")
        print(f"   Total words: {total_words}")
        print("=" * 80)

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
        print(f"\n❌ PROCESSING FAILED")
        print(f"   Error: {error_msg}")
        import traceback
        traceback.print_exc()
        print("=" * 80)

        try:
            if story_id:
                db.update_story_status(story_id, StoryStatus.FAILED, error_msg)
                db.increment_retry_count(story_id)
                volume.commit()
                print(f"   Updated Story ID {story_id} status to FAILED")
        except Exception as db_error:
            print(f"   Failed to update database: {db_error}")

        return {
            "status": "error",
            "message": error_msg,
            "story_id": story_id if story_id else None,
        }


def parse_brevo_webhook(data: Dict[str, Any]) -> list[Dict[str, Any]]:
    """
    Parse Brevo inbound webhook payload into internal format.

    Brevo sends webhooks with an 'items' array containing email objects.
    Each email object has fields like Subject, From, Date, RawHtmlBody, RawTextBody, etc.

    Args:
        data: Raw Brevo webhook payload with 'items' array

    Returns:
        List of email data dicts in internal format
    """
    emails = []

    # Brevo sends an 'items' array
    items = data.get("items", [])

    for item in items:
        # Extract fields from Brevo format
        # Brevo uses capitalized field names
        email_data = {
            "message-id": item.get("Uuid") or item.get("MessageId") or str(uuid.uuid4()),
            "subject": item.get("Subject", "No Subject"),
            "from": item.get("From", {}).get("Address", "unknown@unknown.com"),
            "text": item.get("RawTextBody", ""),
            "html": item.get("RawHtmlBody", ""),
            "date": item.get("Date", ""),
        }

        # Also check for "To" address if needed for routing
        # to_addresses = item.get("To", [])

        emails.append(email_data)

    return emails


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("story-prep-secrets")],
)
@modal.fastapi_endpoint(method="POST")
def webhook(data: Dict[str, Any]):
    """
    Webhook endpoint for receiving parsed emails from Brevo.

    Brevo sends inbound emails as JSON with an 'items' array.
    Each email in the array is parsed and processed asynchronously.

    Example Brevo payload:
    {
      "items": [
        {
          "Uuid": "unique-id",
          "MessageId": "<message-id@email.com>",
          "Subject": "Story Title",
          "From": {"Address": "author@patreon.com", "Name": "Author Name"},
          "Date": "2024-01-01T12:00:00Z",
          "RawTextBody": "Story content...",
          "RawHtmlBody": "<html>Story content...</html>"
        }
      ]
    }
    """
    import json

    db = Database(f"/data/{DB_NAME}")

    # Log raw webhook payload
    print("=" * 80)
    print("📨 WEBHOOK RECEIVED")
    print("=" * 80)
    raw_payload_str = json.dumps(data, indent=2)
    print(f"Raw payload size: {len(raw_payload_str)} bytes")
    print(f"Payload preview (first 500 chars):\n{raw_payload_str[:500]}...")

    try:
        # Parse Brevo webhook format
        emails = parse_brevo_webhook(data)
        print(f"\n✅ Parsed {len(emails)} email(s) from webhook")

        if not emails:
            error_msg = "No emails found in webhook payload"
            print(f"❌ {error_msg}")

            # Log failed webhook
            db.log_webhook(
                raw_payload=raw_payload_str,
                parsed_emails_count=0,
                processing_status="error",
                error_message=error_msg
            )
            volume.commit()

            return {
                "status": "error",
                "message": error_msg,
            }

        # Log each parsed email
        for i, email_data in enumerate(emails, 1):
            print(f"\n📧 Email {i}/{len(emails)}:")
            print(f"   Message ID: {email_data.get('message-id')}")
            print(f"   Subject: {email_data.get('subject')}")
            print(f"   From: {email_data.get('from')}")
            print(f"   Text length: {len(email_data.get('text', ''))} chars")
            print(f"   HTML length: {len(email_data.get('html', ''))} chars")

        # Process each email asynchronously
        results = []
        for email_data in emails:
            result = process_story.spawn(email_data)
            results.append({
                "email_id": email_data.get("message-id"),
                "subject": email_data.get("subject"),
                "call_id": str(result.object_id),
            })

        # Log successful webhook
        db.log_webhook(
            raw_payload=raw_payload_str,
            parsed_emails_count=len(emails),
            processing_status="accepted"
        )
        volume.commit()

        print(f"\n✅ Webhook accepted, spawned {len(results)} processing task(s)")
        print("=" * 80)

        return {
            "status": "accepted",
            "message": f"Processing {len(emails)} email(s)",
            "emails": results,
        }

    except Exception as e:
        error_msg = f"Webhook processing error: {str(e)}"
        print(f"\n❌ {error_msg}")
        import traceback
        traceback.print_exc()

        # Log failed webhook
        db.log_webhook(
            raw_payload=raw_payload_str,
            parsed_emails_count=0,
            processing_status="error",
            error_message=error_msg
        )
        volume.commit()

        return {
            "status": "error",
            "message": error_msg,
        }


@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("story-prep-secrets")],
)
@modal.fastapi_endpoint(method="POST")
def submit_url(data: Dict[str, Any]):
    """
    Manual endpoint for submitting a story URL.

    POST a URL (optionally with password) to extract and process.

    Example:
    curl -X POST https://your-url/submit_url \\
      -H "Content-Type: application/json" \\
      -d '{
        "url": "https://example.com/story",
        "password": "optional-password",
        "title": "Story Title (optional)",
        "author": "Author Name (optional)"
      }'
    """
    url = data.get("url")
    if not url:
        return {"status": "error", "message": "Missing 'url' field"}

    password = data.get("password", "")
    title = data.get("title", "Story from URL")
    author = data.get("author", "Unknown Author")

    # Create email-like data structure
    email_data = {
        "message-id": f"url-{uuid.uuid4()}",
        "subject": title,
        "from": f"{author} <url@manual.com>",
        "text": f"{url}\nPassword: {password}" if password else url,
        "html": "",
    }

    # Process async (default behavior)
    result = process_story.spawn(email_data)
    return {
        "status": "accepted",
        "message": f"Processing story from URL: {url}",
        "call_id": str(result.object_id),
        "url": url,
    }


# Scheduled functions (production only)
if not IS_DEV:
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
        db = Database(f"/data/{DB_NAME}")
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
    db = Database(f"/data/{DB_NAME}")
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
