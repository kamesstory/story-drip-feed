"""
Content extraction agent using Claude Agent SDK.

Refactored version for Modal API - uses Supabase Storage instead of file-based storage.
Returns storage URLs instead of file paths.
"""

import os
import re
from typing import Optional, Dict, Any
from src.email_parser import EmailParser, PasswordProtectedURLStrategy
from src.supabase_storage import SupabaseStorage


async def extract_content_with_agent(email_data: Dict[str, Any], storage_id: str,
                                      storage: SupabaseStorage) -> Optional[Dict[str, Any]]:
    """
    Use Claude Agent SDK to intelligently extract story content from email.

    Args:
        email_data: Dict with keys like 'html', 'text', 'subject', 'from'
        storage_id: Unique ID for this story (used in storage paths)
        storage: SupabaseStorage instance

    Returns:
        Dict with:
        - content_url: Storage path to extracted content
        - metadata: Dict with title, author, extraction_method, etc.
        Or None if extraction fails
    """
    try:
        from claude_agent_sdk import query
        import anyio

        # Prepare email preview for agent analysis
        email_preview = _prepare_email_preview(email_data)

        analysis_prompt = f"""Analyze this email to determine how to extract story content.

Email Preview:
{email_preview}

CRITICAL INSTRUCTIONS:
1. DO NOT generate story content from memory or imagination - you will use extraction tools
2. Story content = narrative prose, dialogue, scenes, descriptions (multiple paragraphs of actual story)
3. NOT story content = chapter numbers, dates, "View in app", author notes, Patreon links, social media buttons
4. Look at the TEXT CONTENT carefully - if there are many paragraphs of narrative after the metadata, that IS the story
5. Only choose URL strategy if there's NO substantial narrative in the email body itself
6. REMEMBER: The extraction tool will clean out metadata, so focus on detecting WHERE the story is, not worrying about headers

Decision Tree:
- If email has >1000 characters of narrative prose with dialogue/scenes → STRATEGY: inline
- If email has ONLY a URL, password, and brief text → STRATEGY: url
- If unsure → prefer inline if there's any substantial narrative present

For URL strategy:
- Extract the EXACT URL from the email text (look for https://)
- Extract the EXACT password (look for "Password:", "pass:", "pw:", etc.)
- Password is usually on a line after "Password:" label

Respond in this format:
STRATEGY: <inline|url>
URL: <exact url if found, otherwise none>
PASSWORD: <exact password if found, otherwise none>
CONFIDENCE: <high|medium|low>
REASONING: <1-2 sentences explaining what you saw>

EXAMPLES:
- Email with "Chapter 27\\nMaryam was not having a good time..." + 5000+ words → inline
- Email with "Password: shortCharacters\\nhttps://..." + NO other prose → url"""

        # Query the agent
        response_parts = []
        async for message in query(prompt=analysis_prompt):
            response_parts.append(str(message))

        analysis = "".join(response_parts)
        print(f"\n{'='*80}\nAGENT ANALYSIS:\n{'='*80}\n{analysis}\n{'='*80}\n")

        # Extract just the result text from the agent response
        if 'result=' in analysis:
            result_start = analysis.find('result=') + 8
            result_end = analysis.rfind("')")
            if result_end > result_start:
                analysis = analysis[result_start:result_end]
                print(f"\n{'='*80}\nEXTRACTED RESULT:\n{'='*80}\n{analysis}\n{'='*80}\n")

        # Parse agent's decision
        strategy = _extract_field(analysis, "STRATEGY")
        url = _extract_field(analysis, "URL")
        password = _extract_field(analysis, "PASSWORD")
        confidence = _extract_field(analysis, "CONFIDENCE")

        print(f"DEBUG - Parsed strategy: '{strategy}'")
        print(f"DEBUG - Parsed URL: '{url}'")
        print(f"DEBUG - Parsed confidence: '{confidence}'")

        # Execute based on agent's decision
        story_content = None
        metadata = {}

        if strategy == "url" and url and url != "none":
            print(f"Agent recommends URL strategy: {url}")
            url_strategy = PasswordProtectedURLStrategy()

            # Inject discovered URL/password into email data for strategy
            enhanced_email_data = email_data.copy()
            if url not in enhanced_email_data.get("text", ""):
                enhanced_email_data["text"] = f"{enhanced_email_data.get('text', '')}\n\n{url}"
            if password and password != "none":
                enhanced_email_data["text"] += f"\nPassword: {password}"

            result = url_strategy.extract_story(enhanced_email_data)
            if result:
                story_content = result["text"]
                metadata = {
                    "title": result.get("title", email_data.get("subject", "Unknown Title")),
                    "author": result.get("author", _extract_author_from_email(email_data.get("from", ""))),
                    "source_type": "agent_url",
                    "extraction_method": "agent",
                    "agent_confidence": confidence,
                    "extracted_url": url,
                    "had_password": password != "none"
                }

        elif strategy == "inline" or strategy == "mixed":
            print(f"Agent recommends inline strategy - using agent to clean content")
            # Use agent to extract just the story content
            story_content = await _extract_story_with_agent(email_data)

            if story_content:
                metadata = {
                    "title": email_data.get("subject", "Unknown Title"),
                    "author": _extract_author_from_email(email_data.get("from", "")),
                    "source_type": "agent_inline",
                    "extraction_method": "agent",
                    "agent_confidence": confidence
                }

        if story_content and metadata:
            # Add word count to metadata
            metadata["word_count"] = len(re.findall(r'\b\w+\b', story_content))

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

            print(f"✅ Saved story files to Supabase:")
            print(f"   Content: {content_path}")
            print(f"   Metadata: {metadata_path}")
            print(f"   Original: {original_path}")

            return {
                "content_url": content_path,
                "metadata": metadata
            }

        # If agent strategy didn't work, return None to trigger fallback
        print("Agent strategy failed, will fall back to traditional parser")
        return None

    except ImportError:
        print("claude-agent-sdk not installed, falling back to traditional parser")
        return None
    except Exception as e:
        print(f"Agent extraction error: {e}, falling back to traditional parser")
        import traceback
        traceback.print_exc()
        return None


