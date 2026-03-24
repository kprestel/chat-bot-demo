from pathlib import Path

from chat_bot_demo.tools.file_read import FileReadTool


def test_reads_allowed_file() -> None:
    tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))

    result = tool.read("pricing.md")

    assert result.error is None
    assert result.path == "pricing.md"
    assert "Starter: $299 per month" in result.content


def test_rejects_path_traversal() -> None:
    tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))

    result = tool.read("../README.md")

    assert result.error == "Path must stay inside the demo data directory."


def test_missing_file_returns_error() -> None:
    tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))

    result = tool.read("missing.md")

    assert result.error == "File not found."


def test_search_respects_allowed_paths() -> None:
    tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))

    result = tool.search("refund after renewal", allowed_paths={"refund_policy.md"})

    assert [match.path for match in result.matches] == ["refund_policy.md"]


def test_support_policy_returns_structured_result() -> None:
    tool = FileReadTool(root=Path("src/chat_bot_demo/demo_data"))

    result = tool.get_support_policy("p1")

    assert result.source == "support_playbook.md"
    assert result.response_target == "1 hour"
