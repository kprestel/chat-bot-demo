from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel, ModelMessage as FunctionModelMessage, ModelResponse
from pydantic_ai.messages import ToolCallPart

from chat_bot_demo.config import AppConfig
from chat_bot_demo.tools.file_read import FileReadTool


class AgentReply(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class AgentDeps:
    file_tool: FileReadTool
    tool_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ChatTurnResult:
    assistant_message: str
    sources: list[str] = field(default_factory=list)
    tool_events: list[str] = field(default_factory=list)


def build_agent(config: AppConfig) -> Agent[AgentDeps, AgentReply]:
    agent = Agent(
        _build_model(config),
        deps_type=AgentDeps,
        output_type=AgentReply,
        system_prompt=config.system_prompt,
    )

    @agent.tool
    def read_file(ctx: RunContext[AgentDeps], path: str) -> str:
        result = ctx.deps.file_tool.run(path)
        if result.get("error"):
            line = f"read_file {path} -> {result['error']}"
        else:
            truncated = " (truncated)" if result.get("truncated") else ""
            line = f"read_file {result['path']}{truncated}"
        ctx.deps.tool_events.append(line)
        return ctx.deps.file_tool.format_for_agent(result)

    return agent


def _build_model(config: AppConfig) -> FunctionModel | str:
    if config.agent_mode == "offline":
        return FunctionModel(_offline_model)
    if config.agent_mode == "real":
        return config.model_name
    raise RuntimeError(f"Unsupported agent mode: {config.agent_mode}")


def _offline_model(messages: list[FunctionModelMessage], info: AgentInfo) -> ModelResponse:
    del info
    last_message = messages[-1]
    tool_return = next(
        (
            part
            for part in last_message.parts
            if isinstance(part, ToolReturnPart) and part.tool_name == "read_file"
        ),
        None,
    )
    if tool_return is not None:
        return ModelResponse(
            parts=[ToolCallPart("final_result", _build_offline_reply(str(tool_return.content)))]
        )

    user_prompt = _latest_user_prompt(messages)
    path = _choose_demo_file(user_prompt)
    if path:
        return ModelResponse(parts=[ToolCallPart("read_file", {"path": path})])

    return ModelResponse(
        parts=[
            ToolCallPart(
                "final_result",
                {
                    "answer": (
                        "I can answer questions about pricing, refunds, support, and "
                        "the company overview. Ask about one of those topics to see the file tool."
                    ),
                    "sources": [],
                },
            )
        ]
    )


def _latest_user_prompt(messages: list[ModelMessage]) -> str:
    for message in reversed(messages):
        for part in message.parts:
            if isinstance(part, UserPromptPart):
                return str(part.content).lower()
    return ""


def _choose_demo_file(user_text: str) -> str | None:
    keyword_map = {
        "pricing": "pricing.md",
        "price": "pricing.md",
        "refund": "refund_policy.md",
        "cancel": "refund_policy.md",
        "support": "support_playbook.md",
        "hours": "support_playbook.md",
        "company": "company_overview.md",
        "overview": "company_overview.md",
        "onboarding": "company_overview.md",
    }
    for keyword, filename in keyword_map.items():
        if keyword in user_text:
            return filename
    return None


def _build_offline_reply(tool_content: str) -> dict[str, Any]:
    source = "unknown"
    error = None
    content_lines: list[str] = []
    in_content = False
    for line in tool_content.splitlines():
        if line.startswith("SOURCE: "):
            source = line.removeprefix("SOURCE: ").strip()
        elif line.startswith("ERROR: "):
            error = line.removeprefix("ERROR: ").strip()
        elif line == "CONTENT:":
            in_content = True
        elif in_content:
            content_lines.append(line)

    if error:
        return {"answer": f"I could not read `{source}`: {error}", "sources": [source]}

    content = "\n".join(content_lines).strip()
    summary = _summarize_document(content)
    return {"answer": f"According to `{source}`, {summary}", "sources": [source]}


def _summarize_document(content: str) -> str:
    lines = [line.strip("- ").strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return "the document did not contain readable content."
    if len(lines) <= 3:
        return " ".join(lines)

    headline = lines[0]
    details = "; ".join(lines[1:4])
    return f"{headline}. Key details: {details}"


@dataclass(slots=True)
class ChatSession:
    agent: Agent[AgentDeps, AgentReply]
    file_tool: FileReadTool
    history: list[ModelMessage] = field(default_factory=list)

    async def process_user_message(self, content: str) -> ChatTurnResult:
        deps = AgentDeps(file_tool=self.file_tool)
        result = await self.agent.run(content, deps=deps, message_history=self.history)
        self.history = result.all_messages()

        reply = result.output
        sources = list(dict.fromkeys(reply.sources))
        return ChatTurnResult(
            assistant_message=reply.answer,
            sources=sources,
            tool_events=deps.tool_events,
        )

    def process_user_message_sync(self, content: str) -> ChatTurnResult:
        deps = AgentDeps(file_tool=self.file_tool)
        result = self.agent.run_sync(content, deps=deps, message_history=self.history)
        self.history = result.all_messages()

        reply = result.output
        sources = list(dict.fromkeys(reply.sources))
        return ChatTurnResult(
            assistant_message=reply.answer,
            sources=sources,
            tool_events=deps.tool_events,
        )
