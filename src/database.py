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
                    content_path TEXT,
                    metadata_path TEXT,
                    original_email_path TEXT,
                    chunk_manifest_path TEXT,
                    extraction_method TEXT
                )
            """)

            # Check if story_chunks table needs migration
            cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='story_chunks'")
            existing_schema = cursor.fetchone()

            if existing_schema and 'chunk_text' not in existing_schema[0]:
                # Old schema exists, need to migrate
                print("Migrating story_chunks table to new schema...")
                conn.execute("ALTER TABLE story_chunks RENAME TO story_chunks_old")

                conn.execute("""
                    CREATE TABLE story_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        story_id INTEGER NOT NULL,
                        chunk_number INTEGER NOT NULL,
                        total_chunks INTEGER NOT NULL,
                        word_count INTEGER,
                        chunk_text TEXT NOT NULL DEFAULT '',
                        epub_path TEXT,
                        sent_to_kindle_at TIMESTAMP,
                        FOREIGN KEY (story_id) REFERENCES stories(id),
                        UNIQUE(story_id, chunk_number)
                    )
                """)

                # Copy data from old table (chunk_text will be empty for old records)
                conn.execute("""
                    INSERT INTO story_chunks (id, story_id, chunk_number, total_chunks, word_count, epub_path, sent_to_kindle_at)
                    SELECT id, story_id, chunk_number, 1, word_count, epub_path, sent_to_kindle_at
                    FROM story_chunks_old
                """)

                conn.execute("DROP TABLE story_chunks_old")
                print("Migration complete")
            else:
                # Create table with new schema
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS story_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        story_id INTEGER NOT NULL,
                        chunk_number INTEGER NOT NULL,
                        total_chunks INTEGER NOT NULL,
                        word_count INTEGER,
                        chunk_text TEXT NOT NULL DEFAULT '',
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

            # Webhook logs table for debugging
            conn.execute("""
                CREATE TABLE IF NOT EXISTS webhook_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at TIMESTAMP NOT NULL,
                    raw_payload TEXT NOT NULL,
                    parsed_emails_count INTEGER,
                    processing_status TEXT,
                    error_message TEXT,
                    story_ids TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_webhook_logs_received_at
                ON webhook_logs(received_at DESC)
            """)

    def create_story(self, email_id: str, title: Optional[str] = None,
                    author: Optional[str] = None,
                    content_path: Optional[str] = None,
                    metadata_path: Optional[str] = None,
                    original_email_path: Optional[str] = None,
                    extraction_method: Optional[str] = None) -> int:
        """Create a new story record with file paths."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO stories (email_id, title, author, received_at, content_path, metadata_path, original_email_path, extraction_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (email_id, title, author, datetime.utcnow(), content_path, metadata_path, original_email_path, extraction_method))
            return cursor.lastrowid

    def update_story_paths(self, story_id: int, content_path: Optional[str] = None,
                          metadata_path: Optional[str] = None, chunk_manifest_path: Optional[str] = None):
        """Update file paths for a story."""
        with self.get_connection() as conn:
            updates = []
            values = []
            if content_path:
                updates.append("content_path = ?")
                values.append(content_path)
            if metadata_path:
                updates.append("metadata_path = ?")
                values.append(metadata_path)
            if chunk_manifest_path:
                updates.append("chunk_manifest_path = ?")
                values.append(chunk_manifest_path)

            if updates:
                values.append(story_id)
                conn.execute(f"""
                    UPDATE stories
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, tuple(values))

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

    def update_story_metadata(self, story_id: int, title: Optional[str] = None,
                              author: Optional[str] = None, extraction_method: Optional[str] = None):
        """Update story title, author, and extraction method."""
        with self.get_connection() as conn:
            updates = []
            values = []
            if title:
                updates.append("title = ?")
                values.append(title)
            if author:
                updates.append("author = ?")
                values.append(author)
            if extraction_method:
                updates.append("extraction_method = ?")
                values.append(extraction_method)

            if updates:
                values.append(story_id)
                conn.execute(f"""
                    UPDATE stories
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, tuple(values))

    def create_chunk(self, story_id: int, chunk_number: int, total_chunks: int,
                    chunk_text: str, word_count: int, epub_path: Optional[str] = None) -> int:
        """Create a story chunk record."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO story_chunks (story_id, chunk_number, total_chunks, chunk_text, word_count, epub_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (story_id, chunk_number, total_chunks, chunk_text, word_count, epub_path))
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

    def get_next_unsent_chunk(self) -> Optional[Dict[str, Any]]:
        """Get the next chunk that hasn't been sent to Kindle yet."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT sc.*, s.title, s.author
                FROM story_chunks sc
                JOIN stories s ON sc.story_id = s.id
                WHERE sc.sent_to_kindle_at IS NULL
                AND s.status = ?
                ORDER BY s.received_at ASC, sc.chunk_number ASC
                LIMIT 1
            """, (StoryStatus.CHUNKED.value,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_story_by_id(self, story_id: int) -> Optional[Dict[str, Any]]:
        """Get a story by its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM stories WHERE id = ?
            """, (story_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_stories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all stories, most recent first."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM stories
                ORDER BY received_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_chunk_by_id(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific chunk by its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT sc.*, s.title, s.author
                FROM story_chunks sc
                JOIN stories s ON sc.story_id = s.id
                WHERE sc.id = ?
            """, (chunk_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_story(self, story_id: int) -> bool:
        """Delete a story and all its chunks."""
        with self.get_connection() as conn:
            # Check if story exists
            cursor = conn.execute("SELECT id FROM stories WHERE id = ?", (story_id,))
            if not cursor.fetchone():
                return False

            # Delete chunks first (foreign key constraint)
            conn.execute("DELETE FROM story_chunks WHERE story_id = ?", (story_id,))

            # Delete story
            conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))

            return True

    def delete_all_stories(self):
        """Delete all stories and chunks. USE WITH CAUTION!"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM story_chunks")
            conn.execute("DELETE FROM stories")

    def reset_chunk_status(self, chunk_id: int) -> bool:
        """Mark a chunk as unsent (for re-testing)."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE story_chunks
                SET sent_to_kindle_at = NULL
                WHERE id = ?
            """, (chunk_id,))
            return cursor.rowcount > 0

    # Webhook logging methods
    def log_webhook(self, raw_payload: str, parsed_emails_count: int = 0,
                   processing_status: str = "received", error_message: Optional[str] = None,
                   story_ids: Optional[List[int]] = None) -> int:
        """Log a webhook payload for debugging."""
        with self.get_connection() as conn:
            story_ids_str = ",".join(map(str, story_ids)) if story_ids else None
            cursor = conn.execute("""
                INSERT INTO webhook_logs (received_at, raw_payload, parsed_emails_count, processing_status, error_message, story_ids)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow(), raw_payload, parsed_emails_count, processing_status, error_message, story_ids_str))
            return cursor.lastrowid

    def get_webhook_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent webhook logs."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM webhook_logs
                ORDER BY received_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_webhook_log_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific webhook log by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM webhook_logs WHERE id = ?
            """, (log_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
