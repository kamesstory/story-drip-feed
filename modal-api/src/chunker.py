"""
Story chunking module for Modal API.

Simplified version - agent-only chunking, no fallbacks.
Uses Claude Agent SDK for intelligent break point detection.
"""

import re
from typing import List, Tuple, Dict, Any
from src.supabase_storage import SupabaseStorage


def count_words(text: str) -> int:
    """Count words in text."""
    return len(re.findall(r'\b\w+\b', text))


class AgentChunker:
    """Uses Claude Agent SDK for context-aware chunking with intelligent break point detection."""

    def __init__(self, target_words: int = 8000, tolerance: float = 0.15):
        """
        Args:
            target_words: Target word count per chunk (default: 8000)
            tolerance: Acceptable deviation (0.15 = ±15%)
        """
        self.target_words = target_words
        self.min_words = int(target_words * (1 - tolerance))
        self.max_words = int(target_words * (1 + tolerance))

    async def chunk_story_from_storage(self, storage_id: str, content_url: str,
                                       storage: SupabaseStorage) -> Dict[str, Any]:
        """
        Read story content from Supabase, chunk it, and save chunks back to Supabase.

        Args:
            storage_id: Unique ID for this story
            content_url: Storage path to content file
            storage: SupabaseStorage instance

        Returns:
            Dict with:
            - chunks: List of chunk info dicts (url, word_count, chunk_number)
            - total_chunks: Total number of chunks
            - total_words: Total word count across all chunks
            - chunking_strategy: Name of strategy used

        Raises:
            Exception: If agent chunking fails
        """
        # Read content from Supabase
        content = storage.download_text(content_url)

        # Chunk the content using agent
        chunks = await self.chunk_text(content)

        # Save each chunk to Supabase
        chunk_info = []
        total_words = 0
        for i, (chunk_text, word_count) in enumerate(chunks, 1):
            chunk_path = f"story-chunks/{storage_id}/chunk_{i:03d}.txt"
            storage.upload_text(chunk_path, chunk_text)
            
            chunk_info.append({
                "chunk_number": i,
                "url": chunk_path,
                "word_count": word_count
            })
            total_words += word_count

        print(f"✅ Created {len(chunks)} chunks for story {storage_id}")
        
        return {
            "chunks": chunk_info,
            "total_chunks": len(chunks),
            "total_words": total_words,
            "chunking_strategy": "AgentChunker"
        }

    async def chunk_text(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text using Agent SDK for holistic story analysis.

        Returns:
            List of tuples (chunk_text, word_count)

        Raises:
            Exception: If agent fails or returns no chunks
        """
        try:
            chunks = await self._chunk_with_agent(text)

            if not chunks:
                raise Exception("Agent returned no chunks")

            return chunks

        except ImportError:
            raise Exception("claude-agent-sdk not installed")
        except Exception as e:
            raise Exception(f"Agent chunking failed: {str(e)}")

    async def _chunk_with_agent(self, text: str) -> List[Tuple[str, int]]:
        """Use agent to analyze full story and identify all break points."""
        import os
        from anthropic import AsyncAnthropic
        
        client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        
        total_words = count_words(text)
        estimated_chunks = max(1, round(total_words / self.target_words))

        paragraphs = re.split(r'\n\s*\n', text)
        numbered_text = ""
        paragraph_positions = {}

        current_pos = 0
        for i, para in enumerate(paragraphs):
            if para.strip():
                para_num = i + 1
                numbered_text += f"[Para {para_num}]\n{para}\n\n"
                paragraph_positions[para_num] = current_pos
                current_pos += len(para) + 2

        max_preview_length = 100000
        if len(numbered_text) > max_preview_length:
            numbered_text = numbered_text[:max_preview_length] + "\n\n[...text truncated for length...]"

        prompt = f"""Analyze this story and identify natural break point(s) for splitting into reading chunks.

Target: ~{self.target_words} words per chunk (flexible)
Total: ~{total_words} words, {len(paragraphs)} paragraphs
Suggested chunks: ~{estimated_chunks}

CRITICAL PRIORITIES - Look for these IN ORDER:
1. **EXPLICIT SCENE BREAKS** - Paragraphs containing ONLY "--", "* * *", or "═══" (these are MANDATORY breaks, use them even if far from target)
2. **Scene transitions** - Character moves to completely different location or significant time passage
3. **Resolution of conflicts** - After action sequence/fight ENDS and before next begins
4. **Perspective shifts** - POV changes to different character
5. **Completed emotional arcs** - After character completes internal transformation, NOT during it

EXPLICITLY AVOID (these are BAD breaks):
- Mid-combat: Character actively fighting/fleeing
- Mid-dialogue: Characters in conversation
- Mid-transformation: Character in middle of emotional/psychological change
- Mid-climax: During peak of tension (wait for resolution)
- Mid-flashback: Inside parenthetical glimpses or memory sequences

FLEXIBILITY RULES:
- Explicit scene breaks (---, * * *) ALWAYS take priority, even if chunks are unequal
- Can create chunks as small as 2000 words or as large as 8000 words if it hits a proper scene break
- Better to have 2500 + 4500 word split at a real scene break than 3500 + 3500 at a bad break
- If multiple good breaks exist, prefer the one closest to target
- Narrative coherence > word count balance

For each break point, respond:
BREAK_PARA: <number>
REASON: Scene/action that ENDS before break | Scene/action that BEGINS after break

If no breaks needed (story too short): NO_BREAKS_NEEDED

Text with paragraph numbers:
{numbered_text}"""

        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = response.content[0].text

        print("\n" + "="*80)
        print("AGENT CHUNKING ANALYSIS:")
        print("="*80)
        print(response_text)
        print("="*80 + "\n")

        if "NO_BREAKS_NEEDED" in response_text or "NO BREAKS" in response_text:
            return [(text, count_words(text))]

        break_points = []
        for line in response_text.split('\n'):
            if 'BREAK_PARA:' in line:
                try:
                    para_num_str = line.split('BREAK_PARA:')[1].strip()
                    para_num = int(''.join(filter(str.isdigit, para_num_str)))

                    if para_num in paragraph_positions:
                        pos = paragraph_positions[para_num]

                        remaining_text = text[pos:]
                        remaining_words = count_words(remaining_text)
                        if remaining_words < 500:
                            print(f"Skipping break at paragraph {para_num} - would create tiny {remaining_words} word chunk")
                            continue

                        print(f"Agent identified break at paragraph {para_num} (position {pos})")
                        break_points.append(pos)
                except (ValueError, IndexError) as e:
                    print(f"Error parsing break point: {e}")
                    continue

        if not break_points:
            print("Warning: No valid break points identified, using story as single chunk")
            return [(text, count_words(text))]

        return self._split_at_break_points(text, break_points)

    def _split_at_break_points(self, text: str, break_points: List[int]) -> List[Tuple[str, int]]:
        """Split text at the identified break points and add recaps."""
        if not break_points:
            return [(text, count_words(text))]

        para_boundaries = [0]
        for match in re.finditer(r'\n\s*\n', text):
            para_boundaries.append(match.end())
        para_boundaries.append(len(text))

        adjusted_breaks = [0]
        max_adjustment = 2000

        for break_point in break_points:
            nearby_boundaries = [
                pb for pb in para_boundaries
                if abs(pb - break_point) <= max_adjustment
            ]

            if nearby_boundaries:
                closest = min(nearby_boundaries, key=lambda x: abs(x - break_point))
                if closest not in adjusted_breaks:
                    adjusted_breaks.append(closest)
            else:
                if break_point not in adjusted_breaks:
                    adjusted_breaks.append(break_point)

        adjusted_breaks.append(len(text))
        adjusted_breaks = sorted(set(adjusted_breaks))

        chunks = []
        previous_chunk_text = None

        for i in range(len(adjusted_breaks) - 1):
            start = adjusted_breaks[i]
            end = adjusted_breaks[i + 1]
            chunk_text = text[start:end].strip()

            if chunk_text:
                if previous_chunk_text and i > 0:
                    recap = self._create_simple_recap(previous_chunk_text)
                    chunk_text = recap + "\n\n" + chunk_text

                word_count = count_words(chunk_text)
                chunks.append((chunk_text, word_count))
                previous_chunk_text = text[start:end].strip()

        return chunks

    def _create_simple_recap(self, previous_chunk: str) -> str:
        """Create simple recap from last few sentences."""
        sentences = re.split(r'(?<=[.!?])\s+', previous_chunk)

        recap_sentences = []
        word_count = 0
        target_words = 250

        for sentence in reversed(sentences):
            sent_words = count_words(sentence)
            if word_count + sent_words > target_words and recap_sentences:
                break
            recap_sentences.insert(0, sentence)
            word_count += sent_words
            if len(recap_sentences) >= 10:
                break

        recap_text = " ".join(recap_sentences).strip()

        return f"───────────────────────────────────────\n*Previously:*\n> {recap_text}\n───────────────────────────────────────"


async def chunk_story(content_url: str, storage_id: str, target_words: int,
                      storage: SupabaseStorage) -> Dict[str, Any]:
    """
    Convenience function to chunk a story from Supabase Storage.
    Always uses AgentChunker, fails loudly if issues.

    Args:
        content_url: Storage path to content file
        storage_id: Unique ID for this story
        target_words: Target words per chunk
        storage: SupabaseStorage instance

    Returns:
        Dict with chunks info

    Raises:
        Exception: If chunking fails
    """
    chunker = AgentChunker(target_words=target_words)
    return await chunker.chunk_story_from_storage(storage_id, content_url, storage)
