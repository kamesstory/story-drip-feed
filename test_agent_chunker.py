#!/usr/bin/env python3
"""
Compare AgentChunker vs LLMChunker on test files.

Usage:
    poetry run python test_agent_chunker.py examples/inputs/pale-lights-example-1.txt
"""
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from chunker import AgentChunker, LLMChunker

load_dotenv()


def compare_chunkers(file_path: str, target_words: int = 5000):
    """Compare AgentChunker and LLMChunker on the same text."""
    print(f"Testing chunkers on: {file_path}")
    print("="*80)

    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_filename = Path(file_path).stem
    output_dir = Path("test_outputs") / f"chunker_comparison_{input_filename}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Saving results to: {output_dir}\n")

    # Read test file
    with open(file_path, "r") as f:
        text = f.read()

    total_words = len(text.split())
    print(f"\nTotal words: {total_words}")
    print(f"Target words per chunk: {target_words}\n")

    # Save input text for reference
    with open(output_dir / "input.txt", "w") as f:
        f.write(text)

    # Test AgentChunker
    print("\n" + "="*80)
    print("TESTING AGENT CHUNKER")
    print("="*80)
    agent_chunks = None
    try:
        agent_chunker = AgentChunker(target_words=target_words)
        agent_chunks = agent_chunker.chunk_text(text)

        print(f"\n✅ AgentChunker created {len(agent_chunks)} chunks:")

        # Save chunks to separate files
        agent_dir = output_dir / "agent_chunks"
        agent_dir.mkdir(exist_ok=True)

        chunk_metadata = []
        for i, (chunk_text, word_count) in enumerate(agent_chunks, 1):
            print(f"  Chunk {i}: {word_count} words")
            preview = chunk_text[:100].replace('\n', ' ')
            print(f"    Preview: {preview}...")

            # Save chunk to file
            chunk_file = agent_dir / f"chunk_{i:02d}.txt"
            with open(chunk_file, "w") as f:
                f.write(chunk_text)

            chunk_metadata.append({
                "chunk_number": i,
                "word_count": word_count,
                "has_recap": "Previously:" in chunk_text,
                "file": str(chunk_file.name)
            })

        # Save metadata
        with open(agent_dir / "metadata.json", "w") as f:
            json.dump({
                "total_chunks": len(agent_chunks),
                "target_words": target_words,
                "chunks": chunk_metadata
            }, f, indent=2)

        print(f"\n📝 Saved {len(agent_chunks)} chunks to {agent_dir}")

    except Exception as e:
        print(f"\n❌ AgentChunker failed: {e}")
        with open(output_dir / "agent_error.txt", "w") as f:
            f.write(f"Error: {e}\n")

    # Test LLMChunker
    print("\n" + "="*80)
    print("TESTING LLM CHUNKER")
    print("="*80)
    llm_chunks = None
    try:
        llm_chunker = LLMChunker(target_words=target_words)
        llm_chunks = llm_chunker.chunk_text(text)

        print(f"\n✅ LLMChunker created {len(llm_chunks)} chunks:")

        # Save chunks to separate files
        llm_dir = output_dir / "llm_chunks"
        llm_dir.mkdir(exist_ok=True)

        chunk_metadata = []
        for i, (chunk_text, word_count) in enumerate(llm_chunks, 1):
            print(f"  Chunk {i}: {word_count} words")
            preview = chunk_text[:100].replace('\n', ' ')
            print(f"    Preview: {preview}...")

            # Save chunk to file
            chunk_file = llm_dir / f"chunk_{i:02d}.txt"
            with open(chunk_file, "w") as f:
                f.write(chunk_text)

            chunk_metadata.append({
                "chunk_number": i,
                "word_count": word_count,
                "has_recap": "Previously:" in chunk_text,
                "file": str(chunk_file.name)
            })

        # Save metadata
        with open(llm_dir / "metadata.json", "w") as f:
            json.dump({
                "total_chunks": len(llm_chunks),
                "target_words": target_words,
                "chunks": chunk_metadata
            }, f, indent=2)

        print(f"\n📝 Saved {len(llm_chunks)} chunks to {llm_dir}")

    except Exception as e:
        print(f"\n❌ LLMChunker failed: {e}")
        with open(output_dir / "llm_error.txt", "w") as f:
            f.write(f"Error: {e}\n")

    # Compare results
    print("\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)

    comparison = {
        "input_file": file_path,
        "total_words": total_words,
        "target_words": target_words,
        "timestamp": timestamp,
    }

    if agent_chunks and llm_chunks:
        print(f"\nAgentChunker: {len(agent_chunks)} chunks")
        print(f"LLMChunker:   {len(llm_chunks)} chunks")

        # Check for recaps
        agent_has_recaps = any("Previously:" in chunk[0] for chunk in agent_chunks)
        llm_has_recaps = any("Previously:" in chunk[0] for chunk in llm_chunks)

        print(f"\nAgentChunker has recaps: {agent_has_recaps}")
        print(f"LLMChunker has recaps:   {llm_has_recaps}")

        # Compare word count distribution
        agent_word_counts = [wc for _, wc in agent_chunks]
        llm_word_counts = [wc for _, wc in llm_chunks]

        print("\nWord count distribution:")
        print("AgentChunker:", agent_word_counts)
        print("LLMChunker:  ", llm_word_counts)

        comparison["agent"] = {
            "success": True,
            "chunk_count": len(agent_chunks),
            "has_recaps": agent_has_recaps,
            "word_counts": agent_word_counts
        }
        comparison["llm"] = {
            "success": True,
            "chunk_count": len(llm_chunks),
            "has_recaps": llm_has_recaps,
            "word_counts": llm_word_counts
        }
    elif agent_chunks:
        comparison["agent"] = {"success": True, "chunk_count": len(agent_chunks)}
        comparison["llm"] = {"success": False, "error": "Failed"}
    elif llm_chunks:
        comparison["agent"] = {"success": False, "error": "Failed"}
        comparison["llm"] = {"success": True, "chunk_count": len(llm_chunks)}
    else:
        comparison["agent"] = {"success": False, "error": "Failed"}
        comparison["llm"] = {"success": False, "error": "Failed"}

    # Save comparison summary
    with open(output_dir / "comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)

    print(f"\n✅ All results saved to: {output_dir}")
    print(f"   - input.txt: Original input text")
    print(f"   - agent_chunks/: AgentChunker output")
    print(f"   - llm_chunks/: LLMChunker output")
    print(f"   - comparison.json: Summary comparison")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: poetry run python test_agent_chunker.py <file_path>")
        print("Example: poetry run python test_agent_chunker.py examples/inputs/pale-lights-example-1.txt")
        sys.exit(1)

    # Check if ANTHROPIC_API_KEY is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set in environment")
        sys.exit(1)

    file_path = sys.argv[1]
    target_words = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

    compare_chunkers(file_path, target_words)
