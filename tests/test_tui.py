from pathlib import Path

import pytest
from textual.widgets import Input

from chat_bot_demo.agent.service import ChatSession, build_agent
from chat_bot_demo.config import AppConfig
from chat_bot_demo.tools.file_read import FileReadTool
from chat_bot_demo.tui import build_app


@pytest.mark.asyncio
async def test_tui_smoke_flow() -> None:
    config = AppConfig(agent_mode="offline")
    file_tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))
    session = ChatSession(
        agent=build_agent(config),
        file_tool=file_tool,
    )
    app = build_app(session=session, config=config)

    async with app.run_test() as pilot:
        await pilot.pause()
        composer = app.query_one("#composer", Input)
        composer.insert_text_at_cursor("What is the pricing?")
        await composer.action_submit()
        await pilot.pause()

        assert "Sources: pricing.md" in app.chat_events[-1].message
        assert "pricing.md" in app.tool_events[-1]
