# tests/html_processor/test_processor.py

import pytest
import gzip

from src.html_processor import HTMLProcessor
from src.html_processor.exceptions import MinificationError, DOMDiffError, HTMLProcessingError
from src.html_processor.processor import MINIFY_HTML_AVAILABLE, BS4_AVAILABLE # Corrected import
from unittest import mock

@pytest.fixture
def processor() -> HTMLProcessor:
    return HTMLProcessor()

# --- Minify Tests ---
@pytest.mark.skipif(not MINIFY_HTML_AVAILABLE, reason="minify-html library not installed")
def test_minify_behavior_with_minify_html(processor: HTMLProcessor):
    html_in = "<html>  <head> <title>Test</title> </head>  <body> <!-- comment --> <p>Hello</p> </body> </html>"
    html_with_doctype = "<!DOCTYPE html>" + html_in

    # 1. Test with HTMLProcessor.minify() default arguments 
    #    (minify_js=False, minify_css=False, keep_comments=False in our wrapper)
    #    Default minify-html behavior for other Cfg options applies.
    expected_defaults = "<title>Test</title><body><p>Hello" # Adjusted: body tag is kept by minify-html
    assert processor.minify(html_in) == expected_defaults

    # 2. Test with keep_comments=True
    # minify-html default keeps body tag, removes </html> and maybe </head>
    expected_keep_comments = "<title>Test</title><body><!-- comment --><p>Hello" 
    assert processor.minify(html_in, keep_comments=True) == expected_keep_comments

    # 3. Test with CSS and JS minification 
    html_css_js = "<style> p { color: red;\n} </style><script> var a = 1; /* js comment */ </script><p>Text</p>"
    
    # With minify_css=True, keep_comments=False 
    # processor.minify defaults minify_css=False, so we pass True. keep_comments=False is default.
    expected_css_min = "<style>p{color:red}</style><script> var a = 1; /* js comment */ </script><p>Text</p>"
    # Note: minify_html might not remove the trailing </p> unless keep_closing_tags is explicitly False in Cfg,
    # which our simplified wrapper doesn't set. So let's expect it.
    expected_css_min_actual = "<style>p{color:red}</style><script> var a = 1; /* js comment */ </script><p>Text</p>"
    assert processor.minify(html_css_js, minify_css=True) == expected_css_min_actual
    
    # With minify_css=True, minify_js=True, keep_comments=False
    expected_css_js_min = "<style>p{color:red}</style><script>var a=1;</script><p>Text</p>"
    assert processor.minify(html_css_js, minify_css=True, minify_js=True) == expected_css_js_min
    
    # With minify_css=True, minify_js=True, keep_comments=True
    # JS comments are typically removed by JS minifiers (like esbuild used by minify-html) 
    # regardless of the keep_comments HTML setting.
    # HTML comments would be kept though.
    html_css_js_html_comment = "<style>p{color:red}</style><!-- HTML --><script>var a=1;/*JS*/</script><p>Text</p>"
    expected_css_js_min_keep_html_comment = "<style>p{color:red}</style><!-- HTML --><script>var a=1;</script><p>Text</p>"
    assert processor.minify(html_css_js_html_comment, minify_css=True, minify_js=True, keep_comments=True) == expected_css_js_min_keep_html_comment

    # 4. Input with checked attribute - minify-html default normalizes boolean attributes
    html_checked = "<input checked=\"checked\" type='text'>"
    expected_checked_min = "<input checked type=text>"
    assert processor.minify(html_checked) == expected_checked_min

    # 5. HTML with DOCTYPE - minify-html by default preserves DOCTYPE as is
    # With default keep_html_and_head_opening_tags=False and keep_closing_tags=False (library defaults for Cfg)
    expected_with_doctype = "<!DOCTYPE html><title>Test</title><body><p>Hello"
    assert processor.minify(html_with_doctype) == expected_with_doctype

# Test for when the library is unavailable
def test_minify_unavailable_with_minify_html(processor: HTMLProcessor):
    with mock.patch('src.html_processor.processor.MINIFY_HTML_AVAILABLE', False):
        with pytest.raises(MinificationError, match="minify-html library not installed"):
            processor.minify("<html></html>")

# --- Gzip Compression Tests ---
def test_gzip_compress_decompress(processor: HTMLProcessor):
    text = "This is a test string for gzip." * 100
    compressed = processor.gzip_compress(text)
    assert isinstance(compressed, bytes)
    assert len(compressed) < len(text.encode('utf-8'))
    
    decompressed = gzip.decompress(compressed).decode('utf-8')
    assert decompressed == text

def test_gzip_compress_invalid_input(processor: HTMLProcessor):
    with pytest.raises(HTMLProcessingError, match="text_content must be a string"):
        processor.gzip_compress(12345) # type: ignore

# --- Simplified DOM Diffing Tests ---
@pytest.mark.skipif(not BS4_AVAILABLE, reason="BeautifulSoup4 not available")
def test_is_significant_change_text_diff(processor: HTMLProcessor):
    html_old = "<p>Hello world</p>"
    html_new_small_change = "<p>Hello dear world</p>"
    html_new_big_change = "<p>Completely different content here now.</p>"
    html_new_same_text_diff_tags = "<div>Hello world</div>"

    assert processor.is_significant_change(html_old, html_new_big_change) is True
    # 'dear ' is 5 chars. len_old=11, len_new=16. diff=5. max_len=16. 5/16 = 0.31 > 0.05 threshold
    assert processor.is_significant_change(html_old, html_new_small_change, text_diff_threshold=0.05) is True 
    # Text content is the same, so no significant change by this metric
    assert processor.is_significant_change(html_old, html_new_same_text_diff_tags, text_diff_threshold=0.05) is False
    assert processor.is_significant_change(html_old, html_old) is False
    assert processor.is_significant_change("<p></p>", "<p>New text</p>") is True
    assert processor.is_significant_change("<p>Old text</p>", "<p> </p>") is True # Changed to effectively empty
    assert processor.is_significant_change("<p> </p>", "<p>  </p>") is False # Both effectively empty

def test_is_significant_change_bs4_unavailable(processor: HTMLProcessor):
    with mock.patch('src.html_processor.processor.BS4_AVAILABLE', False):
        with pytest.raises(DOMDiffError, match="BeautifulSoup4 not available"):
            processor.is_significant_change("<a></a>", "<b></b>")

# --- Length Capping Tests ---
def test_cap_length(processor: HTMLProcessor):
    html = "This is a test string that is definitely longer than ten characters."
    assert processor.cap_length(html, max_chars=10) == "This is a "
    assert processor.cap_length(html, max_chars=100) == html # No change
    assert processor.cap_length(html, max_chars=0) == ""
    assert processor.cap_length("short", max_chars=10) == "short"

def test_cap_length_invalid_input(processor: HTMLProcessor, caplog):
    assert processor.cap_length(12345, max_chars=10) == "12345" # Converts to str
    assert "cap_length received non-string input" in caplog.text
    caplog.clear()
    processor.cap_length("test", max_chars=-5) # Invalid max_chars
    assert "Invalid max_chars (-5) for cap_length" in caplog.text 