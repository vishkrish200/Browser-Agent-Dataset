import gzip
import logging
from typing import Optional, Dict

# Use minify_html instead of htmlmin
MINIFY_HTML_AVAILABLE = False
try:
    import minify_html 
    MINIFY_HTML_AVAILABLE = True
except ImportError:
    minify_html = None

BS4_AVAILABLE = False
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None # type: ignore

from .exceptions import HTMLProcessingError, MinificationError, DOMDiffError

logger = logging.getLogger(__name__)
DEFAULT_LOG_EXTRA_HTML = {"action": "html_processing"}

class HTMLProcessor:
    """
    Provides utilities for processing HTML content, including minification,
    gzipping, simplified DOM diffing, and length capping.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initializes the HTMLProcessor.

        Args:
            config (Optional[Dict]): Configuration options for the processor.
                                     (e.g., minifier settings, diff thresholds, default max_chars).
        """
        self.config = config or {}
        log_extra = {**DEFAULT_LOG_EXTRA_HTML, "sub_action": "__init__"}
        logger.info(f"HTMLProcessor initialized. minify-html available: {MINIFY_HTML_AVAILABLE}, BeautifulSoup available: {BS4_AVAILABLE}", extra=log_extra)

    def minify(self, html_content: str, 
               minify_js: bool = False,
               minify_css: bool = False, # Library default is False, common to want True for CSS
               keep_comments: bool = False 
               ) -> str:
        """
        Minifies HTML content using the minify-html library.

        Args:
            html_content (str): The HTML string to minify.
            minify_js (bool): Minify JS content. Defaults to False.
            minify_css (bool): Minify CSS content. Defaults to False (our wrapper might default to True later if desired).
            keep_comments (bool): If True, keeps HTML comments. Defaults to False (removes comments).

        Returns:
            str: The minified HTML string.

        Raises:
            MinificationError: If minify-html is not available or fails during minification.
        """
        if not MINIFY_HTML_AVAILABLE or not minify_html: 
            msg = "minify-html library not installed or not imported. HTML minification is disabled. Install with `pip install minify-html`."
            logger.error(msg, extra={**DEFAULT_LOG_EXTRA_HTML, "sub_action": "minify"})
            raise MinificationError(msg)
        if not isinstance(html_content, str):
            raise MinificationError("html_content must be a string for minification.")
        
        try:
            # Call with directly supported keyword arguments for minify_html.minify()
            minified = minify_html.minify(
                html_content, 
                minify_js=minify_js,
                minify_css=minify_css, 
                keep_comments=keep_comments
            )
            return minified
        except Exception as e:
            logger.exception("Error during HTML minification with minify-html.", extra={**DEFAULT_LOG_EXTRA_HTML, "sub_action": "minify"})
            raise MinificationError(f"HTML minification failed with minify-html: {e}") from e

    def gzip_compress(self, text_content: str, compression_level: int = 9) -> bytes:
        """
        Compresses text content (typically HTML) using gzip.
        Args:
            text_content (str): The text string to compress.
            compression_level (int): Gzip compression level (0-9). Defaults to 9 (max compression).
        Returns:
            bytes: The gzipped content.
        Raises:
            HTMLProcessingError: If text_content is not a string or compression fails.
        """
        if not isinstance(text_content, str):
            raise HTMLProcessingError("text_content must be a string for gzip compression.")
        try:
            return gzip.compress(text_content.encode('utf-8'), compresslevel=compression_level)
        except Exception as e:
            logger.exception("Error during gzip compression.", extra={**DEFAULT_LOG_EXTRA_HTML, "sub_action": "gzip_compress"})
            raise HTMLProcessingError(f"Gzip compression failed: {e}") from e

    def is_significant_change(self, html_old: str, html_new: str, text_diff_threshold: float = 0.05) -> bool:
        """
        Simplified DOM diffing based on text content change percentage (MVP).
        Compares the plain text content of two HTML documents.
        Args:
            html_old (str): The old HTML content.
            html_new (str): The new HTML content.
            text_diff_threshold (float): If the percentage change in text length is less than this,
                                       it's considered not significant. Defaults to 0.05 (5%).
        Returns:
            bool: True if the change is considered significant, False otherwise.
        Raises:
            DOMDiffError: If BeautifulSoup is not available or parsing fails.
        """
        if not BS4_AVAILABLE or not BeautifulSoup:
            msg = "BeautifulSoup4 not available. DOM diffing is disabled. Install with `pip install beautifulsoup4`."
            logger.error(msg, extra={**DEFAULT_LOG_EXTRA_HTML, "sub_action": "is_significant_change"})
            raise DOMDiffError(msg)
        if not isinstance(html_old, str) or not isinstance(html_new, str):
            raise DOMDiffError("Both html_old and html_new must be strings for diffing.")

        try:
            soup_old = BeautifulSoup(html_old, 'html.parser')
            soup_new = BeautifulSoup(html_new, 'html.parser')
        except Exception as e:
            logger.error(f"Failed to parse HTML for DOM diffing: {e}", extra={**DEFAULT_LOG_EXTRA_HTML, "sub_action": "is_significant_change"})
            raise DOMDiffError(f"HTML parsing failed for diff: {e}") from e

        text_old = soup_old.get_text(separator=" ", strip=True)
        text_new = soup_new.get_text(separator=" ", strip=True)

        if not text_old and not text_new:
            return False 
        if not text_old or not text_new:
            return True 

        len_old = len(text_old)
        len_new = len(text_new)
        
        if len_old == 0 and len_new == 0: return False # Should be caught by the first check
        if len_old == 0 or len_new == 0: return True # If one is zero and other not, caught by second check
        
        abs_diff = abs(len_new - len_old)
        if float(abs_diff) / max(len_old, len_new) > text_diff_threshold:
            return True
        return False

    def cap_length(self, html_content: str, max_chars: int = 30000) -> str:
        """
        Caps the HTML content to a maximum number of characters (simple truncation for MVP).
        Args:
            html_content (str): The HTML string.
            max_chars (int): The maximum number of characters to allow. Defaults to 30000.
        Returns:
            str: The (potentially) truncated HTML string.
        """
        if not isinstance(html_content, str):
            logger.warning("cap_length received non-string input, returning as is.", extra={**DEFAULT_LOG_EXTRA_HTML, "sub_action": "cap_length"})
            return str(html_content) 
        if not isinstance(max_chars, int) or max_chars < 0:
            logger.warning(f"Invalid max_chars ({max_chars}) for cap_length, using default of 30000.", extra={**DEFAULT_LOG_EXTRA_HTML, "sub_action": "cap_length"})
            max_chars = 30000
        
        if len(html_content) > max_chars:
            logger.info(f"Capping HTML content from {len(html_content)} to {max_chars} characters.", extra={**DEFAULT_LOG_EXTRA_HTML, "sub_action": "cap_length"})
            return html_content[:max_chars]
        return html_content 