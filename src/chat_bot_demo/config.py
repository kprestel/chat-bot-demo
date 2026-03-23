from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


PACKAGE_ROOT = Path(__file__).resolve().parent
DEMO_DATA_ROOT = PACKAGE_ROOT / "demo_data"


@dataclass(slots=True)
class AppConfig:
    agent_mode: str = "offline"
    model_name: str = "openai:gpt-4.1-mini"
    demo_data_root: Path = DEMO_DATA_ROOT
    max_file_chars: int = 4000
    system_prompt: str = (
        "You are a business assistant for a product demo. Use the file tool when "
        "the answer depends on local business documents. Always return a concise answer "
        "and include the source file paths you actually used."
    )

    @classmethod
    def from_env(cls) -> "AppConfig":
        mode = os.getenv("CHAT_BOT_AGENT_MODE", "").strip().lower()
        if not mode:
            legacy_mode = os.getenv("CHAT_BOT_PROVIDER", "").strip().lower()
            mode = "real" if legacy_mode == "openai" else "offline"
        return cls(
            agent_mode=mode or "offline",
            model_name=os.getenv("CHAT_BOT_MODEL", "openai:gpt-4.1-mini").strip(),
        )
