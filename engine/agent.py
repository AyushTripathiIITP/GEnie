"""The agent loop: screenshot -> Claude API -> action -> screenshot -> repeat.

This is the engine that replicates the Claude-browser-extension behaviour you asked for,
but self-hosted: WE take the screenshot, WE send it to the Claude API with the computer
tool, Claude replies with where to move/click/type, and WE actuate it on your real Mac.
"""
from __future__ import annotations

import sys

import anthropic

from .actions import Actuator
from .config import Config
from .screen import Screen

# Actions that change the world. In "step" mode the engine pauses for your OK before each.
_ACTUATING = {
    "left_click", "right_click", "middle_click", "double_click", "triple_click",
    "left_click_drag", "left_mouse_down", "left_mouse_up", "type", "key", "hold_key", "scroll",
}
# Click-like actions: the conservative gate point, since the engine can't identify a Submit
# button. These are never auto-executed unless allow_submit is set (the real submit interlock).
_CLICKS = {
    "left_click", "right_click", "middle_click", "double_click", "triple_click",
    "left_click_drag", "left_mouse_down",
}


class ComputerAgent:
    def __init__(self, cfg: Config, system_prompt: str):
        if not cfg.api_key:
            sys.exit("No API key. Set LITELLM_API_KEY (proxy) or ANTHROPIC_API_KEY in jobagent/engine/.env.")
        self.cfg = cfg
        self.system_prompt = system_prompt
        client_kwargs = {"api_key": cfg.api_key}
        if cfg.base_url:
            client_kwargs["base_url"] = cfg.base_url
        self.client = anthropic.Anthropic(**client_kwargs)
        self.screen = Screen(cfg)
        self.actuator = Actuator(cfg, self.screen)

    def _tool_def(self) -> dict:
        td = {
            "type": self.cfg.tool_type,
            "name": "computer",
            "display_width_px": self.screen.display_width_px,
            "display_height_px": self.screen.display_height_px,
            "display_number": 1,
        }
        if self.cfg.supports_zoom and self.cfg.enable_zoom:
            td["enable_zoom"] = True
        return td

    def run(self, task: str) -> None:
        messages = [{"role": "user", "content": task}]
        tools = [self._tool_def()]

        # effort is unsupported on Haiku 4.5 / Sonnet 4.5 — omit output_config there to avoid a 400.
        extra = {"output_config": {"effort": self.cfg.effort}} if self.cfg.supports_effort else {}

        for step in range(1, self.cfg.max_steps + 1):
            try:
                resp = self.client.beta.messages.create(
                    model=self.cfg.model,
                    max_tokens=self.cfg.max_tokens,
                    system=self.system_prompt,
                    messages=messages,
                    tools=tools,
                    betas=[self.cfg.beta],
                    **extra,
                )
            except anthropic.APIStatusError as e:
                msg = str(e)
                if "credit balance" in msg or "Plans & Billing" in msg:
                    endpoint = self.cfg.base_url or "https://api.anthropic.com"
                    sys.exit(
                        f"\n✋ Out of API credits for model '{self.cfg.model}' via {endpoint}.\n"
                        "   This is a billing issue on the Claude account behind that endpoint — not a bug.\n"
                        "   Fix one of:\n"
                        "     • Top up the Anthropic account behind the LiteLLM proxy, then re-run.\n"
                        "     • Use a Claude API key that has credit: set ANTHROPIC_API_KEY=... in\n"
                        "       jobagent/engine/.env and remove the LITELLM_* lines (uses api.anthropic.com).\n"
                    )
                raise
            messages.append({"role": "assistant", "content": resp.content})

            # Surface Claude's narration so you can follow along.
            for block in resp.content:
                if block.type == "text" and block.text.strip():
                    print(f"\n🤖 {block.text.strip()}\n")

            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            if not tool_uses:
                print("✅ Claude finished (no further actions).")
                return

            results = []
            for tu in tool_uses:
                action = tu.input.get("action", "")
                if not self._confirm(action, tu.input):
                    results.append(_text_result(tu.id, "User skipped this action. Re-plan.", is_error=True))
                    continue
                try:
                    note = self.actuator.execute(action, tu.input)
                    results.append(self._result_with_screenshot(tu.id, action, tu.input, note))
                except Exception as e:  # noqa: BLE001 — report any actuation failure back to Claude
                    results.append(_text_result(tu.id, f"Error performing {action}: {e}", is_error=True))

            messages.append({"role": "user", "content": results})

        print(f"\n⏹  Hit max_steps ({self.cfg.max_steps}). Stopping. Raise JOBAGENT_MAX_STEPS to allow more.")

    # ---- helpers ----
    def _result_with_screenshot(self, tool_use_id: str, action: str, inp: dict, note: str | None) -> dict:
        if action == "zoom":
            region = inp.get("region") or [0, 0, self.screen.model_w, self.screen.model_h]
            b64 = self.screen.capture_region_b64(*region)
        else:
            b64 = self.screen.capture_b64()
        content = []
        if note:
            content.append({"type": "text", "text": note})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}

    def _confirm(self, action: str, inp: dict) -> bool:
        # Read-only actions (screenshot/zoom/mouse_move/wait) always run; announce in step mode.
        if action not in _ACTUATING:
            if self.cfg.mode == "step":
                print(f"   · {action} {_short(inp)}")
            return True
        is_click = action in _CLICKS
        # Auto-execute only when: auto mode AND (it's not a click, or submit is explicitly allowed).
        # => clicks are always confirmed unless --allow-submit, even in --auto. This is the
        #    code-level interlock that actually keeps a final Submit from firing unattended.
        if self.cfg.mode == "auto" and (self.cfg.allow_submit or not is_click):
            return True
        gate = "CLICK — could be Submit; --allow-submit not set" if (is_click and not self.cfg.allow_submit) else action
        print(f"\n➡️  CONFIRM {gate}: {action} {_short(inp)}")
        ans = input("   [Enter]=do it  s=skip  q=quit > ").strip().lower()
        if ans == "q":
            sys.exit("Stopped by user.")
        return ans != "s"


def _short(inp: dict) -> str:
    keys = ("coordinate", "start_coordinate", "text", "scroll_direction", "scroll_amount", "region", "duration")
    parts = [f"{k}={inp[k]!r}" for k in keys if k in inp]
    return " ".join(parts)


def _text_result(tool_use_id: str, text: str, is_error: bool = False) -> dict:
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": text, "is_error": is_error}
