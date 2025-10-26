"""
Content extraction agent using Claude Agent SDK.

Simplified version - agent-only cleaning, no fallbacks.
Uses EmailParser for raw extraction, agent for cleaning.
"""

import re
from typing import Dict, Any
from src.email_parser import EmailParser
from src.supabase_storage import SupabaseStorage


def extract_content(email_data: Dict[str, Any], storage_id: str,
                   storage: SupabaseStorage) -> Dict[str, Any]:
    """
    Extract and clean story content from email.
    
    Two-step process:
    1. EmailParser extracts raw content (URL or inline)
    2. Agent cleans the raw content (removes boilerplate)

    Args:
        email_data: Dict with keys like 'html', 'text', 'subject', 'from'
        storage_id: Unique ID for this story (used in storage paths)
        storage: SupabaseStorage instance

    Returns:
        Dict with:
        - content_url: Storage path to extracted content
        - metadata: Dict with title, author, extraction_method, word_count

    Raises:
        Exception: If extraction or cleaning fails
    """
    print(f"🔍 Content Extraction:")
    print(f"   Email has text: {len(email_data.get('text', '')) > 0} ({len(email_data.get('text', ''))} chars)")
    print(f"   Email has HTML: {len(email_data.get('html', '')) > 0} ({len(email_data.get('html', ''))} chars)")

    # Step 1: Use EmailParser to extract raw content
    print("\n📋 Step 1: EmailParser extracting raw content...")
    parser = EmailParser()
    result = parser.parse_email(email_data)

    if not result:
        raise Exception("EmailParser could not extract content from email")

    raw_content = result["text"]
    print(f"✅ Raw content extracted: {len(raw_content)} chars")

    # Step 2: Agent cleans the raw content
    print("\n🤖 Step 2: Agent cleaning content...")
    try:
        import anyio
        story_content = anyio.run(_extract_story_with_agent, raw_content)
    except ImportError:
        raise Exception("claude-agent-sdk not installed")
    except Exception as e:
        raise Exception(f"Agent cleaning failed: {str(e)}")

    if not story_content:
        raise Exception("Agent returned no content after cleaning")

    print(f"✅ Cleaned content: {len(story_content)} chars")

    # Step 3: Calculate metadata and upload to Supabase
    word_count = len(re.findall(r'\b\w+\b', story_content))
    
    metadata = {
        "title": result.get("title", email_data.get("subject", "Unknown Title")),
        "author": result.get("author", _extract_author_from_email(email_data.get("from", ""))),
        "source_type": result.get("source_type", "inline"),
        "extraction_method": "agent",
        "word_count": word_count
    }

    # Upload to Supabase Storage
    content_path = f"story-content/{storage_id}/content.txt"
    metadata_path = f"story-metadata/{storage_id}/metadata.json"
    original_path = f"story-content/{storage_id}/original_email.txt"

    # Save original email for debugging
    email_text = email_data.get("text", "") + "\n\n--- HTML ---\n\n" + email_data.get("html", "")
    storage.upload_text(original_path, email_text)

    # Save content and metadata
    storage.upload_text(content_path, story_content)
    storage.upload_json(metadata_path, metadata)

    print(f"\n✅ Saved story files to Supabase:")
    print(f"   Content: {content_path}")
    print(f"   Metadata: {metadata_path}")
    print(f"   Original: {original_path}")

    return {
        "content_url": content_path,
        "metadata": metadata
    }


async def _extract_story_with_agent(raw_content: str) -> str:
    """Use agent to extract ONLY the story content, removing boilerplate."""
    from claude_agent_sdk import query

    extraction_prompt = f"""Extract ONLY the story content from this text.

Raw content:
{raw_content[:10000]}

CRITICAL INSTRUCTIONS - REMOVE ALL NON-STORY CONTENT:

**ALWAYS REMOVE (even if at start of story):**
1. Chapter numbers/titles ("Chapter 27", "Chapter Title", "Episode 5.23")
2. Dates ("Sep 19, 2025", "Posted on January 1", timestamps)
3. Platform UI elements ("View in app", "Read online", "Open in browser")
4. Author notes ("Author's note:", "A/N:", "Note from author")
5. Patreon boilerplate ("Support me on Patreon", "Become a patron", pledge links)
6. Social media ("Like", "Comment", "Share", "Subscribe", "Follow me on Twitter")
7. Copyright notices ("© 2025", "All rights reserved")
8. Table of contents links
9. Navigation elements ("Previous chapter", "Next chapter", "Back to index")
10. Reader engagement ("Thanks for reading!", "Please leave a comment")
11. Update schedules ("Next chapter: Friday", "Posted weekly")
12. Donation/tip jar links

**KEEP ONLY:**
- The actual narrative prose (descriptions, dialogue, action, scenes)
- In-story formatting (scene breaks like "---", "* * *")
- The story should start with the FIRST LINE OF ACTUAL NARRATIVE
- Example good start: "Maryam was not having a good time."
- Example bad start: "Chapter 27\nSep 19, 2025\nView in app\nMaryam was not having a good time."

**OUTPUT FORMAT:**
- Start immediately with story text
- Keep paragraph breaks intact
- Do NOT summarize or paraphrase - extract exact text
- No preamble, no explanation, just the clean story

Output the clean story content now:"""

    response_parts = []
    async for message in query(prompt=extraction_prompt):
        response_parts.append(str(message))

    story_content = "".join(response_parts).strip()

    # Clean up any result wrapper
    if 'result=' in story_content:
        result_start = story_content.find('result=') + 8
        result_end = story_content.rfind("')")
        if result_end > result_start:
            story_content = story_content[result_start:result_end]

    # Basic validation - should be substantial
    if len(story_content) < 500:
        raise Exception(f"Extracted content too short: {len(story_content)} chars")

    return story_content


def _extract_author_from_email(from_email: str) -> str:
    """Extract author name from email address."""
    match = re.match(r'^([^<]+)<', from_email)
    if match:
        return match.group(1).strip()

    match = re.match(r'^([^@]+)@', from_email)
    if match:
        return match.group(1).strip()

    return "Unknown Author"

