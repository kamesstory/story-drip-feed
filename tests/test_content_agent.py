#!/usr/bin/env python3
"""
Test content extraction agent on example files.

Usage:
    poetry run python test_content_agent.py examples/inputs/wandering-inn-example-1.txt
"""
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from src.content_extraction_agent import extract_content

load_dotenv()


def test_content_extraction(file_path: str):
    """Test agent-based content extraction."""
    print(f"Testing content extraction on: {file_path}")
    print("="*80)

    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_filename = Path(file_path).stem
    output_dir = Path("test_outputs") / f"content_extraction_{input_filename}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Saving results to: {output_dir}\n")

    # Read test file
    with open(file_path, "r") as f:
        content = f.read()

    # Save input for reference
    with open(output_dir / "input.txt", "w") as f:
        f.write(content)

    # Create mock email data
    email_data = {
        "text": content,
        "html": "",
        "subject": "Test Story Chapter",
        "from": "Test Author <test@example.com>",
        "message-id": "test-extraction-001",
    }

    # Enable agent extraction for this test
    os.environ["USE_AGENT_EXTRACTION"] = "true"

    print("\n" + "="*80)
    print("TESTING AGENT EXTRACTION")
    print("="*80)

    result = extract_content(email_data)

    extraction_result = {
        "input_file": file_path,
        "timestamp": timestamp,
        "success": False
    }

    if result:
        print("\n✅ Successfully extracted content!")
        print(f"\nTitle: {result['title']}")
        print(f"Author: {result['author']}")
        print(f"Source Type: {result.get('source_type', 'unknown')}")
        print(f"Metadata: {result.get('metadata', {})}")
        print(f"Content length: {len(result['text'])} characters")
        print(f"\nContent preview (first 500 chars):")
        print("-"*80)
        print(result['text'][:500])
        print("-"*80)

        # Check if it's HTML
        is_html = '<' in result['text'] and '>' in result['text']
        if is_html:
            print("\n✅ Content contains HTML")
        else:
            print("\n✅ Content is plain text")

        # Save extracted content
        with open(output_dir / "extracted_content.txt", "w") as f:
            f.write(result['text'])

        # Save extraction metadata
        extraction_result.update({
            "success": True,
            "title": result['title'],
            "author": result['author'],
            "source_type": result.get('source_type', 'unknown'),
            "metadata": result.get('metadata', {}),
            "content_length": len(result['text']),
            "is_html": is_html
        })

    else:
        print("\n❌ Failed to extract content")
        extraction_result["error"] = "Extraction failed"

        with open(output_dir / "error.txt", "w") as f:
            f.write("Extraction failed\n")

    # Save extraction result
    with open(output_dir / "extraction_result.json", "w") as f:
        json.dump(extraction_result, f, indent=2)

    print(f"\n✅ Results saved to: {output_dir}")
    print(f"   - input.txt: Original input")
    print(f"   - extracted_content.txt: Extracted story content")
    print(f"   - extraction_result.json: Extraction metadata")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: poetry run python test_content_agent.py <file_path>")
        print("Example: poetry run python test_content_agent.py examples/inputs/wandering-inn-example-1.txt")
        sys.exit(1)

    # Check if ANTHROPIC_API_KEY is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set in environment")
        sys.exit(1)

    file_path = sys.argv[1]
    test_content_extraction(file_path)
