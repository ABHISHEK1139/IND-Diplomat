import re
import logging
from typing import List

logger = logging.getLogger(__name__)

class TokenJuice:
    """
    Text compression layer inspired by OpenHuman.
    Reduces token usage by removing HTML, shortening URLs, and stripping boilerplate.
    """
    
    @staticmethod
    def strip_html(text: str) -> str:
        """Removes HTML tags from text."""
        if not text:
            return ""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)
        
    @staticmethod
    def shorten_urls(text: str) -> str:
        """Replaces long URLs with a placeholder."""
        if not text:
            return ""
        # Very basic regex for URLs
        url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        return re.sub(url_pattern, '[URL]', text)
        
    @staticmethod
    def compact_whitespace(text: str) -> str:
        """Removes excessive newlines and spaces."""
        if not text:
            return ""
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()

    @staticmethod
    def deduplicate(lines: List[str]) -> List[str]:
        """Removes exactly duplicate lines while preserving order."""
        seen = set()
        result = []
        for line in lines:
            line_clean = line.strip()
            if line_clean and line_clean not in seen:
                seen.add(line_clean)
                result.append(line)
        return result

    @classmethod
    def compress(cls, text: str, max_length: int = 2000) -> str:
        """
        Runs the full TokenJuice pipeline on a string.
        """
        if not text:
            return ""
            
        text = cls.strip_html(text)
        text = cls.shorten_urls(text)
        text = cls.compact_whitespace(text)
        
        # Split into lines and deduplicate
        lines = text.split('\n')
        lines = cls.deduplicate(lines)
        text = '\n'.join(lines)
        
        # Hard truncate if still too long
        if len(text) > max_length:
            logger.debug("[TokenJuice] Truncating text from %d to %d chars", len(text), max_length)
            text = text[:max_length] + "... [TRUNCATED]"
            
        return text
