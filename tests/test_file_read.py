from pathlib import Path

from chat_bot_demo.tools.file_read import FileReadTool


def test_reads_allowed_file() -> None:
    tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))

    result = tool.run("pricing.md")

    assert result["error"] is None
    assert result["path"] == "pricing.md"
    assert "Starter: $299 per month" in str(result["content"])


def test_rejects_path_traversal() -> None:
    tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))

    result = tool.run("../README.md")

    assert result["error"] == "Path must stay inside the demo data directory."


def test_missing_file_returns_error() -> None:
    tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))

    result = tool.run("missing.md")

    assert result["error"] == "File not found."
