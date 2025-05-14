import pytest
import re
from src.pii_scrubber import PIIScrubber
from src.pii_scrubber import config as pii_config # To access REDACTED strings
from src.pii_scrubber.exceptions import RegexCompilationError, PIIScrubbingError, HTMLParsingError # Assuming these are defined
from src.pii_scrubber.scrubber import BS4_AVAILABLE # Import the module-level constant
from unittest import mock # For patching BS4_AVAILABLE

# Placeholder for PII Scrubber tests.
# These will be added in a subsequent step based on the implementation of PIIScrubber.

# Example test structure:
# def test_scrub_email_simple():
#     scrubber = PIIScrubber()
#     assert scrubber.scrub_text("Contact me at test@example.com") == "Contact me at [REDACTED_EMAIL]"

# def test_clean_html_basic():
#     if not PIIScrubber.BS4_AVAILABLE: # Check if bs4 is installed if tests depend on it
#         pytest.skip("BeautifulSoup4 not available, skipping HTML scrubbing test")
#     scrubber = PIIScrubber()
#     html = "<p>My email is user@domain.com</p><div>Call 123-456-7890</div>"
#     expected = "<p>My email is [REDACTED_EMAIL]</p><div>Call [REDACTED_PHONE]</div>"
#     assert scrubber.clean_html(html) == expected 

# --- Initialization Tests ---
def test_pii_scrubber_initialization():
    scrubber = PIIScrubber()
    assert scrubber.mode == "strict"
    assert hasattr(scrubber, "email_regex")
    assert isinstance(scrubber.email_regex, re.Pattern)
    assert len(scrubber.phone_regexes) > 0
    assert all(isinstance(p, re.Pattern) for p in scrubber.phone_regexes)
    
    initial_counts = scrubber.get_scrub_counts()
    assert initial_counts.get("emails", 0) == 0
    assert initial_counts.get("phones", 0) == 0
    assert initial_counts.get("html_text_nodes", 0) == 0
    assert initial_counts.get("html_attributes", 0) == 0
    # Check if default sensitive patterns categories are in counts
    for cat in pii_config.DEFAULT_SENSITIVE_PATTERNS.keys():
        assert cat in initial_counts, f"Category {cat} missing from initial counts"
        assert initial_counts[cat] == 0

def test_pii_scrubber_custom_patterns():
    custom_patterns_config = {
        "user_ids": [r"user_id_\d+"], 
        "custom_tokens": [r"tok_[A-Z]+"],
        "empty_category_patterns": [] # Test category with no actual patterns
    }
    scrubber = PIIScrubber(custom_sensitive_patterns=custom_patterns_config)
    assert "user_ids" in scrubber.sensitive_regexes
    assert len(scrubber.sensitive_regexes["user_ids"]) == 1
    assert "custom_tokens" in scrubber.sensitive_regexes
    assert "empty_category_patterns" not in scrubber.sensitive_regexes # Should not add if patterns list is empty
    
    scrubber._reset_counts() # Reset before specific scrub test
    result_text = scrubber.scrub_text("data for user_id_123 and tok_ABC")
    # Assuming default replacement for custom patterns is REDACTED_TOKEN
    assert result_text == f"data for {pii_config.REDACTED_TOKEN} and {pii_config.REDACTED_TOKEN}"
    counts = scrubber.get_scrub_counts()
    assert counts.get("user_ids", 0) == 1
    assert counts.get("custom_tokens", 0) == 1

def test_pii_scrubber_bad_regex_compile():
    with pytest.raises(RegexCompilationError, match="Failed to compile regex pattern"):
        PIIScrubber(custom_sensitive_patterns={"bad_regex": ["[*"]})

# --- Basic Text Scrubbing Tests ---
def test_scrub_text_email():
    scrubber = PIIScrubber()
    scrubber._reset_counts()
    assert scrubber.scrub_text("Email me at test@example.com please.") == \
           f"Email me at {pii_config.REDACTED_EMAIL} please."
    assert scrubber.get_scrub_counts()["emails"] == 1
    
    scrubber._reset_counts()
    assert scrubber.scrub_text("No email here.") == "No email here."
    assert scrubber.get_scrub_counts()["emails"] == 0

    scrubber._reset_counts()
    assert scrubber.scrub_text("two emails: first@test.com and second@another.org") == \
           f"two emails: {pii_config.REDACTED_EMAIL} and {pii_config.REDACTED_EMAIL}"
    assert scrubber.get_scrub_counts()["emails"] == 2

