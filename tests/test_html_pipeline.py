#!/usr/bin/env python3
"""
Test full pipeline with HTML content.

Usage:
    poetry run python test_html_pipeline.py examples/inputs/wandering-inn-example-1.txt
"""
import sys
from src.email_parser import EmailParser
from src.chunker import LLMChunker, SimpleChunker
from src.epub_generator import EPUBGenerator


def test_pipeline(file_path: str, use_llm: bool = True):
    """Test full pipeline with HTML content."""
    print(f"Testing pipeline with: {file_path}")
    print("="*80)

    # Read the file
    with open(file_path, "r") as f:
        email_content = f.read()

    # Create mock email data
    email_data = {
        "text": email_content,
        "html": "",
        "subject": "Wandering Inn Test",
        "from": "pirateaba <test@example.com>",
    }

    # 1. Parse email
    print("\n📧 Parsing email...")
    parser = EmailParser()
    result = parser.parse_email(email_data)

    if not result:
        print("❌ Failed to parse email")
        return

    print(f"✅ Parsed: {result['title']} by {result['author']}")
    print(f"   Content: {len(result['text'])} characters")

    # 2. Chunk the content
    print("\n✂️  Chunking content...")
    if use_llm:
        chunker = LLMChunker(target_words=5000)
    else:
        chunker = SimpleChunker(target_words=5000)

    chunks = chunker.chunk_text(result['text'])
    print(f"✅ Created {len(chunks)} chunks")

    for i, (chunk_text, word_count) in enumerate(chunks, 1):
        print(f"   Chunk {i}: {word_count} words")

    # 3. Generate EPUB
    print("\n📚 Generating EPUB...")
    epub_gen = EPUBGenerator("test_output")

    epub_paths = epub_gen.create_multipart_epubs(
        chunks=chunks,
        title=result['title'],
        author=result['author']
    )

    print(f"✅ Generated {len(epub_paths)} EPUB files:")
    for path in epub_paths:
        print(f"   {path}")

    print("\n" + "="*80)
    print("✅ Pipeline test complete!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: poetry run python test_html_pipeline.py <file_path> [--simple]")
        print("Example: poetry run python test_html_pipeline.py examples/inputs/wandering-inn-example-1.txt")
        sys.exit(1)

    use_llm = "--simple" not in sys.argv
    test_pipeline(sys.argv[1], use_llm=use_llm)
