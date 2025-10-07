"""
Content extraction agent using Claude Agent SDK.

This module provides intelligent content extraction from emails using Claude's
Agent SDK. The agent can analyze emails and determine the best extraction strategy,
handle complex scenarios, and fall back to traditional strategies when needed.
"""

import os
import re
from typing import Optional, Dict, Any
from email_parser import EmailParser, InlineTextStrategy, PasswordProtectedURLStrategy


async def extract_content_with_agent(email_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Use Claude Agent SDK to intelligently extract story content from email.

    The agent analyzes the email and determines:
    - Is content inline or requires URL fetching?
    - Are there passwords or authentication needed?
    - Are there multiple content sources to combine?
    - What's the best extraction approach?

    Args:
        email_data: Dict with keys like 'html', 'text', 'subject', 'from'

    Returns:
        Dict with keys: 'text', 'title', 'author', 'source_type', 'metadata'
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
3. NOT story content = email headers, "View in app", dates, brief announcements, URLs by themselves
4. Look at the TEXT CONTENT carefully - if there are many paragraphs of narrative after the header, that IS the story
5. Only choose URL strategy if there's NO substantial narrative in the email body itself

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

        # Parse agent's decision
        strategy = _extract_field(analysis, "STRATEGY")
        url = _extract_field(analysis, "URL")
        password = _extract_field(analysis, "PASSWORD")
        confidence = _extract_field(analysis, "CONFIDENCE")

        # Execute based on agent's decision
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
                result["source_type"] = "agent_url"
                result["metadata"] = {
                    "agent_confidence": confidence,
                    "extracted_url": url,
                    "had_password": password != "none"
                }
                return result

        elif strategy == "inline" or strategy == "mixed":
            print(f"Agent recommends inline strategy - using agent to clean content")
            # Use agent to extract just the story content
            story_content = await _extract_story_with_agent(email_data)

            if story_content:
                result = {
                    "text": story_content,
                    "title": email_data.get("subject", "Unknown Title"),
                    "author": _extract_author_from_email(email_data.get("from", "")),
                    "source_type": "agent_inline",
                    "metadata": {
                        "agent_confidence": confidence
                    }
                }
                return result

        # If agent strategy didn't work, return None to trigger fallback
        print("Agent strategy failed, will fall back to traditional parser")
        return None

    except ImportError:
        print("claude-agent-sdk not installed, falling back to traditional parser")
        return None
    except Exception as e:
        print(f"Agent extraction error: {e}, falling back to traditional parser")
        return None


def extract_content(email_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Extract content with agent-first approach and automatic fallback.

    Tries agent extraction first, falls back to traditional EmailParser if needed.

    Args:
        email_data: Dict with keys like 'html', 'text', 'subject', 'from'

    Returns:
        Dict with keys: 'text', 'title', 'author', optionally 'source_type', 'metadata'
        or None if all extraction methods fail
    """
    # Agent extraction enabled by default
    use_agent = os.environ.get("USE_AGENT_EXTRACTION", "true").lower() == "true"

    if use_agent:
        print("Attempting agent-based content extraction...")
        try:
            import anyio
            result = anyio.run(extract_content_with_agent, email_data)
            if result:
                print(f"✅ Agent extraction successful ({result.get('source_type', 'unknown')})")
                return result
        except Exception as e:
            print(f"Agent extraction failed: {e}")

    # Fall back to traditional parser
    print("Using traditional EmailParser strategies...")
    parser = EmailParser()
    result = parser.parse_email(email_data)

    if result:
        # Add metadata to indicate fallback was used
        result["source_type"] = result.get("source_type", "traditional_parser")
        result["metadata"] = {"used_fallback": use_agent}

    return result


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


def _extract_field(text: str, field_name: str) -> str:
    """Extract a field value from agent response."""
    pattern = rf'{field_name}:\s*(.+?)(?:\n|$)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""
