from bs4 import BeautifulSoup
from typing import Optional, Dict, Any
import re
import requests
from abc import ABC, abstractmethod


class EmailParsingStrategy(ABC):
    """Abstract base class for email parsing strategies."""

    @abstractmethod
    def can_handle(self, email_data: Dict[str, Any]) -> bool:
        """Check if this strategy can handle the email."""
        pass

    @abstractmethod
    def extract_story(self, email_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Extract story content from email.

        Returns:
            Dict with keys: 'text', 'title', 'author' or None if extraction fails
        """
        pass


class InlineTextStrategy(EmailParsingStrategy):
    """Extract story text directly from email body."""

    def can_handle(self, email_data: Dict[str, Any]) -> bool:
        """Check if email contains substantial text content."""
        html_content = email_data.get("html", "")
        text_content = email_data.get("text", "")

        # Check if there's meaningful content
        total_length = len(html_content) + len(text_content)
        return total_length > 500  # Arbitrary threshold

    def extract_story(self, email_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Extract story from email body."""
        html_content = email_data.get("html", "")
        text_content = email_data.get("text", "")
        subject = email_data.get("subject", "Unknown Title")
        from_email = email_data.get("from", "")

        # Try to extract author from email
        author = self._extract_author(from_email)

        # Prefer HTML content, parse with BeautifulSoup
        if html_content:
            story_text = self._extract_text_from_html(html_content)
        else:
            story_text = text_content

        if not story_text or len(story_text.strip()) < 100:
            return None

        return {
            "text": story_text.strip(),
            "title": self._clean_subject(subject),
            "author": author,
        }

    def _extract_text_from_html(self, html: str) -> str:
        """Extract clean text from HTML content."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text

    def _extract_author(self, from_email: str) -> str:
        """Extract author name from email address."""
        # Try to extract name from "Name <email@domain.com>" format
        match = re.match(r'^([^<]+)<', from_email)
        if match:
            return match.group(1).strip()

        # Otherwise use email username
        match = re.match(r'^([^@]+)@', from_email)
        if match:
            return match.group(1).strip()

        return "Unknown Author"

    def _clean_subject(self, subject: str) -> str:
        """Clean up email subject line."""
        # Remove common email prefixes
        subject = re.sub(r'^(Re:|Fwd:|Fw:)\s*', '', subject, flags=re.IGNORECASE)
        return subject.strip()


class PasswordProtectedURLStrategy(EmailParsingStrategy):
    """Extract story from password-protected URL."""

    def can_handle(self, email_data: Dict[str, Any]) -> bool:
        """Check if email contains a URL."""
        text = email_data.get("text", "") + email_data.get("html", "")
        return bool(re.search(r'https?://\S+', text))

    def extract_story(self, email_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Extract story from URL in email."""
        html_content = email_data.get("html", "")
        text_content = email_data.get("text", "")
        subject = email_data.get("subject", "Unknown Title")
        from_email = email_data.get("from", "")

        # Extract URL
        url = self._extract_url(text_content + html_content)
        if not url:
            return None

        # Extract password if present
        password = self._extract_password(text_content + html_content)

        # Fetch content from URL
        story_text = self._fetch_url_content(url, password)
        if not story_text:
            return None

        author = InlineTextStrategy()._extract_author(from_email)

        return {
            "text": story_text.strip(),
            "title": InlineTextStrategy()._clean_subject(subject),
            "author": author,
        }

    def _extract_url(self, text: str) -> Optional[str]:
        """Extract URL from text."""
        match = re.search(r'https?://[^\s<>"]+', text)
        return match.group(0) if match else None

    def _extract_password(self, text: str) -> Optional[str]:
        """Extract password from text."""
        # Look for common password patterns
        patterns = [
            r'password[:\s]+(\S+)',
            r'pass[:\s]+(\S+)',
            r'code[:\s]+(\S+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _fetch_url_content(self, url: str, password: Optional[str] = None) -> Optional[str]:
        """Fetch content from URL, handling WordPress password-protected posts."""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })

            # First, try to GET the page
            response = session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Check if password is required
            password_form = soup.find("form", class_="post-password-form")

            if password_form and password:
                print(f"Password-protected post detected, submitting password...")

                # WordPress password-protected posts use 'post_password' field
                form_data = {
                    'post_password': password,
                    'Submit': 'Enter'
                }

                # POST to the same URL with password
                response = session.post(url, data=form_data, timeout=30)
                response.raise_for_status()

                # Re-parse with authenticated session
                soup = BeautifulSoup(response.content, "html.parser")
                print(f"Password submitted successfully")

            # Extract the main content area
            content_html = self._extract_post_content(soup)

            if not content_html:
                print("Warning: Could not find post content, returning full body")
                # Fallback to body content
                content_html = soup.find("body")

            if not content_html:
                return None

            # Return HTML with styling preserved
            return str(content_html)

        except Exception as e:
            print(f"Failed to fetch URL {url}: {e}")
            return None

    def _extract_post_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Extract the main post content area from HTML."""
        # Common WordPress/blog post content selectors (in order of preference)
        selectors = [
            "article .entry-content",
            ".entry-content",
            ".post-content",
            ".article-content",
            "article .content",
            ".chapter-content",
            "article",
            "main",
        ]

        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                print(f"Found content using selector: {selector}")

                # Remove unwanted elements
                for unwanted in content.select("script, style, nav, .sharedaddy, .jp-relatedposts, .comments, footer"):
                    unwanted.decompose()

                # Check if content has substantial text
                text_content = content.get_text(strip=True)
                if len(text_content) > 500:  # At least 500 characters
                    return content

        return None


class EmailParser:
    """Main email parser that tries multiple strategies."""

    def __init__(self):
        # Try URL strategy first - if there's a URL, prefer fetching it over inline content
        self.strategies = [
            PasswordProtectedURLStrategy(),
            InlineTextStrategy(),
        ]

    def parse_email(self, email_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Parse email and extract story content.

        Args:
            email_data: Dict with keys like 'html', 'text', 'subject', 'from'

        Returns:
            Dict with 'text', 'title', 'author' or None if parsing fails
        """
        for strategy in self.strategies:
            if strategy.can_handle(email_data):
                result = strategy.extract_story(email_data)
                if result:
                    return result

        return None

    def add_strategy(self, strategy: EmailParsingStrategy):
        """Add a custom parsing strategy."""
        self.strategies.append(strategy)
