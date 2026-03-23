from __future__ import annotations

from chat_bot_demo.agent.service import ChatSession, build_agent
from chat_bot_demo.config import AppConfig
from chat_bot_demo.tools.file_read import FileReadTool
from chat_bot_demo.tui import build_app


def main() -> None:
    config = AppConfig.from_env()
    file_tool = FileReadTool(root=config.demo_data_root, max_chars=config.max_file_chars)
    session = ChatSession(
        agent=build_agent(config),
        file_tool=file_tool,
    )
    app = build_app(session=session, config=config)
    app.run()


if __name__ == "__main__":
    main()
