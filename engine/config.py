"""Engine configuration — single place to tune model, beta header, and screen scaling.

The computer-use tool is model-versioned. As of mid-2026 the latest tool is
`computer_20251124`, gated behind the `computer-use-2025-11-24` beta header, and
supported on Opus 4.8 / 4.7 / 4.6, Sonnet 4.6, and Opus 4.5.

NOTE: Claude Fable 5 is NOT on the computer-use supported-model list, so this engine
defaults to Opus 4.8. Don't switch MODEL to claude-fable-5 — the API will reject the tool.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


# Per-model computer-use wiring. Pick the row matching MODEL.
_TOOL_MATRIX = {
    # newer tool: Opus 4.8/4.7/4.6, Sonnet 4.6, Opus 4.5
    "new": {
        "tool_type": "computer_20251124",
        "beta": "computer-use-2025-11-24",
        "supports_zoom": True,
        "image_long_edge_limit": 2576,   # Opus 4.8/4.7 accept up to 2576px on the long edge
    },
    # older tool: Sonnet 4.5, Haiku 4.5, Opus 4.1, etc.
    "old": {
        "tool_type": "computer_20250124",
        "beta": "computer-use-2025-01-24",
        "supports_zoom": False,
        "image_long_edge_limit": 1568,   # earlier models: 1568px long edge, ~1.15MP
    },
}

# Which models use which tool generation.
_NEW_TOOL_MODELS = {
    "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
    "claude-sonnet-4-6", "claude-opus-4-5",
}


@dataclass
class Config:
    # --- Model ---
    model: str = os.environ.get("JOBAGENT_MODEL", "claude-opus-4-8")
    max_tokens: int = 4096
    effort: str = os.environ.get("JOBAGENT_EFFORT", "medium")  # low|medium|high — medium is the computer-use sweet spot
    api_key: str | None = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY"))

    # --- Loop safety ---
    max_steps: int = int(os.environ.get("JOBAGENT_MAX_STEPS", "40"))
    # "step"  = pause for human confirmation before every actuating action (click/type/key/drag/scroll)
    # "auto"  = run unattended up to max_steps. Even in auto, CLICKS still require confirmation
    #           unless allow_submit is True — the engine can't tell a "Submit" click from any other,
    #           so a click is the conservative gate point.
    mode: str = os.environ.get("JOBAGENT_MODE", "step")
    # Code-level interlock: when False, click actions are never auto-executed (always confirmed),
    # so a final Submit/Apply can't fire unattended. Set True (via --allow-submit) to lift it.
    allow_submit: bool = os.environ.get("JOBAGENT_ALLOW_SUBMIT", "").lower() in ("1", "true", "yes")

    # --- Screen / scaling ---
    # The image we send to Claude. Smaller = cheaper + historically more accurate; larger = crisper text.
    # 1366 is a good balance; raise toward image_long_edge_limit on Opus 4.8 for crisper small text.
    target_long_edge: int = int(os.environ.get("JOBAGENT_LONG_EDGE", "1366"))
    enable_zoom: bool = True

    def _row(self) -> dict:
        return _TOOL_MATRIX["new"] if self.model in _NEW_TOOL_MODELS else _TOOL_MATRIX["old"]

    @property
    def tool_type(self) -> str:
        return self._row()["tool_type"]

    @property
    def beta(self) -> str:
        return self._row()["beta"]

    @property
    def supports_zoom(self) -> bool:
        return self._row()["supports_zoom"]

    @property
    def image_long_edge_limit(self) -> int:
        return self._row()["image_long_edge_limit"]

    @property
    def effective_long_edge(self) -> int:
        # Never exceed the model's hard image limit.
        return min(self.target_long_edge, self.image_long_edge_limit)
