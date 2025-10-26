"""
Story chunking module for Modal API.

Refactored version - uses Supabase Storage instead of file-based storage.
Returns storage URLs instead of file paths.
"""

import re
import os
from typing import List, Tuple, Optional, Dict, Any
from abc import ABC, abstractmethod
import anthropic
from src.supabase_storage import SupabaseStorage


class ChunkingStrategy(ABC):
    """Abstract base class for text chunking strategies."""

    @abstractmethod
    def chunk_text(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text into segments.

        Returns:
            List of tuples (chunk_text, word_count)
        """
        pass

    def chunk_story_from_storage(self, storage_id: str, content_url: str,
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
        """
        # Read content from Supabase
        content = storage.download_text(content_url)

        # Chunk the content
        chunks = self.chunk_text(content)

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
            "chunking_strategy": self.__class__.__name__
        }

    def count_words(self, text: str) -> int:
        """Count words in text."""
        return len(re.findall(r'\b\w+\b', text))


class SimpleChunker(ChunkingStrategy):
    """Simple paragraph/word-based chunking strategy."""

    def __init__(self, target_words: int = 10000, tolerance: float = 0.1):
        """
        Args:
            target_words: Target word count per chunk
            tolerance: Acceptable deviation (0.1 = ±10%)
        """
        self.target_words = target_words
        self.min_words = int(target_words * (1 - tolerance))
        self.max_words = int(target_words * (1 + tolerance))

    def split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def chunk_text(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text into segments of approximately target_words.

        Returns:
            List of tuples (chunk_text, word_count)
        """
        paragraphs = self.split_into_paragraphs(text)
        chunks = []
        current_chunk = []
        current_word_count = 0

        for paragraph in paragraphs:
            para_words = self.count_words(paragraph)

            # If single paragraph exceeds max_words, split it further
            if para_words > self.max_words:
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append((chunk_text, current_word_count))
                    current_chunk = []
                    current_word_count = 0

                sentences = self._split_large_paragraph(paragraph)
                for sentence in sentences:
                    sent_words = self.count_words(sentence)
                    if current_word_count + sent_words > self.max_words and current_chunk:
                        chunk_text = '\n\n'.join(current_chunk)
                        chunks.append((chunk_text, current_word_count))
                        current_chunk = [sentence]
                        current_word_count = sent_words
                    else:
                        current_chunk.append(sentence)
                        current_word_count += sent_words
                continue

            if current_word_count + para_words > self.max_words and current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append((chunk_text, current_word_count))
                current_chunk = [paragraph]
                current_word_count = para_words
            else:
                current_chunk.append(paragraph)
                current_word_count += para_words

                if current_word_count >= self.min_words:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append((chunk_text, current_word_count))
                    current_chunk = []
                    current_word_count = 0

        # Add remaining text as final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append((chunk_text, current_word_count))

        return chunks

    def _split_large_paragraph(self, paragraph: str) -> List[str]:
        """Split a large paragraph into sentences."""
        sentences = re.split(r'([.!?]+\s+)', paragraph)
        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                result.append(sentences[i] + sentences[i + 1])
            else:
                result.append(sentences[i])
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1])
        return [s.strip() for s in result if s.strip()]


class LLMChunker(ChunkingStrategy):
    """Uses LLM (Claude) to identify natural break points in stories."""

    def __init__(
        self,
        target_words: int = 5000,
        tolerance: float = 0.1,
        api_key: Optional[str] = None,
        fallback_to_simple: bool = True,
    ):
        """
        Args:
            target_words: Target word count per chunk
            tolerance: Acceptable deviation (0.1 = ±10%)
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            fallback_to_simple: If True, fall back to SimpleChunker on API failure
        """
        self.target_words = target_words
        self.min_words = int(target_words * (1 - tolerance))
        self.max_words = int(target_words * (1 + tolerance))
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.fallback_to_simple = fallback_to_simple
        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None

    def chunk_text(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text using LLM to identify natural break points.

        Returns:
            List of tuples (chunk_text, word_count)
        """
        if not self.client:
            print("Warning: No Anthropic API key found, falling back to SimpleChunker")
            return self._fallback_chunk(text)

        try:
            break_points = self._find_break_points(text)

            if not break_points:
                print("Warning: No break points identified, falling back to SimpleChunker")
                return self._fallback_chunk(text)

            chunks = self._split_at_break_points(text, break_points)
            return chunks

        except Exception as e:
            print(f"Error using LLM chunker: {e}")
            if self.fallback_to_simple:
                print("Falling back to SimpleChunker")
                return self._fallback_chunk(text)
            raise

    def _find_break_points(self, text: str) -> List[int]:
        """Use Claude to identify natural break points in the text."""
        total_words = self.count_words(text)
        estimated_chunks = max(1, round(total_words / self.target_words))

        paragraphs = re.split(r'\n\s*\n', text)
        numbered_text = ""
        paragraph_positions = [0]
        current_pos = 0

        for i, para in enumerate(paragraphs):
            if para.strip():
                numbered_text += f"[Para {i+1}]\n{para}\n\n"
                paragraph_positions.append(current_pos)
                current_pos += len(para) + 2

        prompt = f"""Analyze this story and identify natural break point(s) for splitting into reading chunks.

Target: ~{self.target_words} words per chunk (flexible)
Total: ~{total_words} words, {len(paragraphs)} paragraphs

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

For each break point:
BREAK_PARA: <number>
REASON: Scene/action that ENDS before break | Scene/action that BEGINS after break

Text with paragraph numbers:
{numbered_text}"""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        print("\n" + "="*80)
        print("CLAUDE'S ANALYSIS:")
        print("="*80)
        print(response_text)
        print("="*80 + "\n")

        if "NO_BREAKS_NEEDED" in response_text or "NO BREAKS" in response_text:
            return []

        break_points = []
        for line in response_text.split('\n'):
            if line.startswith('BREAK_PARA:'):
                try:
                    para_num_str = line.split('BREAK_PARA:')[1].strip()
                    para_num = int(''.join(filter(str.isdigit, para_num_str)))

                    if 1 <= para_num <= len(paragraphs):
                        pos = paragraph_positions[para_num] if para_num < len(paragraph_positions) else paragraph_positions[-1]

                        remaining_text = text[pos:]
                        remaining_words = self.count_words(remaining_text)
                        if remaining_words < 500:
                            print(f"Skipping break at paragraph {para_num} - would create tiny {remaining_words} word chunk")
                            continue

                        print(f"LLM identified break at paragraph {para_num} (position {pos})")
                        break_points.append(pos)
                except (ValueError, IndexError):
                    continue

        return sorted(break_points)

    def _split_at_break_points(self, text: str, break_points: List[int]) -> List[Tuple[str, int]]:
        """Split text at the identified break points."""
        if not break_points:
            return [(text, self.count_words(text))]

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
                    recap = self._create_recap(previous_chunk_text)
                    chunk_text = recap + "\n\n" + chunk_text

                word_count = self.count_words(chunk_text)
                chunks.append((chunk_text, word_count))
                previous_chunk_text = text[start:end].strip()

        return chunks

    def _create_recap(self, previous_chunk: str) -> str:
        """Create a recap from the end of the previous chunk."""
        sentences = re.split(r'(?<=[.!?])\s+', previous_chunk)

        recap_sentences = []
        word_count = 0
        target_words = 250

        for sentence in reversed(sentences):
            sent_words = self.count_words(sentence)
            if word_count + sent_words > target_words and recap_sentences:
                break
            recap_sentences.insert(0, sentence)
            word_count += sent_words
            if len(recap_sentences) >= 10:
                break

        recap_text = " ".join(recap_sentences).strip()

        return f"───────────────────────────────────────\n*Previously:*\n> {recap_text}\n───────────────────────────────────────"

    def _fallback_chunk(self, text: str) -> List[Tuple[str, int]]:
        """Fallback to SimpleChunker."""
        simple = SimpleChunker(target_words=self.target_words)
        return simple.chunk_text(text)


class AgentChunker(ChunkingStrategy):
    """Uses Claude Agent SDK for more context-aware chunking with full story analysis."""

    def __init__(
        self,
        target_words: int = 8000,
        tolerance: float = 0.15,
        fallback_to_simple: bool = True,
    ):
        """
        Args:
            target_words: Target word count per chunk (default: 8000)
            tolerance: Acceptable deviation (0.15 = ±15%)
            fallback_to_simple: If True, fall back to SimpleChunker on failure
        """
        self.target_words = target_words
        self.min_words = int(target_words * (1 - tolerance))
        self.max_words = int(target_words * (1 + tolerance))
        self.fallback_to_simple = fallback_to_simple

    def chunk_text(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text using Agent SDK for holistic story analysis.

        Returns:
            List of tuples (chunk_text, word_count)
        """
        try:
            from claude_agent_sdk import query
            import anyio

            chunks = anyio.run(self._chunk_with_agent, text)

            if not chunks:
                print("Warning: Agent returned no chunks, falling back to SimpleChunker")
                return self._fallback_chunk(text)

            return chunks

        except ImportError:
            print("Warning: claude-agent-sdk not installed, falling back to SimpleChunker")
            return self._fallback_chunk(text)
        except Exception as e:
            print(f"Error using Agent chunker: {e}")
            if self.fallback_to_simple:
                print("Falling back to SimpleChunker")
                return self._fallback_chunk(text)
            raise

    async def _chunk_with_agent(self, text: str) -> List[Tuple[str, int]]:
        """Use agent to analyze full story and identify all break points."""
        from claude_agent_sdk import query

        total_words = self.count_words(text)
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

        response_parts = []
        async for message in query(prompt=prompt):
            response_parts.append(str(message))

        response_text = "".join(response_parts)

        print("\n" + "="*80)
        print("AGENT CHUNKING ANALYSIS:")
        print("="*80)
        print(response_text)
        print("="*80 + "\n")

        if 'result=' in response_text:
            result_start = response_text.find('result=') + 8
            result_end = response_text.rfind("')")
            if result_end > result_start:
                response_text = response_text[result_start:result_end]
                print(f"\n{'='*80}\nEXTRACTED RESULT:\n{'='*80}\n{response_text}\n{'='*80}\n")

        if "NO_BREAKS_NEEDED" in response_text or "NO BREAKS" in response_text:
            return [(text, self.count_words(text))]

        break_points = []
        for line in response_text.split('\n'):
            if 'BREAK_PARA:' in line:
                try:
                    para_num_str = line.split('BREAK_PARA:')[1].strip()
                    para_num = int(''.join(filter(str.isdigit, para_num_str)))

                    if para_num in paragraph_positions:
                        pos = paragraph_positions[para_num]

                        remaining_text = text[pos:]
                        remaining_words = self.count_words(remaining_text)
                        if remaining_words < 500:
                            print(f"Skipping break at paragraph {para_num} - would create tiny {remaining_words} word chunk")
                            continue

                        print(f"Agent identified break at paragraph {para_num} (position {pos})")
                        break_points.append(pos)
                except (ValueError, IndexError) as e:
                    print(f"Error parsing break point: {e}")
                    continue

        if not break_points:
            print("Warning: No valid break points identified")
            return [(text, self.count_words(text))]

        return self._split_at_break_points(text, break_points)

    def _split_at_break_points(self, text: str, break_points: List[int]) -> List[Tuple[str, int]]:
        """Split text at the identified break points and add recaps."""
        if not break_points:
            return [(text, self.count_words(text))]

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

                word_count = self.count_words(chunk_text)
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
            sent_words = self.count_words(sentence)
            if word_count + sent_words > target_words and recap_sentences:
                break
            recap_sentences.insert(0, sentence)
            word_count += sent_words
            if len(recap_sentences) >= 10:
                break

        recap_text = " ".join(recap_sentences).strip()

        return f"───────────────────────────────────────\n*Previously:*\n> {recap_text}\n───────────────────────────────────────"

    def _fallback_chunk(self, text: str) -> List[Tuple[str, int]]:
        """Fallback to SimpleChunker."""
        simple = SimpleChunker(target_words=self.target_words)
        return simple.chunk_text(text)


def chunk_story(content_url: str, storage_id: str, target_words: int,
                storage: SupabaseStorage, strategy: Optional[ChunkingStrategy] = None) -> Dict[str, Any]:
    """
    Convenience function to chunk a story from Supabase Storage.

    Args:
        content_url: Storage path to content file
        storage_id: Unique ID for this story
        target_words: Target words per chunk
        storage: SupabaseStorage instance
        strategy: Chunking strategy to use (defaults to AgentChunker)

    Returns:
        Dict with chunks info
    """
    if strategy is None:
        # Default to AgentChunker
        strategy = AgentChunker(target_words=target_words, fallback_to_simple=True)
    
    return strategy.chunk_story_from_storage(storage_id, content_url, storage)

