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

    assert "Refunds:" in result.assistant_message
    assert result.reply.topics_used == ["refunds"]
    assert result.reply.agents_consulted == ["refund specialist"]
    assert result.sources == ["refund_policy.md"]
    assert any(event == "handoff coordinator -> refund specialist" for event in result.activity_events)
    assert any("refund specialist.search_documents" in event for event in result.activity_events)
    assert any("refund specialist.read_document refund_policy.md" in event for event in result.activity_events)
    assert session.history


@pytest.mark.asyncio
async def test_chat_session_returns_general_help_when_no_tool_needed() -> None:
    session = build_session()

    result = await session.process_user_message("Hello there")

    assert not result.activity_events
    assert "pricing, refunds, support" in result.assistant_message
    assert result.reply.follow_up_questions


@pytest.mark.asyncio
async def test_chat_session_reuses_history_across_turns() -> None:
    session = build_session()

    first = await session.process_user_message("What is the pricing?")
    second = await session.process_user_message("What are the support hours?")

    assert first.reply.topics_used == ["pricing"]
    assert second.reply.topics_used == ["support"]
    assert len(session.history) >= 4


@pytest.mark.asyncio
async def test_chat_session_routes_to_multiple_specialists() -> None:
    session = build_session()

    result = await session.process_user_message(
        "We have 20 users, may need a refund, and want to know outage response targets."
    )

    assert result.reply.topics_used == ["pricing", "refunds", "support"]
    assert result.reply.agents_consulted == [
        "pricing specialist",
        "refund specialist",
        "support specialist",
    ]
    assert set(result.sources) == {"pricing.md", "refund_policy.md", "support_playbook.md"}
    assert any("support specialist.get_support_policy" in event for event in result.activity_events)
