"""
Test that extraction properly removes metadata and boilerplate.
"""

import os
import shutil
from src.file_storage import LocalFileStorage
from src.database import Database
from src.content_extraction_agent import extract_content

def test_metadata_removal():
    """Test that agent extraction removes all metadata."""

    # Clean up
    if os.path.exists("./local_data"):
        shutil.rmtree("./local_data")
    if os.path.exists("./test_stories.db"):
        os.remove("./test_stories.db")

    storage = LocalFileStorage("./local_data")
    db = Database("./test_stories.db")

    # Create test email with lots of metadata
    test_email = {
        "message-id": "test-metadata",
        "subject": "Test Story - Chapter 1",
        "from": "Test Author <test@example.com>",
        "text": """Chapter 27
Sep 19, 2025

View in app

Maryam was not having a good time.

"Black fucking Goat," she cursed, ducking under the spinning metal blade.

It screeched and sparked above her head, suddenly whipping back as the articulated metal arm that'd shot it out withdrew into the wall.

---

Later, back at camp, they discussed what had happened.

"That was close," Ishanvi said.

────────────────────

Thanks for reading! If you enjoyed this chapter, please consider:

❤️ Like this post
💬 Comment below
🔄 Share with friends
📧 Subscribe for updates

Support me on Patreon: https://patreon.com/author
Follow me on Twitter: @author

Next chapter coming Friday!

© 2025 Author Name. All rights reserved.""",
        "html": ""
    }

    print("=" * 80)
    print("Testing Metadata Removal")
    print("=" * 80)
    print()

    # Show original
    print("ORIGINAL EMAIL (first 500 chars):")
    print("-" * 80)
    print(test_email["text"][:500])
    print("-" * 80)
    print()

    # Create story and extract
    story_id = db.create_story(
        email_id=test_email["message-id"],
        title=test_email["subject"]
    )

    # Enable agent extraction
    os.environ["USE_AGENT_EXTRACTION"] = "true"

    print("Extracting with agent...")
    result = extract_content(test_email, story_id, storage)

    if not result:
        print("❌ Extraction failed!")
        return False

    content_path, metadata_path, original_email_path = result

    # Read extracted content
    extracted_content = storage.read_story_content(content_path)

    print()
    print("EXTRACTED CONTENT:")
    print("=" * 80)
    print(extracted_content)
    print("=" * 80)
    print()

    # Check what was removed
    removed_items = [
        ("Chapter number", "Chapter 27" not in extracted_content),
        ("Date", "Sep 19, 2025" not in extracted_content),
        ("View in app", "View in app" not in extracted_content),
        ("Like button", "❤️ Like" not in extracted_content or "Like this post" not in extracted_content),
        ("Comment prompt", "💬 Comment" not in extracted_content or "Comment below" not in extracted_content),
        ("Share prompt", "Share with friends" not in extracted_content),
        ("Subscribe prompt", "Subscribe" not in extracted_content),
        ("Patreon link", "patreon.com" not in extracted_content),
        ("Twitter link", "@author" not in extracted_content or "Twitter" not in extracted_content),
        ("Update schedule", "Next chapter coming Friday" not in extracted_content or "Friday" not in extracted_content),
        ("Copyright", "©" not in extracted_content and "All rights reserved" not in extracted_content),
        ("Thanks message", "Thanks for reading" not in extracted_content),
    ]

    # Check what was kept
    kept_items = [
        ("Story content", "Maryam was not having a good time" in extracted_content),
        ("Dialogue", '"Black fucking Goat,"' in extracted_content),
        ("Scene break", "---" in extracted_content or "Later, back at camp" in extracted_content),
        ("Story ending", '"That was close,"' in extracted_content),
    ]

    print("VALIDATION RESULTS:")
    print()
    print("✓ REMOVED (should be True):")
    all_removed = True
    for item, removed in removed_items:
        status = "✅" if removed else "❌"
        print(f"  {status} {item}: {removed}")
        if not removed:
            all_removed = False

    print()
    print("✓ KEPT (should be True):")
    all_kept = True
    for item, kept in kept_items:
        status = "✅" if kept else "❌"
        print(f"  {status} {item}: {kept}")
        if not kept:
            all_kept = False

    print()
    print("=" * 80)

    if all_removed and all_kept:
        print("✅ PASSED: All metadata removed, story content preserved!")
    else:
        print("❌ FAILED: Some issues detected")
        if not all_removed:
            print("   - Some metadata not removed")
        if not all_kept:
            print("   - Some story content missing")

    print("=" * 80)

    return all_removed and all_kept

if __name__ == "__main__":
    success = test_metadata_removal()
    exit(0 if success else 1)
