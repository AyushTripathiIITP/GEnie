"""CLI entry point.

    python -m jobagent.engine.run --task "Apply to the LinkedIn Easy Apply job currently open in Chrome"

Loads your profile + answer bank so Claude fills forms with real data, builds a system
prompt with the safety rules, then runs the computer-use loop on your real Mac.
"""
from __future__ import annotations

import argparse
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]  # .../jobagent


def _load_dotenv() -> None:
    """Minimal .env loader (KEY=VALUE lines) — avoids a python-dotenv dependency.
    Must run before Config() reads os.environ."""
    env = pathlib.Path(__file__).resolve().parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

from .agent import ComputerAgent  # noqa: E402 — import after .env is loaded
from .config import Config  # noqa: E402


def _read(p: pathlib.Path) -> str:
    try:
        return p.read_text()
    except FileNotFoundError:
        return "(not found)"


def build_system_prompt(allow_submit: bool) -> str:
    profile = _read(ROOT / "profile" / "master_profile.yaml")
    answers = _read(ROOT / "profile" / "answer_bank.yaml")
    submit_rule = (
        "When you reach the final Submit/Apply button you MAY click it to submit the application."
        if allow_submit else
        "When you reach the final Submit/Apply button, STOP. Do NOT click it. Announce that the "
        "form is ready for review and end your turn so the human can submit."
    )
    return f"""You are Ayush's job-application copilot, operating his actual Mac through the computer tool.
You can see the screen via screenshots and control the mouse and keyboard.

Your job: find and fill job applications (LinkedIn Easy Apply first, plus external ATS forms),
using ONLY the facts below. Never invent experience, credentials, or numbers.

After EACH action, take a screenshot and verify the result before the next step. State your
reasoning briefly ("I have evaluated step X..."). If a UI element is hard to click, prefer
keyboard navigation (Tab/Enter). For small or unreadable text, use the zoom action.

For screening questions: match an answer from the answer bank first, otherwise derive a
reasonable answer from the profile facts. For free-text questions, write 2-4 first-person
sentences grounded in the profile, tailored to the specific job. Never answer salary/CTC
unless a value exists in the profile.

SAFETY: {submit_rule}
Never accept terms, change account settings, or take destructive actions without it being an
explicit, necessary step of filling THIS application.

==== MASTER PROFILE ====
{profile}

==== ANSWER BANK ====
{answers}
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Self-hosted computer-use engine for job applications.")
    ap.add_argument("--task", default=(
        "In Google Chrome, work on the LinkedIn job that is currently open. If an Easy Apply "
        "button is visible, start the application and fill every field from my profile. Advance "
        "through each step of the form."
    ))
    ap.add_argument("--auto", action="store_true", help="Run unattended (no per-action confirmation).")
    ap.add_argument("--allow-submit", action="store_true", help="Permit clicking the final Submit button.")
    ap.add_argument("--max-steps", type=int, default=None)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    cfg = Config()
    if args.auto:
        cfg.mode = "auto"
    if args.max_steps is not None:
        cfg.max_steps = args.max_steps
    if args.model:
        cfg.model = args.model

    print(f"Model: {cfg.model}  |  tool: {cfg.tool_type}  |  mode: {cfg.mode}  |  "
          f"image: {cfg.effective_long_edge}px long edge  |  submit: {'ALLOWED' if args.allow_submit else 'blocked'}")
    print("Tip: slam the mouse into a screen corner at any time to abort (pyautogui failsafe).\n")

    agent = ComputerAgent(cfg, build_system_prompt(args.allow_submit))
    agent.run(args.task)


if __name__ == "__main__":
    main()
