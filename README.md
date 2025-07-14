# Browser-Agent Dataset

A production-ready orchestration platform for capturing real browser interactions and generating high-quality datasets for training web-capable AI agents.

## Overview

The Browser-Agent Dataset project creates comprehensive training datasets by recording AI agents performing real web tasks. It combines cloud browser automation (Browserbase), AI-powered web agents (browser-use + OpenAI), and sophisticated data capture to produce datasets suitable for fine-tuning large language models into effective web agents.

### Key Features

- **Cloud Browser Infrastructure**: Leverages Browserbase for scalable, isolated browser sessions
- **AI-Powered Data Generation**: Uses browser-use library with OpenAI models to perform realistic web tasks
- **Comprehensive Data Capture**: Records screenshots, HTML snapshots, AI reasoning, and actions for each step
- **Production-Ready Storage**: Supports both local and S3 storage with automatic compression and organization
- **Privacy-First**: Built-in PII scrubbing to ensure datasets are safe for training
- **Flexible Workflows**: Support for multiple interaction patterns (search, forms, navigation, etc.)

## How It Works

### 1. Session Orchestration
```
Orchestrator → Browserbase API → Cloud Browser Session
     ↓
AI Agent (browser-use + OpenAI) performs tasks
     ↓
Step-by-step data capture
```

### 2. Data Collection Pipeline
For each AI agent step, the system captures:
- **Visual State**: WebP screenshots of the current page
- **DOM State**: Gzipped HTML content of the page
- **AI Reasoning**: Raw LLM responses and extracted actions
- **Action Details**: Specific interactions (clicks, typing, navigation)
- **Metadata**: Timestamps, URLs, session context

### 3. Dataset Processing
Raw interaction data is processed through:
- **Filtering**: Remove incomplete or low-quality interactions
- **PII Scrubbing**: Sanitize sensitive information
- **Format Conversion**: Transform to JSONL format for training
- **Train/Val Splitting**: Automatic dataset splitting
- **Statistics Generation**: Comprehensive dataset metrics

## Dataset Format

The system generates datasets in JSONL format optimized for LLM training. Each line represents a single interaction step.

### Raw Data Structure

Each step during data collection captures:

```json
{
  "step_id": "uuid-string",
  "session_id": "browserbase_session_xyz", 
  "stagehand_task_id": "optional_task_id",
  "url": "https://example.com/page",
  "ts": "2024-01-01T12:00:00Z",
  "action": {
    "type": "click|type|navigate|scroll",
    "selector": "#button-id",
    "text": "optional_text_input",
    "stagehand_metadata": {}
  },
  "obs_html_gz_path": "s3://bucket/session/step/page.html.gz",
  "screenshot_webp_path": "s3://bucket/session/step/screenshot.webp"
}
```

### Processed Dataset Format

The final training dataset transforms raw steps into structured training examples:

```json
{
  "id": "step_uuid",
  "prompt": "<DOM>...cleaned_html...</DOM><URL>https://example.com</URL><TASK>Click the login button</TASK>",
  "completion": "<ACTION>click #login-btn</ACTION>",
  "metadata": {
    "session_id": "browserbase_session_xyz",
    "timestamp": "2024-01-01T12:00:00Z",
    "url": "https://example.com",
    "action_type": "click"
  }
}
```

### Dataset Statistics

Each dataset includes comprehensive statistics:

```json
{
  "total_steps": 15420,
  "unique_sessions": 1250,
  "action_type_distribution": {
    "click": 8500,
    "type": 3200,
    "navigate": 2100,
    "scroll": 1620
  },
  "domain_distribution": {
    "google.com": 3400,
    "wikipedia.org": 2100,
    "github.com": 1800
  },
  "avg_steps_per_session": 12.3,
  "data_quality_metrics": {
    "complete_sessions": 0.94,
    "successful_actions": 0.89
  }
}
```

## Quick Start

### Prerequisites

