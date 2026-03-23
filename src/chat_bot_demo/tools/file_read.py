from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class FileReadTool:
    root: Path
    max_chars: int = 4000

    def run(self, path: str) -> dict[str, object]:
        root = self.root.resolve()
        try:
            resolved = self._resolve_path(path)
        except ValueError as exc:
            return {"path": path, "content": "", "truncated": False, "error": str(exc)}

        if not resolved.exists():
            return {"path": path, "content": "", "truncated": False, "error": "File not found."}

        content = resolved.read_text(encoding="utf-8")
        truncated = len(content) > self.max_chars
        if truncated:
            content = content[: self.max_chars].rstrip() + "\n...[truncated]"

        return {
            "path": str(resolved.relative_to(root)),
            "content": content,
            "truncated": truncated,
            "error": None,
        }

    def format_for_agent(self, result: dict[str, object]) -> str:
        if result.get("error"):
            return f"SOURCE: {result['path']}\nERROR: {result['error']}"

        truncated = "yes" if result.get("truncated") else "no"
        return (
            f"SOURCE: {result['path']}\n"
            f"TRUNCATED: {truncated}\n"
            "CONTENT:\n"
            f"{result['content']}"
        )

    def _resolve_path(self, raw_path: str) -> Path:
        candidate = (self.root / raw_path).resolve()
        root = self.root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Path must stay inside the demo data directory.") from exc
        return candidate
