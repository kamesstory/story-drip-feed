#!/usr/bin/env python3
"""
Test email parser with example files.

Usage:
    poetry run python test_email_parser.py examples/inputs/wandering-inn-example-1.txt
"""
import sys
from email_parser import EmailParser


def test_email_parser(file_path: str):
    """Test email parser with a file."""
    print(f"Testing email parser with: {file_path}")
    print("="*80)

    # Read the file
    with open(file_path, "r") as f:
        email_content = f.read()

    # Create mock email data
    email_data = {
        "text": email_content,
        "html": "",  # Could add HTML version if needed
        "subject": "Test Email",
        "from": "Test Author <test@example.com>",
    }

    # Parse email
    parser = EmailParser()
    result = parser.parse_email(email_data)

    if result:
        print("\n✅ Successfully parsed email!")
        print(f"\nTitle: {result['title']}")
        print(f"Author: {result['author']}")
        print(f"Content length: {len(result['text'])} characters")
        print(f"\nContent preview (first 500 chars):")
        print("-"*80)
        print(result['text'][:500])
        print("-"*80)

        # Check if it's HTML
        if '<' in result['text'] and '>' in result['text']:
            print("\n✅ Content appears to contain HTML formatting")
        else:
            print("\n⚠️  Content appears to be plain text")

    else:
        print("\n❌ Failed to parse email")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: poetry run python test_email_parser.py <file_path>")
        print("Example: poetry run python test_email_parser.py examples/inputs/wandering-inn-example-1.txt")
        sys.exit(1)

    test_email_parser(sys.argv[1])