def test_scrub_text_phone():
    scrubber = PIIScrubber()
    scrubber._reset_counts()
    assert scrubber.scrub_text("Call 123-456-7890 or (098) 765-4321.") == \
           f"Call {pii_config.REDACTED_PHONE} or {pii_config.REDACTED_PHONE}."
    assert scrubber.get_scrub_counts()["phones"] == 2

    scrubber._reset_counts()
    assert scrubber.scrub_text("Number 9876543210 is a phone.") == \
           f"Number {pii_config.REDACTED_PHONE} is a phone."
    assert scrubber.get_scrub_counts()["phones"] == 1

    scrubber._reset_counts()
    assert scrubber.scrub_text("Just numbers 12345.") == "Just numbers 12345."
    assert scrubber.get_scrub_counts()["phones"] == 0

def test_scrub_text_no_pii():
    scrubber = PIIScrubber()
    scrubber._reset_counts()
    text = "This is a perfectly safe sentence."
    assert scrubber.scrub_text(text) == text
    # Sum all counts except for html specific ones for this text-only test
    text_pii_counts = sum(v for k, v in scrubber.get_scrub_counts().items() if k not in ["html_text_nodes", "html_attributes"])
    assert text_pii_counts == 0

def test_scrub_text_multiple_pii_types():
    scrubber = PIIScrubber()
    scrubber._reset_counts()
    text = "Email: user@test.com, Phone: (123)456-7890. No custom tokens here."
    expected = f"Email: {pii_config.REDACTED_EMAIL}, Phone: {pii_config.REDACTED_PHONE}. No custom tokens here."
    assert scrubber.scrub_text(text) == expected
    counts = scrubber.get_scrub_counts()
    assert counts["emails"] == 1
    assert counts["phones"] == 1
    # assert counts.get("some_custom_category", 0) == 0 # if checking custom ones

def test_scrub_text_with_custom_sensitive_patterns():
    custom_patterns_config = {"secret_codes": [r"alpha-\d{4}"]}
    scrubber = PIIScrubber(custom_sensitive_patterns=custom_patterns_config)
    scrubber._reset_counts()
    text = "My code is alpha-1234 and email is beta@gamma.com"
    expected = f"My code is {pii_config.REDACTED_TOKEN} and email is {pii_config.REDACTED_EMAIL}"
    assert scrubber.scrub_text(text) == expected
    counts = scrubber.get_scrub_counts()
    assert counts["secret_codes"] == 1
    assert counts["emails"] == 1

def test_scrub_text_resets_counts_when_flagged():
    scrubber = PIIScrubber()
    scrubber.scrub_text("first@pass.com")
    assert scrubber.get_scrub_counts()["emails"] == 1
    
    scrubber.scrub_text("second@pass.com", reset_counts_before_scrub=True)
    assert scrubber.get_scrub_counts()["emails"] == 1 # Only the second one counted

    scrubber.scrub_text("third@pass.com", reset_counts_before_scrub=False) 
    assert scrubber.get_scrub_counts()["emails"] == 2 # second and third

# --- HTML Scrubbing Tests ---
HTML_TEST_CASES = [
    ("<p>Email: test@example.com</p>", f"<p>Email: {pii_config.REDACTED_EMAIL}</p>", {"emails": 1, "html_text_nodes": 1}),
    ("<div>Call (123) 456-7890 now!</div>", f"<div>Call {pii_config.REDACTED_PHONE} now!</div>", {"phones": 1, "html_text_nodes": 1}),
    ("<p>user@site.com and 123.456.7890</p>", f"<p>{pii_config.REDACTED_EMAIL} and {pii_config.REDACTED_PHONE}</p>", {"emails": 1, "phones": 1, "html_text_nodes": 1}),
    ("<p>No PII here.</p>", "<p>No PII here.</p>", {"html_text_nodes": 0}), # No change
    ("<script>var email = 'danger@x.com';</script><p>safe</p>", "<script>var email = 'danger@x.com';</script><p>safe</p>", {}), # Script ignored, no text nodes modified beyond script
    ("<!-- My mail is hide@me.com --><p>Hello</p>", "<!-- My mail is hide@me.com --><p>Hello</p>", {}), # Comment ignored
    ('<input type="text" value="secret@password.com">', f'<input type="text" value="{pii_config.REDACTED_EMAIL}"/>', {"emails":1, "html_attributes":1}),
    ('<input type="password" value="123-456-7890">', f'<input type="password" value="{pii_config.REDACTED_PHONE}"/>', {"phones":1, "html_attributes":1}),
    ('<input type="number" value="1234567890"> <p>12345</p>', '<input type="number" value="1234567890"/> <p>12345</p>', {}), # Input type 'number' not scrubbed
    ('<textarea name="notes">My number is 098-765-4321</textarea>', f'<textarea name="notes">My number is {pii_config.REDACTED_PHONE}</textarea>', {"phones":1, "html_text_nodes":1}),
    ("<!DOCTYPE html><html><body><p>doc@type.com</p></body></html>", f"<!DOCTYPE html>\n<html><body><p>{pii_config.REDACTED_EMAIL}</p></body></html>", {"emails":1, "html_text_nodes":1})
]

