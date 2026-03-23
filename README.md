# Chat Bot Demo

A small Python chatbot demo with a `textual` terminal UI, a `pydantic-ai` agent, a safe local file-read tool, and bundled business documents for grounded answers.

## Features

- Interactive TUI chat experience built with `textual`
- `pydantic-ai` agent with structured output (`answer` + `sources`)
- Offline demo mode by default, plus optional real-model mode
- Model-invoked `read_file` tool constrained to bundled demo documents
- In-memory session history for the current run
- Demo data covering pricing, refunds, support, and company overview
- Tests for the file tool, chat orchestration, and a TUI smoke flow

## Requirements

- Python 3.12+
- `uv` recommended for dependency management and running commands

## Quick Start

Install dependencies:

```bash
uv sync
```

Run the demo in offline mode:

```bash
uv run chat-bot-demo
```

Optional real-model mode:

```bash
CHAT_BOT_AGENT_MODE=real CHAT_BOT_MODEL=openai:gpt-4.1-mini OPENAI_API_KEY=your_key uv run chat-bot-demo
```

## Demo Topics

Ask about:

- pricing
- refund policy
- support hours
- company overview

The TUI will show the conversation in the main panel, source paths in assistant replies, and file tool activity in the side panel.

## Tests

```bash
uv run --extra dev pytest
```
