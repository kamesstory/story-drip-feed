"""
Supabase Storage client for Modal API.

Handles uploading and downloading text content, chunks, and metadata to/from Supabase Storage.
Uses a flat bucket structure with paths to organize content.
"""

import os
import json
from typing import Dict, Any, Optional
from supabase import create_client, Client


class SupabaseStorage:
    """Client for Supabase Storage operations."""

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        """
        Initialize Supabase Storage client.

        Args:
            supabase_url: Supabase project URL (defaults to SUPABASE_URL env var)
            supabase_key: Supabase service role key (defaults to SUPABASE_SERVICE_ROLE_KEY env var)
        """
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.bucket = "story-storage"  # Single bucket for all story-related files

    def upload_text(self, path: str, content: str) -> str:
        """
        Upload text content to Supabase Storage.

        Args:
            path: Storage path (e.g., "story-content/abc123/content.txt")
            content: Text content to upload

        Returns:
            Storage path of uploaded file
        """
        try:
            # Upload as text file
            self.client.storage.from_(self.bucket).upload(
                path=path,
                file=content.encode("utf-8"),
                file_options={"content-type": "text/plain; charset=utf-8", "upsert": "true"}
            )
            print(f"✅ Uploaded text to {path}")
            return path
        except Exception as e:
            print(f"❌ Failed to upload text to {path}: {e}")
            raise

    def download_text(self, path: str) -> str:
        """
        Download text content from Supabase Storage.

        Args:
            path: Storage path (e.g., "story-content/abc123/content.txt")

        Returns:
            Text content as string
        """
        try:
            response = self.client.storage.from_(self.bucket).download(path)
            content = response.decode("utf-8")
            print(f"✅ Downloaded text from {path} ({len(content)} chars)")
            return content
        except Exception as e:
            print(f"❌ Failed to download text from {path}: {e}")
            raise

    def upload_json(self, path: str, data: Dict[str, Any]) -> str:
        """
        Upload JSON data to Supabase Storage.

        Args:
            path: Storage path (e.g., "story-metadata/abc123/metadata.json")
            data: Dictionary to upload as JSON

        Returns:
            Storage path of uploaded file
        """
        try:
            json_content = json.dumps(data, indent=2)
            self.client.storage.from_(self.bucket).upload(
                path=path,
                file=json_content.encode("utf-8"),
                file_options={"content-type": "application/json", "upsert": "true"}
            )
            print(f"✅ Uploaded JSON to {path}")
            return path
        except Exception as e:
            print(f"❌ Failed to upload JSON to {path}: {e}")
            raise

    def download_json(self, path: str) -> Dict[str, Any]:
        """
        Download JSON data from Supabase Storage.

        Args:
            path: Storage path (e.g., "story-metadata/abc123/metadata.json")

        Returns:
            Parsed JSON as dictionary
        """
        try:
            response = self.client.storage.from_(self.bucket).download(path)
            data = json.loads(response.decode("utf-8"))
            print(f"✅ Downloaded JSON from {path}")
            return data
        except Exception as e:
            print(f"❌ Failed to download JSON from {path}: {e}")
            raise

    def file_exists(self, path: str) -> bool:
        """
        Check if a file exists in Supabase Storage.

        Args:
            path: Storage path to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            # Try to get file info - if it doesn't throw, file exists
            self.client.storage.from_(self.bucket).download(path)
            return True
        except Exception:
            return False

    def delete_file(self, path: str) -> None:
        """
        Delete a file from Supabase Storage.

        Args:
            path: Storage path to delete
        """
        try:
            self.client.storage.from_(self.bucket).remove([path])
            print(f"✅ Deleted {path}")
        except Exception as e:
            print(f"❌ Failed to delete {path}: {e}")
            raise

    def list_files(self, prefix: str = "", limit: int = 100) -> list:
        """
        List files in Supabase Storage with optional prefix filter.

        Args:
            prefix: Path prefix to filter by (e.g., "story-content/abc123/")
            limit: Maximum number of files to return

        Returns:
            List of file metadata dictionaries
        """
        try:
            files = self.client.storage.from_(self.bucket).list(path=prefix)
            return files[:limit]
        except Exception as e:
            print(f"❌ Failed to list files with prefix {prefix}: {e}")
            raise

    def get_public_url(self, path: str) -> str:
        """
        Get public URL for a file (if bucket is public).

        Args:
            path: Storage path

        Returns:
            Public URL string
        """
        return self.client.storage.from_(self.bucket).get_public_url(path)

    def health_check(self) -> bool:
        """
        Check if Supabase Storage is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to list files as a health check
            self.client.storage.from_(self.bucket).list(path="")
            return True
        except Exception as e:
            print(f"❌ Supabase Storage health check failed: {e}")
            return False

