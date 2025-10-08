"""
File storage manager for Modal volume.

Handles all file operations for stories, chunks, and EPUBs on the persistent volume.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional


class FileStorage:
    """Manages file storage on Modal volume."""

    def __init__(self, base_path: str = "/data"):
        """
        Initialize file storage.

        Args:
            base_path: Base path for Modal volume (default: /data)
        """
        self.base_path = Path(base_path)
        self.raw_path = self.base_path / "raw"
        self.chunks_path = self.base_path / "chunks"
        self.epubs_path = self.base_path / "epubs"

        # Create base directories
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all base directories exist."""
        for path in [self.raw_path, self.chunks_path, self.epubs_path]:
            path.mkdir(parents=True, exist_ok=True)

    def create_story_directory(self, story_id: int) -> Path:
        """Create directory for a story."""
        story_dir = self.raw_path / f"story_{story_id:06d}"
        story_dir.mkdir(parents=True, exist_ok=True)
        return story_dir

    def save_original_email(self, story_id: int, email_text: str) -> str:
        """Save original email for debugging."""
        story_dir = self.create_story_directory(story_id)
        email_path = story_dir / "original_email.txt"
        email_path.write_text(email_text)
        return str(email_path.relative_to(self.base_path))

    def save_story_content(self, story_id: int, content: str) -> str:
        """
        Save clean story content.

        Returns:
            Relative path from base_path
        """
        story_dir = self.create_story_directory(story_id)
        content_path = story_dir / "content.txt"
        content_path.write_text(content)
        return str(content_path.relative_to(self.base_path))

    def save_metadata(self, story_id: int, metadata: Dict[str, Any]) -> str:
        """
        Save story metadata as YAML.

        Returns:
            Relative path from base_path
        """
        story_dir = self.create_story_directory(story_id)
        metadata_path = story_dir / "metadata.yaml"
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f, default_flow_style=False)
        return str(metadata_path.relative_to(self.base_path))

    def read_story_content(self, content_path: str) -> str:
        """Read story content from relative path."""
        full_path = self.base_path / content_path
        return full_path.read_text()

    def read_metadata(self, metadata_path: str) -> Dict[str, Any]:
        """Read metadata from relative path."""
        full_path = self.base_path / metadata_path
        with open(full_path, 'r') as f:
            return yaml.safe_load(f)

    def create_chunks_directory(self, story_id: int) -> Path:
        """Create directory for story chunks."""
        chunks_dir = self.chunks_path / f"story_{story_id:06d}"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        return chunks_dir

    def save_chunk(self, story_id: int, chunk_number: int, content: str) -> str:
        """
        Save a chunk.

        Returns:
            Relative path from base_path
        """
        chunks_dir = self.create_chunks_directory(story_id)
        chunk_path = chunks_dir / f"chunk_{chunk_number:03d}.txt"
        chunk_path.write_text(content)
        return str(chunk_path.relative_to(self.base_path))

    def save_chunk_manifest(self, story_id: int, manifest: Dict[str, Any]) -> str:
        """
        Save chunk manifest with metadata about all chunks.

        Returns:
            Relative path from base_path
        """
        chunks_dir = self.create_chunks_directory(story_id)
        manifest_path = chunks_dir / "chunk_manifest.yaml"
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False)
        return str(manifest_path.relative_to(self.base_path))

    def read_chunk(self, chunk_path: str) -> str:
        """Read chunk content from relative path."""
        full_path = self.base_path / chunk_path
        return full_path.read_text()

    def read_chunk_manifest(self, manifest_path: str) -> Dict[str, Any]:
        """Read chunk manifest from relative path."""
        full_path = self.base_path / manifest_path
        with open(full_path, 'r') as f:
            return yaml.safe_load(f)

    def list_chunks(self, story_id: int) -> List[str]:
        """List all chunk paths for a story (relative paths)."""
        chunks_dir = self.chunks_path / f"story_{story_id:06d}"
        if not chunks_dir.exists():
            return []

        chunk_files = sorted(chunks_dir.glob("chunk_*.txt"))
        return [str(p.relative_to(self.base_path)) for p in chunk_files]

    def save_epub(self, story_id: int, chunk_number: int, epub_data: bytes) -> str:
        """
        Save EPUB file.

        Returns:
            Relative path from base_path
        """
        self.epubs_path.mkdir(parents=True, exist_ok=True)
        epub_path = self.epubs_path / f"story_{story_id:06d}_chunk_{chunk_number:03d}.epub"
        epub_path.write_bytes(epub_data)
        return str(epub_path.relative_to(self.base_path))

    def get_epub_path(self, epub_relative_path: str) -> Path:
        """Get full path to EPUB file."""
        return self.base_path / epub_relative_path

    def get_absolute_path(self, relative_path: str) -> Path:
        """Convert relative path to absolute path."""
        return self.base_path / relative_path


# For local development (outside Modal)
class LocalFileStorage(FileStorage):
    """File storage for local development."""

    def __init__(self, base_path: str = "./local_data"):
        """Use local directory instead of Modal volume."""
        super().__init__(base_path)
