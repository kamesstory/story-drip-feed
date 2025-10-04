#!/usr/bin/env python3
"""Debug script for LLM chunker."""

import os
from dotenv import load_dotenv
from chunker import LLMChunker

load_dotenv()

def debug_chunker(file_path: str):
    """Debug the LLM chunker."""
    with open(file_path, 'r') as f:
        text = f.read()

    print(f"File: {file_path}")
    print(f"Total characters: {len(text)}")
    print(f"Total words: {len(text.split())}\n")

    chunker = LLMChunker(target_words=5000)

    # Get break points
    break_points = chunker._find_break_points(text)
    print(f"Break points identified: {break_points}")

    # Show what's at those positions
    for i, pos in enumerate(break_points):
        print(f"\nBreak {i+1} at position {pos}:")
        start = max(0, pos - 100)
        end = min(len(text), pos + 100)
        print(f"Context: ...{text[start:end]}...")

if __name__ == "__main__":
    debug_chunker("examples/pale-lights.txt")
