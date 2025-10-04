#!/usr/bin/env python3
"""Test script for LLM chunker."""

import os
from dotenv import load_dotenv
from chunker import LLMChunker, SimpleChunker

# Load environment variables
load_dotenv()

def test_chunker(file_path: str, target_words: int = 5000, use_llm: bool = True, output_dir: str = "examples/outputs"):
    """Test chunker on a file."""
    with open(file_path, 'r') as f:
        text = f.read()

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    print(f"Testing on: {file_path}")
    print(f"Total words: {len(text.split())}")
    print(f"Target words per chunk: {target_words}")
    print(f"Using LLM: {use_llm}\n")

    if use_llm:
        chunker = LLMChunker(target_words=target_words)
    else:
        chunker = SimpleChunker(target_words=target_words)

    chunks = chunker.chunk_text(text)

    print(f"\nResults: {len(chunks)} chunks created")
    print("=" * 80)

    # Get base filename without extension
    base_name = os.path.splitext(os.path.basename(file_path))[0]

    for i, (chunk_text, word_count) in enumerate(chunks, 1):
        print(f"\nChunk {i}: {word_count} words")

        # Show first 200 characters
        preview = chunk_text[:200].replace('\n', ' ')
        print(f"Preview: {preview}...")

        # Write chunk to file
        output_file = os.path.join(output_dir, f"{base_name}_chunk{i}_target{target_words}.txt")
        with open(output_file, 'w') as f:
            f.write(chunk_text)
        print(f"Saved to: {output_file}")
        print("-" * 80)

if __name__ == "__main__":
    import sys

    file_path = sys.argv[1] if len(sys.argv) > 1 else "examples/pale-lights.txt"
    target_words = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    use_llm = os.environ.get("USE_LLM_CHUNKER", "true").lower() == "true"

    test_chunker(file_path, target_words, use_llm)
