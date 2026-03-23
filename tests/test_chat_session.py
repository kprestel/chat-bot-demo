from pathlib import Path

import pytest

from chat_bot_demo.agent.service import ChatSession, build_agent
from chat_bot_demo.config import AppConfig
from chat_bot_demo.tools.file_read import FileReadTool


def build_session() -> ChatSession:
    config = AppConfig(agent_mode="offline")
    file_tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))
    return ChatSession(
        agent=build_agent(config),
        file_tool=file_tool,
    )


@pytest.mark.asyncio
async def test_chat_session_runs_tool_cycle() -> None:
    session = build_session()

    result = await session.process_user_message("What is the refund policy?")

    assert result.tool_events == ["read_file refund_policy.md"]
    assert "refund_policy.md" in result.assistant_message
    assert result.sources == ["refund_policy.md"]
    assert session.history


@pytest.mark.asyncio
async def test_chat_session_returns_general_help_when_no_tool_needed() -> None:
    session = build_session()

    result = await session.process_user_message("Hello there")

    assert not result.tool_events
    assert "pricing, refunds, support" in result.assistant_message


@pytest.mark.asyncio
async def test_chat_session_reuses_history_across_turns() -> None:
    session = build_session()

    first = await session.process_user_message("What is the pricing?")
    second = await session.process_user_message("What are the support hours?")

    assert first.sources == ["pricing.md"]
    assert second.sources == ["support_playbook.md"]
    assert len(session.history) >= 4
