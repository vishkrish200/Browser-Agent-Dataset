# src/pii_scrubber/config.py

# Default replacement strings
REDACTED_EMAIL = "[REDACTED_EMAIL]"
REDACTED_PHONE = "[REDACTED_PHONE]"
REDACTED_GENERIC_PII = "[REDACTED_PII]"
REDACTED_TOKEN = "[REDACTED_TOKEN]"

# Regex patterns (examples, to be refined)
# Simple email regex - for more robust, consider libraries or more complex patterns
EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

# Basic North American phone numbers, can be expanded for international
PHONE_REGEX_PATTERNS = [
    r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", # xxx-xxx-xxxx, xxx.xxx.xxxx, xxx xxx xxxx
    r"\(\d{3}\)\s?\d{3}[-.]?\d{4}",      # (xxx) xxx-xxxx
    r"\b\d{10}\b" # xxxxxxxxxx
]

# Example patterns for session tokens or sensitive query parameters (to be customized)
# These are highly dependent on the specific application and tokens used.
# Users of this library would likely need to provide their own sensitive patterns.
DEFAULT_SENSITIVE_PATTERNS = {
    "session_tokens": [
        # r"session_id=[a-zA-Z0-9\-_]{20,}", # Example for a query param
        # r'"sessionToken"\s*:\s*"[a-zA-Z0-9\-_.]+"' # Example for a JSON value
    ],
    "auth_tokens": [
        # r"Bearer\s+[a-zA-Z0-9\-_.]+",
        # r"api_key=[a-zA-Z0-9\-]{30,}"
    ],
    "generic_secrets": [
        # r"password=\S+", 
        # r"secret=\S+"
    ]
}

# Configuration for HTML scrubbing
# Tags whose text content should generally be scrubbed
TEXT_CONTENT_SCRUB_TAGS = ['p', 'span', 'div', 'a', 'li', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'label', 'button', 'option', 'title', 'figcaption', 'article']
# Input tags whose 'value' attribute should be scrubbed
INPUT_VALUE_SCRUB_TAGS = {
    'input': ['text', 'email', 'password', 'tel', 'search', 'url'], # Scrub 'value' for these input types
    'textarea': [] # Always scrub 'value' (text content) of textarea
}
# Attributes that might contain PII URLs or sensitive data
ATTRIBUTE_VALUE_SCRUB_PATTERNS = {
    # "href": [r"user_id=\d+", r"session_token=\w+"], # Example: scrub hrefs with user_id
    # "src": [r"profile_pic\/"] 
} 