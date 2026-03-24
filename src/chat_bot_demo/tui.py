from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, RichLog, Static

from chat_bot_demo.agent.service import ChatSession
from chat_bot_demo.config import AppConfig


@dataclass(slots=True)
class TurnView:
    speaker: str
    message: str


class ChatBotDemoApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    #chat-panel, #tool-panel {
        height: 1fr;
        border: round $accent;
    }

    #tool-panel {
        width: 36;
    }

    #composer {
        dock: bottom;
        height: 3;
        margin: 1 0 0 0;
    }

    Input {
        width: 1fr;
    }
    """

    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(self, session: ChatSession, config: AppConfig) -> None:
        super().__init__()
        self.session = session
        self.config = config
        self.chat_events: list[TurnView] = []
        self.tool_events: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(self._status_text(), id="status")
        with Horizontal(id="body"):
            yield RichLog(id="chat-panel", markup=True, wrap=True, highlight=True)
            yield RichLog(id="tool-panel", markup=True, wrap=True, highlight=True)
        yield Input(
            placeholder="Ask a support-triage question that may involve pricing, refunds, support, or company info.",
            id="composer",
        )
        yield Footer()

    def on_mount(self) -> None:
        chat_log = self.query_one("#chat-panel", RichLog)
        tool_log = self.query_one("#tool-panel", RichLog)
        self.chat_events.append(
            TurnView(
                speaker="Assistant",
                message="Ask a support-triage question and I will route it to the right specialists.",
            )
        )
        self.tool_events.append("Activity: waiting for the first request.")
        chat_log.write("[b]Assistant[/b]: Ask a support-triage question and I will route it to the right specialists.")
        tool_log.write("[b]Activity[/b]: waiting for the first request.")

    @on(Input.Submitted, "#composer")
    async def handle_submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        event.input.value = ""
        chat_log = self.query_one("#chat-panel", RichLog)
        tool_log = self.query_one("#tool-panel", RichLog)
        status = self.query_one("#status", Static)

        chat_log.write(f"[b]User[/b]: {text}")
        self.chat_events.append(TurnView(speaker="User", message=text))
        status.update("Working...")

        try:
            result = await self.session.process_user_message(text)
        except Exception as exc:  # pragma: no cover - defensive UI path
            chat_log.write(f"[b red]Error[/b red]: {exc}")
            status.update(self._status_text(error=str(exc)))
            return

        for line in result.activity_events:
            self.tool_events.append(line)
            if line.startswith("handoff"):
                tool_log.write(f"[bold cyan]{line}[/bold cyan]")
            elif "->" in line:
                tool_log.write(f"[yellow]{line}[/yellow]")
            else:
                tool_log.write(line)

        reply = result.reply
        rendered_message = reply.answer
        if reply.topics_used:
            rendered_message += f"\nTopics: {', '.join(reply.topics_used)}"
        if reply.agents_consulted:
            rendered_message += f"\nAgents: {', '.join(reply.agents_consulted)}"
        if reply.citations:
            rendered_message += "\nCitations:"
            for citation in reply.citations:
                rendered_message += f"\n- {citation.source}: {citation.excerpt}"
        if reply.follow_up_questions:
            rendered_message += "\nFollow-ups:"
            for item in reply.follow_up_questions:
                rendered_message += f"\n- {item}"

        chat_log.write(f"[b]Assistant[/b]: {rendered_message}")
        self.chat_events.append(TurnView(speaker="Assistant", message=rendered_message))
        status.update(self._status_text())

    def _status_text(self, error: str | None = None) -> str:
        if error:
            return f"Mode: {self.config.agent_mode} | Error: {error}"
        return f"Mode: {self.config.agent_mode} | Demo docs: {self.config.demo_data_root}"


def build_app(session: ChatSession, config: AppConfig) -> ChatBotDemoApp:
    return ChatBotDemoApp(session=session, config=config)
