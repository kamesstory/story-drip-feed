"""Test that email parser works with non-password-protected URLs."""

from email_parser import EmailParser

def test_public_url():
    """Test parsing an email with a public URL (no password required)."""

    # Simulate an email with a public URL
    email_data = {
        "message-id": "test-public-url",
        "subject": "Test Chapter - Public",
        "from": "Test Author <author@example.com>",
        "text": """
Test Chapter - No Password Required
Jan 1, 2025

Here's a chapter that's publicly available!

https://httpbin.org/html

Enjoy!
""",
        "html": ""
    }

    parser = EmailParser()
    result = parser.parse_email(email_data)

    if result:
        print("✅ Successfully parsed public URL!")
        print(f"\nTitle: {result['title']}")
        print(f"Author: {result['author']}")
        print(f"Content length: {len(result['text'])} characters")
        print(f"\nContent preview (first 500 chars):")
        print("-" * 80)
        print(result['text'][:500])
        print("-" * 80)

        # Check if HTML was preserved
        if '<' in result['text'] and '>' in result['text']:
            print("\n✅ HTML content preserved")

        return True
    else:
        print("❌ Failed to parse email with public URL")
        return False

if __name__ == "__main__":
    success = test_public_url()
    exit(0 if success else 1)