@pytest.mark.parametrize("html_input, html_expected, expected_counts", HTML_TEST_CASES)
def test_clean_html(html_input, html_expected, expected_counts):
    if not BS4_AVAILABLE: # Use the imported constant
        pytest.skip("BeautifulSoup4 not available, skipping HTML scrubbing test")
    scrubber = PIIScrubber()
    assert scrubber.clean_html(html_input) == html_expected
    counts = scrubber.get_scrub_counts()
    for key, val in expected_counts.items():
        assert counts.get(key, 0) == val, f"Count mismatch for {key}. Counts: {counts}"

def test_clean_html_bs4_unavailable():
    with mock.patch('src.pii_scrubber.scrubber.BS4_AVAILABLE', False):
        scrubber = PIIScrubber()
        with pytest.raises(PIIScrubbingError, match="BeautifulSoup4 not installed"):
            scrubber.clean_html("<p>test@example.com</p>")

def test_clean_html_unparseable():
    if not BS4_AVAILABLE: # Use the imported constant
        pytest.skip("BeautifulSoup4 not available")
    scrubber = PIIScrubber()
    # Malformed HTML that BeautifulSoup might struggle with and raise an error, 
    # or try to fix. The goal is to ensure our HTMLParsingError is raised if BS4 itself errors out.
    # This specific malformed HTML might be auto-corrected by bs4; a more complex one might be needed
    # or we mock BeautifulSoup to raise an error on parsing.
    # For now, let's trust that bs4 handles most things or we catch its general Exception.
    with mock.patch('src.pii_scrubber.scrubber.BeautifulSoup') as mock_bs_constructor:
        mock_bs_constructor.side_effect = Exception("BS4 internal parse error")
        with pytest.raises(HTMLParsingError, match="Failed to parse HTML: BS4 internal parse error"):
            scrubber.clean_html("<p><b>test@example.com<i></p</b>") 


# --- Action Data Scrubbing Tests ---
ACTION_DATA_TEST_CASES = [
    ({"type": "type", "value": "send to test@example.com"}, {"type": "type", "value": f"send to {pii_config.REDACTED_EMAIL}"}, {"emails":1}),
    ({"details": ["call 123-456-7890", {"notes": "contact: other@person.net"}]}, 
     {"details": [f"call {pii_config.REDACTED_PHONE}", {"notes": f"contact: {pii_config.REDACTED_EMAIL}"}]}, {"emails":1, "phones":1}),
    (["safe string", {"value": 12345, "email_list": ["a@b.com", "c@d.com"]}], 
     ["safe string", {"value": 12345, "email_list": [f"{pii_config.REDACTED_EMAIL}", f"{pii_config.REDACTED_EMAIL}"]}], 
     {"emails":2}),
    ("A string with an email: user@public.org", f"A string with an email: {pii_config.REDACTED_EMAIL}", {"emails":1}),
    (12345, 12345, {}), # Non-string, non-collection
    ({"url": "http://server.com/path?token=secret_val&user=admin@example.com"}, # Assuming "token=" isn't a default sensitive pattern
     {"url": f"http://server.com/path?token=secret_val&user={pii_config.REDACTED_EMAIL}"}, {"emails":1}),
]

@pytest.mark.parametrize("action_input, action_expected, expected_pii_counts", ACTION_DATA_TEST_CASES)
def test_clean_action_data(action_input, action_expected, expected_pii_counts):
    scrubber = PIIScrubber() # Resets counts on init
    assert scrubber.clean_action_data(action_input) == action_expected
    counts = scrubber.get_scrub_counts()
    for key, val in expected_pii_counts.items():
        assert counts.get(key, 0) == val, f"PII count mismatch for '{key}' in action_data test. Counts: {counts}"
    # Check that other PII types (not in expected_pii_counts for this case) are zero
    all_possible_pii_keys = ["emails", "phones"] + list(pii_config.DEFAULT_SENSITIVE_PATTERNS.keys())
    for k in all_possible_pii_keys:
        if k not in expected_pii_counts:
            assert counts.get(k, 0) == 0, f"Count for '{k}' should be 0 but was {counts.get(k,0)} in action_data test. Counts: {counts}"


# --- Test get_scrub_counts and reset_counts (general) ---
def test_get_and_reset_counts_general():
    scrubber = PIIScrubber()
    initial_counts = scrubber.get_scrub_counts()
    assert all(v == 0 for k, v in initial_counts.items() if k != "custom_other") # custom_other might exist if no custom patterns

    scrubber.scrub_text("test@example.com and 123-456-7890", reset_counts_before_scrub=True) # Resets first
    counts_after_scrub = scrubber.get_scrub_counts()
    assert counts_after_scrub["emails"] == 1
    assert counts_after_scrub["phones"] == 1

    scrubber._reset_counts() # Explicitly reset
    counts_after_reset = scrubber.get_scrub_counts()
    assert all(v == 0 for k,v in counts_after_reset.items() if k != "custom_other") 