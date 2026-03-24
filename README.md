# Chat Bot Demo

A small Python chatbot demo with a `textual` terminal UI and a more opinionated `pydantic-ai` support-triage workflow. The demo now shows a coordinator agent delegating to specialist agents, using typed tools, and returning a strongly typed final answer.

## What This Demo Is

This project is not trying to be a production support bot. It is a teaching demo for `pydantic-ai`.

The app presents a realistic but small workflow:

- a user asks a business-support question
- a coordinator agent decides which specialist agents should help
- each specialist uses typed tools against local documents
- the coordinator combines those specialist reports into one typed final answer
- the TUI shows the answer and the orchestration activity

The goal is to make `pydantic-ai` features visible instead of hiding them behind generic chatbot behavior.

## What It Is Trying To Show

This demo is designed to highlight a few specific `pydantic-ai` ideas:

- Multiple agents: one coordinator delegates work to pricing, refund, support, and company specialists.
- Typed tools: tools return structured Pydantic models instead of unstructured text blobs.
- Typed outputs: specialist agents and the coordinator both return Pydantic models.
- Tool-driven grounding: specialists inspect local source documents before answering.
- Observable orchestration: the UI shows handoffs, tool calls, and the final structured response.
- Offline parity: the offline mode still exercises routing and tool usage so the demo works without API keys.

## Features

- Interactive TUI chat experience built with `textual`
- Coordinator agent that routes questions to pricing, refund, support, and company specialists
- Strongly typed `pydantic-ai` outputs for specialist reports, citations, follow-ups, and final answers
- Offline demo mode by default, plus optional real-model mode
- Typed tools for document discovery, document reads, and support-policy lookups
- Visible routing, handoffs, and tool activity in the TUI side panel
- In-memory session history for the current run
- Demo data covering pricing, refunds, support, and company overview
- Tests for typed tools, chat orchestration, and a TUI smoke flow

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

## Architecture Overview

The demo has four main parts:

- `src/chat_bot_demo/agent/service.py`
  Defines the coordinator agent, the specialist agents, shared dependencies, typed outputs, and the offline orchestration models.
- `src/chat_bot_demo/tools/file_read.py`
  Defines the local knowledge tools. These tools list documents, search them, read them safely, and expose a support-policy helper.
- `src/chat_bot_demo/tui.py`
  Renders the chat UI, including the final answer and the routing/tool activity stream.
- `src/chat_bot_demo/demo_data/*.md`
  The local business documents used as the demo knowledge base.

## How A Request Flows

When the user submits a prompt, the demo does this:

1. The coordinator agent reads the question and decides which topics are involved.
2. The coordinator calls one or more specialist-agent tools such as pricing, refunds, or support.
3. Each specialist uses typed tools to search its allowed document set and read the relevant document.
4. The support specialist can also call a typed support-policy helper to show a non-file tool.
5. Each specialist returns a structured `SpecialistReport`.
6. The coordinator merges those reports into a structured `CoordinatorReply`.
7. The TUI renders the final answer, citations, consulted agents, follow-up questions, and the side-panel activity log.

## What The User Sees

The interface has two panels:

- Main panel: the final assistant response, including answer text, topics used, consulted agents, citations, and follow-up questions.
- Side panel: the orchestration trace, including coordinator handoffs and tool calls made by specialists.

This matters because the point of the demo is not just “get an answer.” It is to show how the answer was assembled.

## Demo Topics

Ask about:

- pricing and discounts
- refund policy and renewal eligibility
- support hours and response targets
- company overview and onboarding
- cross-topic triage questions that need multiple specialists

The TUI shows the structured assistant response in the main panel and routing/tool activity in the side panel. Good demo prompts:

- `We have 20 users. Which plan fits us and do annual contracts get a discount?`
- `Can I still get a refund after renewal?`
- `What are your outage response targets and support hours?`
- `We are evaluating the product for our finance team. What do you do and how fast is onboarding?`
- `We have 20 users, may need a refund, and want to know outage response targets.`

## Why The Demo Uses Local Documents

The bundled markdown files keep the demo deterministic and easy to explain.

- They make tool usage obvious.
- They give specialists a grounded source of truth.
- They keep offline mode meaningful.
- They let the tests verify end-to-end behavior without external services.

## Offline Mode vs Real Mode

`offline` mode:

- Uses `FunctionModel`-based offline logic.
- Still performs coordinator routing, specialist delegation, and typed tool calls.
- Is the best mode for teaching or local demos.

`real` mode:

- Uses the configured model name from `CHAT_BOT_MODEL`.
- Keeps the same agent graph, tool interfaces, and output schemas.
- Is useful for showing that the design is a real `pydantic-ai` application shape, not only a mocked script.

## Tests

```bash
uv run --extra dev pytest
```
