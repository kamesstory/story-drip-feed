import re
import os
from typing import List, Tuple, Optional
from abc import ABC, abstractmethod
import anthropic


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
                # Save current chunk if it exists
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append((chunk_text, current_word_count))
                    current_chunk = []
                    current_word_count = 0

                # Split large paragraph into sentences
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

            # Check if adding this paragraph would exceed max_words
            if current_word_count + para_words > self.max_words and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append((chunk_text, current_word_count))
                current_chunk = [paragraph]
                current_word_count = para_words
            else:
                # Add to current chunk
                current_chunk.append(paragraph)
                current_word_count += para_words

                # If we've reached target, consider ending chunk at paragraph boundary
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
            # Analyze text with Claude to find break points
            break_points = self._find_break_points(text)

            if not break_points:
                print("Warning: No break points identified, falling back to SimpleChunker")
                return self._fallback_chunk(text)

            # Split text at identified break points
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

        # Calculate approximately how many chunks we need
        estimated_chunks = max(1, round(total_words / self.target_words))

        # Split into paragraphs and number them
        paragraphs = re.split(r'\n\s*\n', text)
        numbered_text = ""
        paragraph_positions = [0]  # Character positions where each paragraph starts
        current_pos = 0

        for i, para in enumerate(paragraphs):
            if para.strip():
                numbered_text += f"[Para {i+1}]\n{para}\n\n"
                paragraph_positions.append(current_pos)
                current_pos += len(para) + 2  # +2 for the double newline

        prompt = f"""Analyze this story and identify {estimated_chunks - 1} natural break point(s) for splitting into reading chunks.

Target: ~{self.target_words} words per chunk (preferred range: {self.min_words}-{self.max_words} words)
Total: ~{total_words} words, {len(paragraphs)} paragraphs

CRITICAL PRIORITIES - Look for these IN ORDER:
1. **Scene transitions** - Character moves to a completely different location or time passes significantly
2. **Resolution of conflicts** - After an action sequence/fight ENDS and before the next begins
3. **Perspective shifts** - POV changes to a different character
4. **Completed emotional arcs** - After a character completes an internal transformation/realization, NOT during it

EXPLICITLY AVOID (these are BAD breaks):
- Mid-combat: Character is actively fighting/fleeing
- Mid-dialogue: Characters are in conversation
- Mid-transformation: Character is in the middle of an emotional/psychological change
- Mid-climax: During the peak of tension (wait for resolution)
- Mid-flashback: Inside parenthetical glimpses or memory sequences

GOOD break examples:
- "She left the room." → [break] → "The next morning..."
- "The fight was over." → [break] → "Later, in the camp..."
- Character finishes internal revelation → [break] → Returns to external action

If no {estimated_chunks - 1} ideal breaks exist within range:
- Prefer FEWER breaks with LONGER chunks over bad breaks
- Can go 20-30% over target to hit a proper scene boundary
- Narrative flow matters more than exact word counts

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

        # Print Claude's reasoning for debugging
        print("\n" + "="*80)
        print("CLAUDE'S ANALYSIS:")
        print("="*80)
        print(response_text)
        print("="*80 + "\n")

        if "NO_BREAKS_NEEDED" in response_text or "NO BREAKS" in response_text:
            return []

        # Parse paragraph numbers from response
        break_points = []
        for line in response_text.split('\n'):
            if line.startswith('BREAK_PARA:'):
                try:
                    para_num_str = line.split('BREAK_PARA:')[1].strip()
                    para_num = int(''.join(filter(str.isdigit, para_num_str)))

                    if 1 <= para_num <= len(paragraphs):
                        # Find position of this paragraph in original text
                        pos = paragraph_positions[para_num] if para_num < len(paragraph_positions) else paragraph_positions[-1]
                        print(f"LLM identified break at paragraph {para_num} (position {pos})")
                        break_points.append(pos)
                except (ValueError, IndexError) as e:
                    continue

        return sorted(break_points)

    def _split_at_break_points(self, text: str, break_points: List[int]) -> List[Tuple[str, int]]:
        """Split text at the identified break points, adjusting to paragraph boundaries."""
        if not break_points:
            return [(text, self.count_words(text))]

        # Find paragraph boundaries (double newlines)
        para_boundaries = [0]
        for match in re.finditer(r'\n\s*\n', text):
            para_boundaries.append(match.end())
        para_boundaries.append(len(text))

        # Adjust each break point to nearest paragraph boundary within reasonable distance
        adjusted_breaks = [0]
        max_adjustment = 2000  # Don't adjust more than 2000 characters away

        for break_point in break_points:
            # Find paragraph boundaries within reasonable distance
            nearby_boundaries = [
                pb for pb in para_boundaries
                if abs(pb - break_point) <= max_adjustment
            ]

            if nearby_boundaries:
                # Find closest paragraph boundary within range
                closest = min(nearby_boundaries, key=lambda x: abs(x - break_point))
                if closest not in adjusted_breaks:
                    adjusted_breaks.append(closest)
            else:
                # No nearby paragraph boundary, use the break point as-is
                if break_point not in adjusted_breaks:
                    adjusted_breaks.append(break_point)

        adjusted_breaks.append(len(text))
        adjusted_breaks = sorted(set(adjusted_breaks))

        # Create chunks with recaps
        chunks = []
        previous_chunk_text = None

        for i in range(len(adjusted_breaks) - 1):
            start = adjusted_breaks[i]
            end = adjusted_breaks[i + 1]
            chunk_text = text[start:end].strip()

            if chunk_text:
                # Add recap from previous chunk (except for first chunk)
                if previous_chunk_text and i > 0:
                    recap = self._create_recap(previous_chunk_text)
                    chunk_text = recap + "\n\n" + chunk_text

                word_count = self.count_words(chunk_text)
                chunks.append((chunk_text, word_count))
                previous_chunk_text = text[start:end].strip()  # Store original without recap

        return chunks

    def _create_recap(self, previous_chunk: str) -> str:
        """Create a recap from the end of the previous chunk."""
        # Get last 3-5 sentences or last ~150 words
        sentences = re.split(r'(?<=[.!?])\s+', previous_chunk)

        # Take last 3-5 sentences, but cap at ~150 words
        recap_sentences = []
        word_count = 0
        target_words = 150

        for sentence in reversed(sentences):
            sent_words = self.count_words(sentence)
            if word_count + sent_words > target_words and recap_sentences:
                break
            recap_sentences.insert(0, sentence)
            word_count += sent_words
            if len(recap_sentences) >= 5:
                break

        recap_text = " ".join(recap_sentences).strip()

        # Format as a recap block
        return f"───────────────────────────────────────\n*Previously:*\n> {recap_text}\n───────────────────────────────────────"

    def _fallback_chunk(self, text: str) -> List[Tuple[str, int]]:
        """Fallback to SimpleChunker."""
        simple = SimpleChunker(target_words=self.target_words)
        return simple.chunk_text(text)


def chunk_story(text: str, target_words: int = 10000,
                strategy: ChunkingStrategy = None) -> List[Tuple[str, int]]:
    """
    Convenience function to chunk a story.

    Args:
        text: Story text to chunk
        target_words: Target words per chunk
        strategy: Chunking strategy to use (defaults to SimpleChunker)

    Returns:
        List of tuples (chunk_text, word_count)
    """
    if strategy is None:
        strategy = SimpleChunker(target_words=target_words)
    return strategy.chunk_text(text)
