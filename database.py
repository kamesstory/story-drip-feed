import sqlite3
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from enum import Enum


class StoryStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CHUNKED = "chunked"
    SENT = "sent"
    FAILED = "failed"


class Database:
    def __init__(self, db_path: str = "stories.db"):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id TEXT UNIQUE NOT NULL,
                    title TEXT,
                    author TEXT,
                    received_at TIMESTAMP NOT NULL,
                    word_count INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    processed_at TIMESTAMP,
                    sent_at TIMESTAMP,
                    raw_content TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS story_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id INTEGER NOT NULL,
                    chunk_number INTEGER NOT NULL,
                    word_count INTEGER,
                    epub_path TEXT,
                    sent_to_kindle_at TIMESTAMP,
                    FOREIGN KEY (story_id) REFERENCES stories(id),
                    UNIQUE(story_id, chunk_number)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stories_status
                ON stories(status)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stories_email_id
                ON stories(email_id)
            """)

    def create_story(self, email_id: str, title: Optional[str] = None,
                    author: Optional[str] = None, raw_content: Optional[str] = None) -> int:
        """Create a new story record."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO stories (email_id, title, author, received_at, raw_content)
                VALUES (?, ?, ?, ?, ?)
            """, (email_id, title, author, datetime.utcnow(), raw_content))
            return cursor.lastrowid

    def update_story_status(self, story_id: int, status: StoryStatus,
                           error_message: Optional[str] = None):
        """Update story status."""
        with self.get_connection() as conn:
            timestamp_field = None
            if status == StoryStatus.CHUNKED:
                timestamp_field = "processed_at"
            elif status == StoryStatus.SENT:
                timestamp_field = "sent_at"

            if timestamp_field:
                conn.execute(f"""
                    UPDATE stories
                    SET status = ?, error_message = ?, {timestamp_field} = ?
                    WHERE id = ?
                """, (status.value, error_message, datetime.utcnow(), story_id))
            else:
                conn.execute("""
                    UPDATE stories
                    SET status = ?, error_message = ?
                    WHERE id = ?
                """, (status.value, error_message, story_id))

    def increment_retry_count(self, story_id: int):
        """Increment retry count for a failed story."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE stories
                SET retry_count = retry_count + 1
                WHERE id = ?
            """, (story_id,))

    def update_word_count(self, story_id: int, word_count: int):
        """Update word count for a story."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE stories
                SET word_count = ?
                WHERE id = ?
            """, (word_count, story_id))

    def create_chunk(self, story_id: int, chunk_number: int,
                    word_count: int, epub_path: Optional[str] = None) -> int:
        """Create a story chunk record."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO story_chunks (story_id, chunk_number, word_count, epub_path)
                VALUES (?, ?, ?, ?)
            """, (story_id, chunk_number, word_count, epub_path))
            return cursor.lastrowid

    def mark_chunk_sent(self, chunk_id: int):
        """Mark a chunk as sent to Kindle."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE story_chunks
                SET sent_to_kindle_at = ?
                WHERE id = ?
            """, (datetime.utcnow(), chunk_id))

    def get_story_by_email_id(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get story by email ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM stories WHERE email_id = ?
            """, (email_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_story_chunks(self, story_id: int) -> List[Dict[str, Any]]:
        """Get all chunks for a story."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM story_chunks
                WHERE story_id = ?
                ORDER BY chunk_number
            """, (story_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_failed_stories(self, max_retries: int = 3) -> List[Dict[str, Any]]:
        """Get failed stories that haven't exceeded max retries."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM stories
                WHERE status = ? AND retry_count < ?
                ORDER BY received_at DESC
            """, (StoryStatus.FAILED.value, max_retries))
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_stories(self) -> List[Dict[str, Any]]:
        """Get all pending stories."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM stories
                WHERE status = ?
                ORDER BY received_at ASC
            """, (StoryStatus.PENDING.value,))
            return [dict(row) for row in cursor.fetchall()]