def extract_content(email_data: Dict[str, Any], storage_id: str,
                   storage: SupabaseStorage) -> Optional[Dict[str, Any]]:
    """
    Extract content with agent-first approach and automatic fallback.

    Args:
        email_data: Dict with keys like 'html', 'text', 'subject', 'from'
        storage_id: Unique ID for this story (used in storage paths)
        storage: SupabaseStorage instance

    Returns:
        Dict with:
        - content_url: Storage path to extracted content
        - metadata: Dict with title, author, extraction_method, word_count
        Or None if all extraction methods fail
    """
    # Agent extraction enabled by default
    use_agent = os.environ.get("USE_AGENT_EXTRACTION", "true").lower() == "true"

    print(f"🔍 Content Extraction Configuration:")
    print(f"   USE_AGENT_EXTRACTION: {use_agent}")
    print(f"   Email has text: {len(email_data.get('text', '')) > 0} ({len(email_data.get('text', ''))} chars)")
    print(f"   Email has HTML: {len(email_data.get('html', '')) > 0} ({len(email_data.get('html', ''))} chars)")

    if use_agent:
        print("\n🤖 Attempting agent-based content extraction...")
        try:
            import anyio
            result = anyio.run(extract_content_with_agent, email_data, storage_id, storage)
            if result:
                print(f"✅ Agent extraction successful")
                return result
            else:
                print(f"⚠️  Agent extraction returned None, falling back...")
        except Exception as e:
            print(f"❌ Agent extraction failed with error: {e}")
            import traceback
            traceback.print_exc()

    # Fall back to traditional parser
    print("\n📋 Using traditional EmailParser strategies...")
    parser = EmailParser()
    result = parser.parse_email(email_data)

    if result:
        print(f"✅ Traditional parser extracted content")
        print(f"   Content length: {len(result.get('text', ''))} chars")
    else:
        print(f"❌ Traditional parser failed to extract content")
        return None

    # Upload to Supabase Storage
    story_content = result["text"]
    word_count = len(re.findall(r'\b\w+\b', story_content))

    metadata = {
        "title": result.get("title", "Unknown Title"),
        "author": result.get("author", "Unknown Author"),
        "source_type": "traditional_parser",
        "extraction_method": "fallback",
        "used_fallback": use_agent,
        "word_count": word_count
    }

    # Save to Supabase Storage
    content_path = f"story-content/{storage_id}/content.txt"
    metadata_path = f"story-metadata/{storage_id}/metadata.json"
    original_path = f"story-content/{storage_id}/original_email.txt"

    # Save original email
    email_text = email_data.get("text", "") + "\n\n--- HTML ---\n\n" + email_data.get("html", "")
    storage.upload_text(original_path, email_text)

    # Save content and metadata
    storage.upload_text(content_path, story_content)
    storage.upload_json(metadata_path, metadata)

    print(f"✅ Saved story files to Supabase (fallback):")
    print(f"   Content: {content_path}")
    print(f"   Metadata: {metadata_path}")
    print(f"   Original: {original_path}")

    return {
        "content_url": content_path,
        "metadata": metadata
    }


def _prepare_email_preview(email_data: Dict[str, Any], max_length: int = 2000) -> str:
    """Prepare a preview of email content for agent analysis."""
    preview_parts = []

    subject = email_data.get("subject", "")
    from_addr = email_data.get("from", "")
    text = email_data.get("text", "")
    html = email_data.get("html", "")

    if subject:
        preview_parts.append(f"Subject: {subject}")
    if from_addr:
        preview_parts.append(f"From: {from_addr}")

    preview_parts.append("\n--- TEXT CONTENT ---")
    preview_parts.append(text[:max_length] if text else "(empty)")

    if html and len(html) < max_length:
        preview_parts.append("\n--- HTML CONTENT ---")
        preview_parts.append(html[:max_length])

    return "\n".join(preview_parts)


async def _extract_story_with_agent(email_data: Dict[str, Any]) -> Optional[str]:
    """Use agent to extract ONLY the story content, removing boilerplate."""
    from claude_agent_sdk import query

    text = email_data.get("text", "")
    html = email_data.get("html", "")
    content = text if text else html

    extraction_prompt = f"""Extract ONLY the story content from this email.

Email content:
{content[:10000]}

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
        print(f"Warning: Extracted content too short ({len(story_content)} chars)")
        return None

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


def _extract_field(text: str, field_name: str) -> str:
    """Extract a field value from agent response."""
    # Handle markdown formatting
    pattern = rf'\*\*{field_name}:\*\*\s*([^\n*]+)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        value = value.replace('\\n', ' ').split('\n')[0].strip()
        return value

    # Fallback to plain format
    pattern = rf'{field_name}:\s*([^\n*]+)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        value = value.replace('\\n', ' ').split('\n')[0].strip()
        return value

    return ""

