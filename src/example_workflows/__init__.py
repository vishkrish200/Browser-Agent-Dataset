# src/example_workflows/__init__.py

# Export example workflow functions/constants

from .video_discovery import get_youtube_video_discovery_workflow
from .general_search import create_general_search_workflow
from .form_submission import create_form_submission_workflow

__all__ = [
    "get_youtube_video_discovery_workflow",
    "create_general_search_workflow",
    "create_form_submission_workflow",
] 