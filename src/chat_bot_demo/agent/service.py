from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel, ModelMessage as FunctionModelMessage, ModelResponse

from chat_bot_demo.config import AppConfig
from chat_bot_demo.tools.file_read import (
    DocumentContent,
    DocumentSearchResult,
    DocumentSummary,
    FileReadTool,
    SupportPolicyResult,
)


class Citation(BaseModel):
    source: str
    excerpt: str


class SpecialistReport(BaseModel):
    agent_name: str
    topic: str
    summary: str
    citations: list[Citation] = Field(default_factory=list)
    follow_up_question: str | None = None


class CoordinatorReply(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    topics_used: list[str] = Field(default_factory=list)
    agents_consulted: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class AgentDeps:
    file_tool: FileReadTool
    activity_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ChatTurnResult:
    reply: CoordinatorReply
    activity_events: list[str] = field(default_factory=list)

    @property
    def assistant_message(self) -> str:
        return self.reply.answer

    @property
    def sources(self) -> list[str]:
        seen: list[str] = []
        for citation in self.reply.citations:
            if citation.source not in seen:
                seen.append(citation.source)
        return seen


TOPIC_DETAILS: dict[str, dict[str, str | tuple[str, ...]]] = {
    "pricing": {
        "doc": "pricing.md",
        "label": "pricing specialist",
        "follow_up": "How many users do you need, and do you want monthly or annual billing?",
    },
    "refunds": {
        "doc": "refund_policy.md",
        "label": "refund specialist",
        "follow_up": "Has the subscription renewed already, or is the request still within the first 30 days?",
    },
    "support": {
        "doc": "support_playbook.md",
        "label": "support specialist",
        "follow_up": "Is the issue an outage, a major issue, or a general question?",
    },
    "company": {
        "doc": "company_overview.md",
        "label": "company specialist",
        "follow_up": "Which part of the company overview matters most: product fit, onboarding, or positioning?",
    },
}


KEYWORD_TOPICS: dict[str, tuple[str, ...]] = {
    "pricing": ("pricing", "price", "cost", "plan", "plans", "users", "discount", "annual", "starter", "growth"),
    "refunds": ("refund", "refunds", "cancel", "cancellation", "renewal", "terminate", "termination"),
    "support": ("support", "hours", "response", "sla", "outage", "incident", "p1", "p2", "p3"),
    "company": ("company", "overview", "northstar", "onboarding", "finance teams", "workflow software"),
}


def build_agent(config: AppConfig) -> Agent[AgentDeps, CoordinatorReply]:
    specialists = {
        topic: _build_specialist_agent(config, topic)
        for topic in ("pricing", "refunds", "support", "company")
    }

    coordinator = Agent(
        _build_model(config, kind="coordinator", topic=None),
        deps_type=AgentDeps,
        output_type=CoordinatorReply,
        name="triage_coordinator",
        instructions=_coordinator_instructions(),
    )

    for topic, specialist in specialists.items():
        coordinator.tool(_make_consult_tool(topic, specialist), name=f"consult_{topic}")

    return coordinator


def _build_specialist_agent(config: AppConfig, topic: str) -> Agent[AgentDeps, SpecialistReport]:
    document_path = cast(str, TOPIC_DETAILS[topic]["doc"])
    label = cast(str, TOPIC_DETAILS[topic]["label"])
    allowed_paths = {document_path}

    agent = Agent(
        _build_model(config, kind="specialist", topic=topic),
        deps_type=AgentDeps,
        output_type=SpecialistReport,
        name=topic,
        instructions=_specialist_instructions(topic),
    )

    @agent.tool
    def list_documents(ctx: RunContext[AgentDeps]) -> list[DocumentSummary]:
        docs = [doc for doc in ctx.deps.file_tool.list_documents() if doc.path in allowed_paths]
        ctx.deps.activity_events.append(f"{label}.list_documents -> {', '.join(doc.path for doc in docs)}")
        return docs

    @agent.tool
    def search_documents(ctx: RunContext[AgentDeps], query: str) -> DocumentSearchResult:
        result = ctx.deps.file_tool.search(query, allowed_paths=allowed_paths)
        rendered = ", ".join(match.path for match in result.matches) or "no matches"
        ctx.deps.activity_events.append(f"{label}.search_documents query={query!r} -> {rendered}")
        return result

    @agent.tool
    def read_document(ctx: RunContext[AgentDeps], path: str) -> DocumentContent:
        result = ctx.deps.file_tool.read(path)
        suffix = f" -> {result.error}" if result.error else ""
        ctx.deps.activity_events.append(f"{label}.read_document {path}{suffix}")
        return result

    if topic == "support":

        @agent.tool
        def get_support_policy(ctx: RunContext[AgentDeps], severity: str) -> SupportPolicyResult:
            result = ctx.deps.file_tool.get_support_policy(severity)
            ctx.deps.activity_events.append(
                f"{label}.get_support_policy severity={severity!r} -> target {result.response_target}"
            )
            return result

    return agent


def _make_consult_tool(
    topic: str,
    specialist: Agent[AgentDeps, SpecialistReport],
):
    async def consult_specialist(ctx: RunContext[AgentDeps], customer_question: str) -> SpecialistReport:
        label = cast(str, TOPIC_DETAILS[topic]["label"])
        ctx.deps.activity_events.append(f"handoff coordinator -> {label}")
        result = await specialist.run(customer_question, deps=ctx.deps)
        return result.output

    return consult_specialist


def _build_model(config: AppConfig, *, kind: str, topic: str | None) -> FunctionModel | str:
    if config.agent_mode == "offline":
        if kind == "coordinator":
            return FunctionModel(_offline_coordinator_model)
        return FunctionModel(_make_offline_specialist_model(cast(str, topic)))
    if config.agent_mode == "real":
        return config.model_name
    raise RuntimeError(f"Unsupported agent mode: {config.agent_mode}")


def _offline_coordinator_model(messages: list[FunctionModelMessage], info: AgentInfo) -> ModelResponse:
    del info
    tool_returns = _tool_returns(messages[-1], "consult_")
    if tool_returns:
        reports = [cast(SpecialistReport, part.content) for part in tool_returns]
        reply = _build_coordinator_reply(reports)
        return ModelResponse(parts=[ToolCallPart("final_result", reply.model_dump(mode="json"))])

    question = _latest_user_prompt(messages)
    topics = _topics_for_question(question)
    if not topics:
        reply = CoordinatorReply(
            answer=(
                "I can triage questions across pricing, refunds, support, and company overview. "
                "Ask a question that needs one or more of those specialists."
            ),
            follow_up_questions=[
                "Do you want pricing guidance, refund eligibility, support response targets, or company background?"
            ],
        )
        return ModelResponse(parts=[ToolCallPart("final_result", reply.model_dump(mode="json"))])

    calls = [ToolCallPart(f"consult_{topic}", {"customer_question": question}) for topic in topics]
    return ModelResponse(parts=calls)


def _make_offline_specialist_model(topic: str):
    def _model(messages: list[FunctionModelMessage], info: AgentInfo) -> ModelResponse:
        del info
        last_message = messages[-1]
        query = _latest_user_prompt(messages)
        search_result = _tool_return(last_message, "search_documents")
        document_result = _tool_return(last_message, "read_document")
        policy_result = _tool_return(last_message, "get_support_policy")

        if document_result is not None or policy_result is not None:
            report = _build_specialist_report(
                topic=topic,
                query=query,
                document=cast(DocumentContent | None, getattr(document_result, "content", None)),
                policy=cast(SupportPolicyResult | None, getattr(policy_result, "content", None)),
            )
            return ModelResponse(parts=[ToolCallPart("final_result", report.model_dump(mode="json"))])

        if search_result is not None:
            result = cast(DocumentSearchResult, search_result.content)
            calls: list[ToolCallPart] = []
            if result.matches:
                calls.append(ToolCallPart("read_document", {"path": result.matches[0].path}))
            if topic == "support":
                severity = _support_severity(query)
                calls.append(ToolCallPart("get_support_policy", {"severity": severity}))
            if not calls:
                report = _build_specialist_report(topic=topic, query=query, document=None, policy=None)
                return ModelResponse(parts=[ToolCallPart("final_result", report.model_dump(mode="json"))])
            return ModelResponse(parts=calls)

        return ModelResponse(parts=[ToolCallPart("search_documents", {"query": query})])

    return _model


def _coordinator_instructions() -> str:
    return (
        "You are the support triage coordinator. Route the customer question to the right specialists, "
        "consult multiple specialists when the request spans multiple topics, and return a structured final answer "
        "with citations, topics used, consulted agents, and useful follow-up questions."
    )


def _specialist_instructions(topic: str) -> str:
    document_path = cast(str, TOPIC_DETAILS[topic]["doc"])
    return (
        f"You are the {TOPIC_DETAILS[topic]['label']}. Use the typed tools to inspect only `{document_path}` "
        "and return a concise structured report with citations and one useful follow-up question."
    )


def _latest_user_prompt(messages: list[ModelMessage]) -> str:
    for message in reversed(messages):
        for part in message.parts:
            if isinstance(part, UserPromptPart):
                return str(part.content).strip()
    return ""


def _topics_for_question(question: str) -> list[str]:
    lowered = question.lower()
    topics = [
        topic
        for topic, keywords in KEYWORD_TOPICS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    return topics


def _tool_return(message: ModelMessage, tool_name: str) -> ToolReturnPart | None:
    for part in message.parts:
        if isinstance(part, ToolReturnPart) and part.tool_name == tool_name:
            return part
    return None


def _tool_returns(message: ModelMessage, tool_name_prefix: str) -> list[ToolReturnPart]:
    return [
        part
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.tool_name.startswith(tool_name_prefix)
    ]


def _build_specialist_report(
    *,
    topic: str,
    query: str,
    document: DocumentContent | None,
    policy: SupportPolicyResult | None,
) -> SpecialistReport:
    label = cast(str, TOPIC_DETAILS[topic]["label"])
    follow_up = cast(str, TOPIC_DETAILS[topic]["follow_up"])
    citations: list[Citation] = []

    if document is not None and document.error:
        summary = f"I could not read the supporting document `{document.path}`: {document.error}"
    elif document is not None:
        summary = _summarize_document(topic, query, document)
        citations.append(Citation(source=document.path, excerpt=_excerpt(document.content)))
    else:
        summary = f"I did not find a supporting document for the {topic} request."

    if policy is not None:
        policy_summary = f" For {policy.severity.upper()} issues, the response target is {policy.response_target}."
        summary = f"{summary}{policy_summary}"
        citations.append(
            Citation(
                source=policy.source,
                excerpt=f"Priority target: {policy.response_target}. Support hours: {policy.support_hours}",
            )
        )

    return SpecialistReport(
        agent_name=label,
        topic=topic,
        summary=summary,
        citations=_dedupe_citations(citations),
        follow_up_question=follow_up,
    )


def _build_coordinator_reply(reports: list[SpecialistReport]) -> CoordinatorReply:
    ordered_reports = sorted(reports, key=lambda report: report.topic)
    answer_lines = [f"{report.topic.title()}: {report.summary}" for report in ordered_reports]
    follow_ups = [report.follow_up_question for report in ordered_reports if report.follow_up_question]
    citations: list[Citation] = []
    for report in ordered_reports:
        citations.extend(report.citations)
    return CoordinatorReply(
        answer="\n".join(answer_lines),
        citations=_dedupe_citations(citations),
        topics_used=[report.topic for report in ordered_reports],
        agents_consulted=[report.agent_name for report in ordered_reports],
        follow_up_questions=follow_ups,
    )


def _summarize_document(topic: str, query: str, document: DocumentContent) -> str:
    lines = [line.strip("- ").strip() for line in document.content.splitlines() if line.strip()]
    if len(lines) <= 1:
        return f"The `{document.title}` document did not contain enough detail to answer the question."

    if topic == "pricing":
        return "Pricing is tiered with Starter at $299/month for up to 10 users, Growth at $799/month for up to 35 users, Enterprise on custom annual pricing, and annual contracts discounted by 10 percent."
    if topic == "refunds":
        return "Refunds are available within 30 days of the initial subscription start date, but not for partial months after a renewal begins; enterprise terms follow the signed order form."
    if topic == "support":
        return "Support runs Monday through Friday, 9 AM to 6 PM Eastern Time, with targets of 1 hour for P1 outages, 4 business hours for P2 issues, and 1 business day for P3 questions."
    if topic == "company":
        return "Northstar Ops sells workflow software for mid-market finance teams, focuses on reducing manual month-end close work, centralizes policy and invoice review, and offers standard onboarding in under two weeks."
    return f"Relevant notes from `{document.title}`: {_excerpt(document.content)}"


def _excerpt(content: str, *, limit: int = 160) -> str:
    compact = " ".join(content.split())
    return compact[:limit].rstrip()


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[str, str]] = set()
    deduped: list[Citation] = []
    for citation in citations:
        key = (citation.source, citation.excerpt)
        if key not in seen:
            seen.add(key)
            deduped.append(citation)
    return deduped


def _support_severity(question: str) -> str:
    lowered = question.lower()
    if "p1" in lowered or "outage" in lowered:
        return "p1"
    if "p2" in lowered or "major" in lowered:
        return "p2"
    if "p3" in lowered:
        return "p3"
    return "general"


@dataclass(slots=True)
class ChatSession:
    agent: Agent[AgentDeps, CoordinatorReply]
    file_tool: FileReadTool
    history: list[ModelMessage] = field(default_factory=list)

    async def process_user_message(self, content: str) -> ChatTurnResult:
        deps = AgentDeps(file_tool=self.file_tool)
        result = await self.agent.run(content, deps=deps, message_history=self.history)
        self.history = result.all_messages()
        return ChatTurnResult(reply=result.output, activity_events=deps.activity_events)

    def process_user_message_sync(self, content: str) -> ChatTurnResult:
        deps = AgentDeps(file_tool=self.file_tool)
        result = self.agent.run_sync(content, deps=deps, message_history=self.history)
        self.history = result.all_messages()
        return ChatTurnResult(reply=result.output, activity_events=deps.activity_events)
