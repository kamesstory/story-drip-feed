"""
Content extraction agent using Claude Agent SDK.

This module provides intelligent content extraction from emails using Claude's
Agent SDK. The agent can analyze emails and determine the best extraction strategy,
handle complex scenarios, and fall back to traditional strategies when needed.

Outputs are saved to Modal volume as files:
- metadata.yaml: Story metadata (title, author, source_type, etc.)
- content.txt: Clean story content
- original_email.txt: Original email for debugging
"""

import os
import re
from typing import Optional, Dict, Any, Tuple
from src.email_parser import EmailParser, InlineTextStrategy, PasswordProtectedURLStrategy
from src.file_storage import FileStorage


async def extract_content_with_agent(email_data: Dict[str, Any], story_id: int,
                                      storage: FileStorage) -> Optional[Tuple[str, str, str]]:
    """
    Use Claude Agent SDK to intelligently extract story content from email.

    The agent analyzes the email and determines:
    - Is content inline or requires URL fetching?
    - Are there passwords or authentication needed?
    - Are there multiple content sources to combine?
    - What's the best extraction approach?

    Saves extracted content and metadata to files.

    Args:
        email_data: Dict with keys like 'html', 'text', 'subject', 'from'
        story_id: Database ID for this story
        storage: FileStorage instance for saving files

    Returns:
        Tuple of (content_path, metadata_path, original_email_path) as relative paths,
        or None if extraction fails
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
        # The claude-agent-sdk returns ResultMessage with a 'result' field
        if 'result=' in analysis:
            # Extract the result portion
            result_start = analysis.find('result=') + 8  # Skip "result='"
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

        # Save original email for debugging
        email_text = email_data.get("text", "") + "\n\n--- HTML ---\n\n" + email_data.get("html", "")
        original_email_path = storage.save_original_email(story_id, email_text)

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
            # Save content and metadata files
            content_path = storage.save_story_content(story_id, story_content)
            metadata_path = storage.save_metadata(story_id, metadata)

            print(f"✅ Saved story files:")
            print(f"   Content: {content_path}")
            print(f"   Metadata: {metadata_path}")
            print(f"   Original: {original_email_path}")

            return (content_path, metadata_path, original_email_path)

        # If agent strategy didn't work, return None to trigger fallback
        print("Agent strategy failed, will fall back to traditional parser")
        return None

    except ImportError:
        print("claude-agent-sdk not installed, falling back to traditional parser")
        return None
    except Exception as e:
        print(f"Agent extraction error: {e}, falling back to traditional parser")
        return None


def extract_content(email_data: Dict[str, Any], story_id: int,
                   storage: FileStorage) -> Optional[Tuple[str, str, str]]:
    """
    Extract content with agent-first approach and automatic fallback.

    Tries agent extraction first, falls back to traditional EmailParser if needed.
    Saves all outputs to files on Modal volume.

    Args:
        email_data: Dict with keys like 'html', 'text', 'subject', 'from'
        story_id: Database ID for this story
        storage: FileStorage instance for saving files

    Returns:
        Tuple of (content_path, metadata_path, original_email_path) as relative paths,
        or None if all extraction methods fail
    """
    # Agent extraction enabled by default
    use_agent = os.environ.get("USE_AGENT_EXTRACTION", "true").lower() == "true"

    if use_agent:
        print("Attempting agent-based content extraction...")
        try:
            import anyio
            result = anyio.run(extract_content_with_agent, email_data, story_id, storage)
            if result:
                print(f"✅ Agent extraction successful")
                return result
        except Exception as e:
            print(f"Agent extraction failed: {e}")

    # Fall back to traditional parser
    print("Using traditional EmailParser strategies...")
    parser = EmailParser()
    result = parser.parse_email(email_data)

    if result:
        # Save original email
        email_text = email_data.get("text", "") + "\n\n--- HTML ---\n\n" + email_data.get("html", "")
        original_email_path = storage.save_original_email(story_id, email_text)

        # Save content
        content_path = storage.save_story_content(story_id, result["text"])

        # Save metadata
        metadata = {
            "title": result.get("title", "Unknown Title"),
            "author": result.get("author", "Unknown Author"),
            "source_type": result.get("source_type", "traditional_parser"),
            "extraction_method": "fallback",
            "used_fallback": use_agent
        }
        metadata_path = storage.save_metadata(story_id, metadata)

        print(f"✅ Saved story files (fallback):")
        print(f"   Content: {content_path}")
        print(f"   Metadata: {metadata_path}")
        print(f"   Original: {original_email_path}")

        return (content_path, metadata_path, original_email_path)

    return None


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

    # Basic validation - should be substantial
    if len(story_content) < 500:
        print(f"Warning: Extracted content too short ({len(story_content)} chars)")
        return None

    return story_content


def _extract_author_from_email(from_email: str) -> str:
    """Extract author name from email address."""
    # Try to extract name from "Name <email@domain.com>" format
    match = re.match(r'^([^<]+)<', from_email)
    if match:
        return match.group(1).strip()

    # Otherwise use email username
    match = re.match(r'^([^@]+)@', from_email)
    if match:
        return match.group(1).strip()

    return "Unknown Author"


def _extract_field(text: str, field_name: str) -> str:
    """Extract a field value from agent response."""
    # Handle markdown formatting: **FIELD:** value (capture single line, trim extra text)
    pattern = rf'\*\*{field_name}:\*\*\s*([^\n*]+)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        # Remove escaped newlines and extra content (handle both \n and actual newlines)
        value = value.replace('\\n', ' ').split('\n')[0].strip()
        return value

    # Fallback to plain format: FIELD: value
    pattern = rf'{field_name}:\s*([^\n*]+)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        value = value.replace('\\n', ' ').split('\n')[0].strip()
        return value

    return ""
