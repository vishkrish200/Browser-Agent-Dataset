import re
import logging
from typing import List, Dict, Optional, Union, Any

# Attempt to import BeautifulSoup, but make it optional so module can load if not installed.
BS4_AVAILABLE = False
try:
    from bs4 import BeautifulSoup, NavigableString, Comment, Doctype, Tag
    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None
    NavigableString = None
    Comment = None
    Doctype = None
    Tag = None
    # Users will get an error only if they try to use HTML scrubbing without bs4 installed.

from . import config as pii_config
from .exceptions import PIIScrubbingError, RegexCompilationError, HTMLParsingError

logger = logging.getLogger(__name__)
DEFAULT_LOG_EXTRA_PII = {"action": "pii_scrubbing"}

class PIIScrubber:
    """
    A component to identify and remove/replace Personally Identifiable Information (PII)
    from text, HTML content, and structured action data.
    """

    def __init__(self, mode: str = "strict", custom_sensitive_patterns: Optional[Dict[str, List[str]]] = None):
        """
        Initializes the PIIScrubber.

        Args:
            mode (str): Scrubbing mode, e.g., "strict". 
                        (Currently, "strict" is the main implemented mode, 
                        "permissive" could be added later to use fewer/lighter regexes).
            custom_sensitive_patterns (Optional[Dict[str, List[str]]]): 
                A dictionary to add or override regex patterns for custom PII detection.
                Keys are categories (e.g., 'session_tokens', 'user_ids'), values are lists of regex strings.
                These are merged with pii_config.DEFAULT_SENSITIVE_PATTERNS.
        """
        self.mode = mode
        self.scrub_counts: Dict[str, int] = {}
        self.sensitive_regexes: Dict[str, List[re.Pattern]] = {} # Initialize before _reset_counts
        self._reset_counts() # Now it's safe to call

        # Compile regex patterns
        self.email_regex = self._compile_regex(pii_config.EMAIL_REGEX, "email_regex")
        self.phone_regexes = [
            self._compile_regex(pattern, f"phone_pattern_{i}") 
            for i, pattern in enumerate(pii_config.PHONE_REGEX_PATTERNS)
        ]

        # Handle custom/default sensitive patterns (populates the already initialized self.sensitive_regexes)
        effective_sensitive_patterns = {**pii_config.DEFAULT_SENSITIVE_PATTERNS, **(custom_sensitive_patterns or {})}
        
        for category, patterns in effective_sensitive_patterns.items():
            if isinstance(patterns, list):
                compiled_list = []
                for i, p_str in enumerate(patterns):
                    if isinstance(p_str, str):
                        compiled_list.append(self._compile_regex(p_str, f"{category}_pattern_{i}"))
                    else:
                        logger.warning(f"Pattern for category '{category}' at index {i} is not a string, skipping.", extra=DEFAULT_LOG_EXTRA_PII)
                if compiled_list:
                    self.sensitive_regexes[category] = compiled_list # Assign to existing dict
            else:
                logger.warning(f"Patterns for category '{category}' is not a list, skipping.", extra=DEFAULT_LOG_EXTRA_PII)
        
        log_init_extra = {**DEFAULT_LOG_EXTRA_PII, "sub_action": "__init__"}
        logger.info(f"PIIScrubber initialized. Mode: {self.mode}. Custom patterns provided: {custom_sensitive_patterns is not None}", extra=log_init_extra)

    def _compile_regex(self, pattern: str, pattern_name: str) -> re.Pattern:
        try:
            return re.compile(pattern)
        except re.error as e:
            msg = f"Failed to compile regex pattern '{pattern_name}': {pattern}. Error: {e}"
            logger.error(msg, extra={**DEFAULT_LOG_EXTRA_PII, "pattern_name": pattern_name, "pattern": pattern})
            raise RegexCompilationError(msg) from e

    def _reset_counts(self):
        """Resets scrub counts for a new cleaning operation or initialization."""
        self.scrub_counts = {"emails": 0, "phones": 0, "html_text_nodes": 0, "html_attributes": 0}
        # Add keys for all sensitive pattern categories dynamically
        for category in self.sensitive_regexes.keys():
            self.scrub_counts[category] = 0
        if not self.sensitive_regexes and pii_config.DEFAULT_SENSITIVE_PATTERNS:
             for category in pii_config.DEFAULT_SENSITIVE_PATTERNS.keys():
                 self.scrub_counts.setdefault(category,0) # Ensure keys exist even if patterns empty
        self.scrub_counts.setdefault("custom_other", 0) # Fallback for patterns not fitting known categories

    def _scrub_text_with_regex_list(self, text: str, regex_list: List[re.Pattern], replacement: str, count_key: str) -> str:
        """Applies a list of compiled regexes to scrub text and updates a single count key."""
        if not text or not regex_list: return text
        scrubbed_text = text
        for regex_pattern in regex_list:
            prev_len = len(scrubbed_text)
            scrubbed_text, num_subs = regex_pattern.subn(replacement, scrubbed_text)
            if num_subs > 0:
                self.scrub_counts[count_key] += num_subs
        return scrubbed_text

    def scrub_text(self, text: str, reset_counts_before_scrub: bool = False) -> str:
        """
        Applies all configured PII scrubbers to a piece of text.
        This is the main text scrubbing routine.

        Args:
            text (str): The input text to scrub.
            reset_counts_before_scrub (bool): If True, resets internal scrub counters before this operation.
                                            Set to False if part of a larger operation like clean_html.

        Returns:
            str: The scrubbed text.
        """
        if not text or not isinstance(text, str):
            return text 
        
        if reset_counts_before_scrub:
            self._reset_counts()

        scrubbed_text = text
        scrubbed_text = self._scrub_text_with_regex_list(scrubbed_text, [self.email_regex], pii_config.REDACTED_EMAIL, "emails")
        scrubbed_text = self._scrub_text_with_regex_list(scrubbed_text, self.phone_regexes, pii_config.REDACTED_PHONE, "phones")
        
        for category, regex_patterns in self.sensitive_regexes.items():
            # Determine replacement: could be category-specific or generic
            replacement = pii_config.REDACTED_TOKEN # Default for sensitive patterns
            if category == "passwords": replacement = "[REDACTED_PASSWORD]" # Example specific
            scrubbed_text = self._scrub_text_with_regex_list(scrubbed_text, regex_patterns, replacement, category)
        
        # NER for names/addresses would be a separate, more complex step here if implemented.
        # Example: if self.mode == "strict" and self.ner_model_available:
        #    scrubbed_text = self._scrub_with_ner(scrubbed_text)
        return scrubbed_text

    def clean_html(self, html_content: str) -> str:
        """
        Scrubs PII from text nodes and relevant attributes within HTML content, 
        aiming to preserve DOM structure.
        Resets scrub counts internally before processing.

        Args:
            html_content (str): The HTML content string to scrub.

        Returns:
            str: The scrubbed HTML content string.

        Raises:
            HTMLParsingError: If BeautifulSoup fails to parse the HTML.
            PIIScrubbingError: If BS4 is not available.
        """
        self._reset_counts()
        if not BS4_AVAILABLE:
            msg = "BeautifulSoup4 not installed. HTML scrubbing is disabled. Install with `pip install beautifulsoup4`."
            logger.error(msg, extra=DEFAULT_LOG_EXTRA_PII)
            raise PIIScrubbingError(msg) # Raise an error instead of returning original
        
        if not html_content or not isinstance(html_content, str):
            return html_content

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as e: 
            logger.error(f"Failed to parse HTML for PII scrubbing: {e}", extra=DEFAULT_LOG_EXTRA_PII)
            raise HTMLParsingError(f"Failed to parse HTML: {e}") from e

        # 1. Scrub all text nodes (NavigableString)
        for text_node in soup.find_all(string=True):
            if text_node.parent and text_node.parent.name in ['script', 'style', 'template']:
                continue 
            if isinstance(text_node, (Comment, Doctype)):
                continue
            
            original_text = str(text_node)
            scrubbed_text = self.scrub_text(original_text, reset_counts_before_scrub=False) # Use existing counts
            if scrubbed_text != original_text:
                text_node.replace_with(scrubbed_text)
                self.scrub_counts["html_text_nodes"] += 1 # Could count specific PII types if scrub_text returned them

        # 2. Scrub 'value' attributes of specified input/textarea tags
        for tag_name_to_scrub, input_types_to_scrub in pii_config.INPUT_VALUE_SCRUB_TAGS.items():
            elements_to_check = soup.find_all(tag_name_to_scrub)
            for element in elements_to_check:
                if not isinstance(element, Tag): continue # Should not happen with find_all(tag_name)

                if tag_name_to_scrub == 'input':
                    current_type = element.get('type', 'text').lower()
                    if current_type in input_types_to_scrub and element.has_attr('value'):
                        original_value = element['value']
                        if isinstance(original_value, str): # Attribute values can be lists
                            scrubbed_value = self.scrub_text(original_value, reset_counts_before_scrub=False)
                            if scrubbed_value != original_value:
                                element['value'] = scrubbed_value
                                self.scrub_counts["html_attributes"] +=1 
                elif tag_name_to_scrub == 'textarea':
                    # Textarea content is handled by NavigableString iteration above.
                    # If it had a 'value' attribute that might contain PII and differs from content,
                    # it could be handled here, but typically textareas use their content.
                    pass 
        
        # 3. (Future) Scrub other attributes like href, src based on pii_config.ATTRIBUTE_VALUE_SCRUB_PATTERNS

        final_html = str(soup)
        total_scrubbed = sum(v for k, v in self.scrub_counts.items() if k not in ["html_text_nodes", "html_attributes"])
        logger.info(
            f"HTML scrubbing complete. Text nodes modified: {self.scrub_counts['html_text_nodes']}. "
            f"Attributes modified: {self.scrub_counts['html_attributes']}. Total PII instances: {total_scrubbed}", 
            extra=DEFAULT_LOG_EXTRA_PII
        )
        return final_html

    def clean_action_data(self, action_data: Union[Dict[str, Any], List[Any], Any], reset_counts_before_scrub: bool = True) -> Union[Dict[str, Any], List[Any], Any]:
        """
        Recursively scrubs string values within a structured action data (dict or list).
        
        Args:
            action_data: The data to scrub (can be nested dict/list).
            reset_counts_before_scrub: If True, resets internal scrub counters. 
                                       Set to False if part of a larger operation.
        Returns:
            The scrubbed data structure.
        """
        if reset_counts_before_scrub:
            self._reset_counts()
        
        if isinstance(action_data, dict):
            return {key: self.clean_action_data(value, reset_counts_before_scrub=False) for key, value in action_data.items()}
        elif isinstance(action_data, list):
            return [self.clean_action_data(item, reset_counts_before_scrub=False) for item in action_data]
        elif isinstance(action_data, str):
            return self.scrub_text(action_data, reset_counts_before_scrub=False) # Counts aggregated by scrub_text
        else:
            return action_data 

    def get_scrub_counts(self) -> Dict[str, int]:
        """Returns the counts of PII found and scrubbed since the last reset or PIIScrubber initialization."""
        return dict(self.scrub_counts) # Return a copy 