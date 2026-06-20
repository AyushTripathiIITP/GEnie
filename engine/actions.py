"""Execute computer-use actions on the real macOS desktop via pyautogui.

Claude emits actions in the schema of the computer tool (action + coordinate/text/...).
This module translates each one into pyautogui calls, operating in LOGICAL points
(Screen.to_logical handles the model->logical conversion before we get here).

Returns, for every action, a fresh screenshot of the resulting screen state so Claude
always sees the consequence of what it just did.
"""
from __future__ import annotations

import subprocess
import time

import pyautogui

from .config import Config
from .screen import Screen

# Move the mouse to a screen corner to abort everything (pyautogui failsafe).
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

# X11 keysym names (what the model tends to emit) -> pyautogui key names.
_KEYMAP = {
    "return": "enter", "enter": "enter", "kp_enter": "enter",
    "escape": "esc", "esc": "esc",
    "backspace": "backspace", "delete": "delete", "tab": "tab",
    "space": "space",
    "page_up": "pageup", "page_down": "pagedown",
    "home": "home", "end": "end",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "ctrl": "ctrl", "control": "ctrl", "control_l": "ctrl", "control_r": "ctrl",
    "alt": "option", "alt_l": "option", "alt_r": "option", "option": "option",
    "shift": "shift", "shift_l": "shift", "shift_r": "shift",
    "super": "command", "super_l": "command", "cmd": "command",
    "meta": "command", "win": "command", "command": "command",
}

# Modifier names usable as the `text` field on click/scroll actions.
_MODIFIERS = {"shift": "shift", "ctrl": "ctrl", "control": "ctrl",
              "alt": "option", "option": "option", "super": "command", "cmd": "command"}


def _key_token(tok: str) -> str:
    t = tok.strip().lower()
    return _KEYMAP.get(t, t)


def _paste_text(text: str) -> None:
    """Type arbitrary (incl. unicode) text via the macOS clipboard, restoring the
    user's previous clipboard afterwards so we don't clobber what they had copied."""
    try:
        prev = subprocess.run(["pbpaste"], capture_output=True).stdout
    except Exception:  # noqa: BLE001 — clipboard read is best-effort
        prev = None
    subprocess.run("pbcopy", input=text.encode("utf-8"), check=True)
    # Wait until the pasteboard actually holds our text before pasting (avoids a race).
    for _ in range(25):
        cur = subprocess.run(["pbpaste"], capture_output=True).stdout.decode("utf-8", "ignore")
        if cur == text:
            break
        time.sleep(0.02)
    pyautogui.hotkey("command", "v")
    time.sleep(0.15)  # let the paste consume the clipboard before we restore it
    if prev is not None:
        subprocess.run("pbcopy", input=prev, check=False)


class Actuator:
    def __init__(self, cfg: Config, screen: Screen):
        self.cfg = cfg
        self.screen = screen

    def execute(self, action: str, inp: dict) -> str | None:
        """Run one action. Returns a short text note, or None. The caller attaches
        the post-action screenshot separately."""
        s = self.screen

        if action in ("screenshot", "wait", "cursor_position"):
            if action == "wait":
                time.sleep(min(float(inp.get("duration", 1)), 5))
            return None

        if action == "zoom":
            return None  # caller renders the cropped region image

        if action == "mouse_move":
            x, y = s.to_logical(*inp["coordinate"])
            pyautogui.moveTo(x, y)
            return None

        if action in ("left_click", "right_click", "middle_click", "double_click", "triple_click"):
            x, y = s.to_logical(*inp["coordinate"])
            mods = _modifiers_from_text(inp.get("text"))
            _with_mods(mods, lambda: _click(action, x, y))
            return None

        if action == "left_click_drag":
            start = inp.get("start_coordinate")
            sx, sy = s.to_logical(*start) if start else pyautogui.position()
            ex, ey = s.to_logical(*inp["coordinate"])
            pyautogui.moveTo(sx, sy)
            pyautogui.dragTo(ex, ey, duration=0.4, button="left")
            return None

        if action == "left_mouse_down":
            if inp.get("coordinate"):
                pyautogui.moveTo(*s.to_logical(*inp["coordinate"]))
            pyautogui.mouseDown()
            return None

        if action == "left_mouse_up":
            if inp.get("coordinate"):
                pyautogui.moveTo(*s.to_logical(*inp["coordinate"]))
            pyautogui.mouseUp()
            return None

        if action == "type":
            _paste_text(inp["text"])
            return None

        if action == "key":
            raw = str(inp["text"])
            if raw.strip() == "":          # a literal space means the spacebar
                pyautogui.press("space")
                return None
            tokens = [_key_token(t) for t in raw.replace(" ", "+").split("+") if t]
            if not tokens:
                return None
            if len(tokens) == 1:
                pyautogui.press(tokens[0])
            else:
                pyautogui.hotkey(*tokens)
            return None

        if action == "hold_key":
            key = _key_token(inp["text"])
            dur = min(float(inp.get("duration", 1)), 5)
            pyautogui.keyDown(key)
            time.sleep(dur)
            pyautogui.keyUp(key)
            return None

        if action == "scroll":
            x, y = s.to_logical(*inp["coordinate"])
            pyautogui.moveTo(x, y)
            amount = int(inp.get("scroll_amount", 3))
            direction = inp.get("scroll_direction", "down")
            mods = _modifiers_from_text(inp.get("text"))
            # On macOS pyautogui scroll units are LINES (fine-grained), not pixels — a few
            # lines per requested "notch". (Anthropic's docs warn large values overshoot.)
            clicks = max(1, amount) * 3
            def _do():
                if direction == "down":
                    pyautogui.scroll(-clicks)
                elif direction == "up":
                    pyautogui.scroll(clicks)
                elif direction == "left":
                    pyautogui.hscroll(-clicks)
                elif direction == "right":
                    pyautogui.hscroll(clicks)
            _with_mods(mods, _do)
            return None

        return f"unhandled action: {action}"


def _click(action: str, x: int, y: int) -> None:
    if action == "left_click":
        pyautogui.click(x, y)
    elif action == "right_click":
        pyautogui.click(x, y, button="right")
    elif action == "middle_click":
        pyautogui.click(x, y, button="middle")
    elif action == "double_click":
        pyautogui.doubleClick(x, y)
    elif action == "triple_click":
        pyautogui.click(x, y, clicks=3, interval=0.08)


def _modifiers_from_text(text) -> list[str]:
    if not text:
        return []
    out = []
    for tok in str(text).replace(" ", "+").split("+"):
        key = tok.strip().lower()
        if key in _MODIFIERS:
            out.append(_MODIFIERS[key])
    return out


def _with_mods(mods: list[str], fn) -> None:
    for m in mods:
        pyautogui.keyDown(m)
    try:
        fn()
    finally:
        for m in reversed(mods):
            pyautogui.keyUp(m)
