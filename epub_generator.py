from ebooklib import epub
from typing import Optional
import os
from datetime import datetime
import re


class EPUBGenerator:
    """Generates EPUB files from text chunks."""

    def __init__(self, output_dir: str = "epubs"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def create_epub(
        self,
        text: str,
        title: str,
        author: str = "Unknown Author",
        chunk_number: Optional[int] = None,
        total_chunks: Optional[int] = None,
    ) -> str:
        """
        Create an EPUB file from text.

        Args:
            text: Story text content
            title: Story title
            author: Author name
            chunk_number: Chunk number (if part of series)
            total_chunks: Total number of chunks

        Returns:
            Path to generated EPUB file
        """
        book = epub.EpubBook()

        # Add metadata
        book.set_identifier(f"{title}_{chunk_number or 1}_{datetime.utcnow().timestamp()}")

        if chunk_number and total_chunks:
            full_title = f"{title} - Part {chunk_number}/{total_chunks}"
        elif chunk_number:
            full_title = f"{title} - Part {chunk_number}"
        else:
            full_title = title

        book.set_title(full_title)
        book.set_language("en")
        book.add_author(author)

        # Create chapter
        chapter = epub.EpubHtml(
            title=full_title,
            file_name="chapter.xhtml",
            lang="en"
        )

        # Convert text to HTML (handles both plain text and HTML input)
        html_content = self._prepare_html_content(text)
        chapter.content = f"<h1>{full_title}</h1>{html_content}"

        # Add chapter to book
        book.add_item(chapter)

        # Define table of contents
        book.toc = (chapter,)

        # Add navigation files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Define spine
        book.spine = ["nav", chapter]

        # Generate filename
        safe_title = self._sanitize_filename(title)
        if chunk_number:
            filename = f"{safe_title}_part{chunk_number}.epub"
        else:
            filename = f"{safe_title}.epub"

        filepath = os.path.join(self.output_dir, filename)

        # Write EPUB file
        epub.write_epub(filepath, book)

        return filepath

    def _prepare_html_content(self, text: str) -> str:
        """Prepare content for EPUB - handles both HTML and plain text."""
        # Check if content is already HTML
        if self._is_html(text):
            # Content is already HTML, use it directly
            return text
        else:
            # Plain text, convert to HTML paragraphs
            return self._text_to_html(text)

    def _is_html(self, text: str) -> bool:
        """Check if text contains HTML tags."""
        # Simple heuristic: if it has HTML tags, treat as HTML
        html_pattern = r'<(?:p|div|article|section|h[1-6]|br|span|em|strong|a)\b[^>]*>'
        return bool(re.search(html_pattern, text, re.IGNORECASE))

    def _text_to_html(self, text: str) -> str:
        """Convert plain text to HTML paragraphs."""
        paragraphs = text.split("\n\n")
        html_parts = []

        for para in paragraphs:
            para = para.strip()
            if para:
                # Preserve single line breaks within paragraphs
                para = para.replace("\n", "<br/>")
                html_parts.append(f"<p>{para}</p>")

        return "\n".join(html_parts)

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to remove invalid characters."""
        # Remove or replace invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")

        # Limit length
        max_length = 200
        if len(filename) > max_length:
            filename = filename[:max_length]

        return filename.strip()

    def create_multipart_epubs(
        self,
        chunks: list[tuple[str, int]],
        title: str,
        author: str = "Unknown Author",
    ) -> list[str]:
        """
        Create multiple EPUB files from text chunks.

        Args:
            chunks: List of (text, word_count) tuples
            title: Story title
            author: Author name

        Returns:
            List of paths to generated EPUB files
        """
        total_chunks = len(chunks)
        epub_paths = []

        for i, (chunk_text, _) in enumerate(chunks, start=1):
            epub_path = self.create_epub(
                text=chunk_text,
                title=title,
                author=author,
                chunk_number=i,
                total_chunks=total_chunks,
            )
            epub_paths.append(epub_path)

        return epub_paths