- Python 3.10+
- Browserbase API key
- OpenAI API key
- Optional: AWS S3 credentials for cloud storage

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/browser-agent-dataset
cd browser-agent-dataset

# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
uv pip install -e .
```

### Configuration

Initialize your configuration:

```bash
bad-agent configure init
```

This creates a `.env` file. Fill in your API keys:

```env
BROWSERBASE_API_KEY=your_browserbase_key
BROWSERBASE_PROJECT_ID=your_project_id
OPENAI_API_KEY=your_openai_key

# Optional S3 storage
S3_BUCKET_NAME=your_s3_bucket
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
```

### Generate Your First Dataset

```bash
# Run a simple search workflow
uv run python run_example_workflow.py

# Or use the CLI
uv run bad-agent collect run general_search
```

This will:
1. Create a Browserbase session
2. Run an AI agent to perform web searches
3. Capture all interaction data
4. Process and save the dataset

## CLI Usage

The Browser-Agent Dataset project includes a Command Line Interface (CLI) to help manage various aspects of the project, from configuration to data collection.

### Available Commands

The CLI provides commands for configuration and data collection:

```bash
# Initialize configuration
uv run bad-agent configure init

# List available workflows
uv run bad-agent collect list-workflows

# Run a specific workflow
uv run bad-agent collect run general_search
uv run bad-agent collect run form_submission
uv run bad-agent collect run video_discovery
```

### Configuration Options

Key environment variables:
- `BROWSERBASE_API_KEY`: Your Browserbase API key
- `BROWSERBASE_PROJECT_ID`: Your Browserbase project ID
- `OPENAI_API_KEY`: OpenAI API key for AI agents
- `S3_BUCKET_NAME`: S3 bucket for cloud storage (optional)
- `LOG_LEVEL`: Logging verbosity (INFO, DEBUG, etc.)

## Architecture

### Core Components

- **Orchestrator**: Manages browser sessions, AI agents, and data collection
- **Browser Clients**: Interfaces for Browserbase and Stagehand services
- **Data Collector**: Captures screenshots, HTML, and action metadata
- **Dataset Builder**: Processes raw data into training-ready formats
- **Storage Manager**: Handles local and S3 storage with compression
- **PII Scrubber**: Removes sensitive information from captured data

### Data Flow

```
1. Orchestrator creates Browserbase session
2. AI Agent (browser-use + OpenAI) performs web tasks
3. Data Collector captures each step:
   - Screenshot (WebP)
   - HTML content (gzipped)
   - AI reasoning and actions
4. Storage Manager saves to local/S3
5. Dataset Builder processes into JSONL format
6. PII Scrubber sanitizes sensitive data
```

## Example Workflows

The project includes several pre-built workflows:

### General Search
Performs web searches and captures navigation patterns:
```python
# Creates workflow for Google search
create_general_search_workflow(search_query="large language models")
```

### Form Submission
Captures form filling and submission interactions:
```python
# Handles various form types and validation
create_form_submission_workflow(form_type="contact", fields=["name", "email"])
```

### Video Discovery
Records video platform interactions:
```python
# Captures video search and playback patterns
create_video_discovery_workflow(platform="youtube", query="machine learning")
```

## Dataset Applications

The generated datasets are suitable for:

- **Web Agent Training**: Fine-tuning LLMs for web automation
- **UI Understanding**: Teaching models to interpret web interfaces
- **Action Prediction**: Training models to predict user actions
- **Workflow Learning**: Capturing complex multi-step web tasks
- **Accessibility Research**: Understanding web interaction patterns

## Contributing

We welcome contributions! Please see our contributing guidelines for:

- Adding new workflows
- Improving data collection
- Enhancing dataset quality
- Expanding storage options

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: [Report bugs and request features](https://github.com/yourusername/browser-agent-dataset/issues)
- Documentation: [Full documentation](https://github.com/yourusername/browser-agent-dataset/wiki)
- Community: [Join our Discord](https://discord.gg/browser-agent-dataset) 