from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from pydantic import BaseModel, Field


class DocumentSummary(BaseModel):
    path: str
    title: str
    description: str


class DocumentMatch(BaseModel):
    path: str
    title: str
    score: int
    reason: str


class DocumentSearchResult(BaseModel):
    query: str
    matches: list[DocumentMatch] = Field(default_factory=list)


class DocumentContent(BaseModel):
    path: str
    title: str
    content: str
    truncated: bool = False
    error: str | None = None


class SupportPolicyResult(BaseModel):
    severity: str
    response_target: str
    support_hours: str
    source: str = "support_playbook.md"


@dataclass(slots=True)
class FileReadTool:
    root: Path
    max_chars: int = 4000

    def list_documents(self) -> list[DocumentSummary]:
        docs: list[DocumentSummary] = []
        root = self.root.resolve()
        for path in sorted(root.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            docs.append(
                DocumentSummary(
                    path=str(path.relative_to(root)),
                    title=self._extract_title(text, path),
                    description=self._describe(text),
                )
            )
        return docs

    def search(
        self,
        query: str,
        *,
        allowed_paths: set[str] | None = None,
        limit: int = 3,
    ) -> DocumentSearchResult:
        tokens = self._tokenize(query)
        matches: list[DocumentMatch] = []
        for summary in self.list_documents():
            if allowed_paths is not None and summary.path not in allowed_paths:
                continue
            content = self.read(summary.path).content.lower()
            haystack = f"{summary.path} {summary.title.lower()} {content}"
            score = sum(2 if token in summary.path else 1 for token in tokens if token in haystack)
            if not score and allowed_paths is not None and len(allowed_paths) == 1:
                score = 1
            if score:
                matches.append(
                    DocumentMatch(
                        path=summary.path,
                        title=summary.title,
                        score=score,
                        reason=self._match_reason(summary, query),
                    )
                )
        matches.sort(key=lambda item: (-item.score, item.path))
        return DocumentSearchResult(query=query, matches=matches[:limit])

    def read(self, path: str) -> DocumentContent:
        root = self.root.resolve()
        try:
            resolved = self._resolve_path(path)
        except ValueError as exc:
            return DocumentContent(path=path, title=path, content="", truncated=False, error=str(exc))

        if not resolved.exists():
            return DocumentContent(path=path, title=path, content="", truncated=False, error="File not found.")

        content = resolved.read_text(encoding="utf-8")
        truncated = len(content) > self.max_chars
        if truncated:
            content = content[: self.max_chars].rstrip() + "\n...[truncated]"

        return DocumentContent(
            path=str(resolved.relative_to(root)),
            title=self._extract_title(content, resolved),
            content=content,
            truncated=truncated,
            error=None,
        )

    def get_support_policy(self, severity: str) -> SupportPolicyResult:
        normalized = severity.strip().lower()
        targets = {
            "p1": "1 hour",
            "outage": "1 hour",
            "p2": "4 business hours",
            "major": "4 business hours",
            "p3": "1 business day",
            "general": "1 business day",
        }
        response_target = targets.get(normalized, "1 business day")
        return SupportPolicyResult(
            severity=normalized or "general",
            response_target=response_target,
            support_hours="Monday through Friday, 9 AM to 6 PM Eastern Time.",
        )

    def run(self, path: str) -> dict[str, object]:
        result = self.read(path)
        return result.model_dump()

    def _resolve_path(self, raw_path: str) -> Path:
        candidate = (self.root / raw_path).resolve()
        root = self.root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Path must stay inside the demo data directory.") from exc
        return candidate

    def _extract_title(self, content: str, path: Path) -> str:
        for line in content.splitlines():
            if line.startswith("# "):
                return line.removeprefix("# ").strip()
        return path.stem.replace("_", " ").title()

    def _describe(self, content: str) -> str:
        lines = [line.strip("- ").strip() for line in content.splitlines() if line.strip()]
        if len(lines) <= 1:
            return "Bundled demo document."
        return lines[1][:140]

    def _tokenize(self, text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 2}

    def _match_reason(self, summary: DocumentSummary, query: str) -> str:
        query_lower = query.lower()
        if summary.path.removesuffix(".md").replace("_", " ") in query_lower:
            return "Matched the document path directly."
        if summary.title.lower() in query_lower:
            return "Matched the document title."
        return f"Relevant to: {summary.title}"
