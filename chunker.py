import re
from typing import List, Tuple
from abc import ABC, abstractmethod


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


# Placeholder for future intelligent chunking strategies
# class LLMChunker(ChunkingStrategy):
#     """Uses LLM to identify natural break points in stories."""
#     pass
#
# class HybridChunker(ChunkingStrategy):
#     """Combines pattern recognition with LLM analysis."""
#     pass


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
