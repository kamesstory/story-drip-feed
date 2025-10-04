import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from typing import List, Optional


class KindleSender:
    """Sends EPUB files to Kindle via email."""

    def __init__(
        self,
        kindle_email: str,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        test_mode: bool = False,
    ):
        """
        Initialize Kindle sender.

        Args:
            kindle_email: Your Kindle email address (e.g., username@kindle.com)
            smtp_host: SMTP server hostname (e.g., smtp.gmail.com)
            smtp_port: SMTP server port (e.g., 587 for TLS)
            smtp_user: SMTP username/email
            smtp_password: SMTP password (use app password for Gmail)
            test_mode: If True, only log email details without actually sending
        """
        self.kindle_email = kindle_email
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.test_mode = test_mode

    def send_epub(
        self,
        epub_path: str,
        title: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> bool:
        """
        Send a single EPUB file to Kindle.

        Args:
            epub_path: Path to EPUB file
            title: Book title (for email body)
            subject: Email subject (defaults to filename)

        Returns:
            True if successful, False otherwise
        """
        return self.send_epubs([epub_path], title, subject)

    def send_epubs(
        self,
        epub_paths: List[str],
        title: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> bool:
        """
        Send multiple EPUB files to Kindle in a single email.

        Args:
            epub_paths: List of paths to EPUB files
            title: Book title (for email body)
            subject: Email subject (defaults to "Story Delivery")

        Returns:
            True if successful, False otherwise
        """
        if not epub_paths:
            return False

        # Test mode: just log the email details
        if self.test_mode:
            print("=" * 80)
            print("TEST MODE - Email would be sent with the following details:")
            print("=" * 80)
            print(f"From: {self.smtp_user}")
            print(f"To: {self.kindle_email}")
            print(f"Subject: {subject or 'Story Delivery'}")
            print(f"Title: {title or 'N/A'}")
            print(f"Number of attachments: {len(epub_paths)}")
            print("\nAttachments:")
            for i, epub_path in enumerate(epub_paths, 1):
                if os.path.exists(epub_path):
                    size_bytes = os.path.getsize(epub_path)
                    size_kb = size_bytes / 1024
                    print(f"  {i}. {os.path.basename(epub_path)} ({size_kb:.1f} KB)")
                else:
                    print(f"  {i}. {os.path.basename(epub_path)} (FILE NOT FOUND)")
            print("=" * 80)
            return True

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.smtp_user
            msg["To"] = self.kindle_email
            msg["Subject"] = subject or "Story Delivery"

            # Email body
            body_text = f"Delivering story: {title}\n\n" if title else "Story delivery from nighttime-story-prep"
            body_text += f"Attached files: {len(epub_paths)}"
            msg.attach(MIMEText(body_text, "plain"))

            # Attach EPUB files
            for epub_path in epub_paths:
                if not os.path.exists(epub_path):
                    print(f"Warning: File not found: {epub_path}")
                    continue

                with open(epub_path, "rb") as f:
                    part = MIMEBase("application", "epub+zip")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)

                    filename = os.path.basename(epub_path)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename= {filename}",
                    )
                    msg.attach(part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            print(f"Successfully sent {len(epub_paths)} EPUB(s) to {self.kindle_email}")
            return True

        except Exception as e:
            print(f"Failed to send EPUB to Kindle: {e}")
            return False

    @classmethod
    def from_env(cls) -> "KindleSender":
        """
        Create KindleSender from environment variables.

        Required env vars:
            KINDLE_EMAIL
            SMTP_HOST
            SMTP_PORT
            SMTP_USER
            SMTP_PASSWORD
            TEST_MODE (optional, set to "true" to enable test mode)
        """
        test_mode = os.environ.get("TEST_MODE", "false").lower() == "true"
        return cls(
            kindle_email=os.environ["KINDLE_EMAIL"],
            smtp_host=os.environ["SMTP_HOST"],
            smtp_port=int(os.environ["SMTP_PORT"]),
            smtp_user=os.environ["SMTP_USER"],
            smtp_password=os.environ["SMTP_PASSWORD"],
            test_mode=test_mode,
        )
