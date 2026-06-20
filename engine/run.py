"""CLI entry point.

    python -m jobagent.engine.run --task "Apply to the LinkedIn Easy Apply job currently open in Chrome"

Loads your profile + answer bank so Claude fills forms with real data, builds a system
prompt with the safety rules, then runs the computer-use loop on your real Mac.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]  # .../jobagent


def open_linkedin_jobs(keywords: str, location: str) -> str:
    """Open a pre-filtered LinkedIn Easy Apply jobs search in Chrome, deterministically,
    so the agent starts on a relevant jobs page instead of having to open Chrome + type a
    URL itself (which is slow and error-prone via computer use). If not logged in, LinkedIn
    redirects to the login wall and the agent will pause and ask the human to log in."""
    params = urllib.parse.urlencode({
        "keywords": keywords,
        "location": location,
        "f_AL": "true",        # Easy Apply only
        "f_TPR": "r86400",     # posted in the last 24h
    })
    url = f"https://www.linkedin.com/jobs/search/?{params}"
    try:
        subprocess.run(["open", "-a", "Google Chrome", url], check=True)
    except Exception:  # noqa: BLE001 — fall back to the default browser
        subprocess.run(["open", url], check=False)
    return url


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
    search = _read(ROOT / "search_config.yaml")
    submit_rule = (
        "When you reach the final Submit/Apply button you MAY click it to submit the application."
        if allow_submit else
        "When you reach the final Submit/Apply button, STOP. Do NOT click it. Announce that the "
        "form is ready for review and end your turn so the human can submit."
    )
    return f"""You are Ayush's job-application copilot, operating his actual Mac through the computer tool.
You can see the screen via screenshots and control the mouse and keyboard.

Your job: find and fill job applications (LinkedIn Easy Apply first, plus external ATS forms),
using ONLY the facts below.

START OF SESSION — do these steps first, in order:
1. Take a screenshot. A LinkedIn Easy Apply jobs search has ALREADY been opened in Google Chrome
   for you, with the search keywords and Easy Apply filter already applied. Bring Chrome to the
   front if it isn't focused and confirm the LinkedIn page loaded. (Only if no linkedin.com page
   is open at all: click Chrome's address bar, type https://www.linkedin.com/jobs/ and press Enter.)
2. Decide whether Ayush is logged in:
   - If you see a sign-in / login / "Join now" wall, or he is NOT logged in: STOP. Do NOT type any
     email, phone, or password yourself. Tell Ayush: "Please log in to LinkedIn in Chrome, then
     tell me to continue (or re-run me)." End your turn and wait. Never enter credentials.
   - If he IS logged in (you see job listings / his feed / profile): continue.
3. On the LinkedIn Jobs results, open the first job that matches the SEARCH CONFIG targets, start
   the Easy Apply application, and fill every field from the profile and answer bank. After each
   application, go back to the results and move to the next matching job.

After EACH action, take a screenshot and verify the result before the next step. State your
reasoning briefly ("I have evaluated step X..."). If a UI element is hard to click, prefer
keyboard navigation (Tab/Enter). For small or unreadable text, use the zoom action.

For screening questions: match an answer from the answer bank first, otherwise derive a
reasonable answer from the profile facts. For free-text questions, write 2-4 first-person
sentences grounded in the profile, tailored to the specific job. Never answer salary/CTC
unless a value exists in the profile. {submit_rule}

==== SEARCH CONFIG (what roles/locations to search for) ====
{search}

==== MASTER PROFILE ====
{profile}

==== ANSWER BANK ====
{answers}
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Self-hosted computer-use engine for job applications.")
    ap.add_argument("--task", default=(
        "Start a LinkedIn job-application session. Follow the START OF SESSION steps: open "
        "linkedin.com if it isn't already open, make sure I'm logged in (ask me to log in if not), "
        "then find and apply to relevant Easy Apply jobs that match my profile."
    ))
    ap.add_argument("--auto", action="store_true", help="Run unattended (no per-action confirmation).")
    ap.add_argument("--allow-submit", action="store_true", help="Permit clicking the final Submit button.")
    ap.add_argument("--max-steps", type=int, default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--keywords", default="AI Engineer", help="LinkedIn jobs search keywords.")
    ap.add_argument("--location", default="India", help="LinkedIn jobs search location.")
    ap.add_argument("--no-open", action="store_true", help="Don't auto-open LinkedIn (assume a tab is already open).")
    args = ap.parse_args()

    cfg = Config()
    if args.auto:
        cfg.mode = "auto"
    if args.allow_submit:
        cfg.allow_submit = True
    if args.max_steps is not None:
        cfg.max_steps = args.max_steps
    if args.model:
        cfg.model = args.model

    print(f"Model: {cfg.model}  |  tool: {cfg.tool_type}  |  mode: {cfg.mode}  |  "
          f"image: {cfg.effective_long_edge}px long edge  |  submit: {'ALLOWED' if cfg.allow_submit else 'blocked'}")
    print(f"Endpoint: {cfg.base_url or 'https://api.anthropic.com'}")
    print("Tip: slam the mouse into a screen corner at any time to abort (pyautogui failsafe).\n")

    # Deterministically open LinkedIn (pre-filtered Easy Apply search) in Chrome so the agent
    # reliably starts on a relevant jobs page. Skip with --no-open.
    if not args.no_open:
        url = open_linkedin_jobs(args.keywords, args.location)
        print(f"Opened LinkedIn Jobs in Chrome: {url}")
        time.sleep(4)  # let the page (or login wall) finish loading before the first screenshot

    # cfg.allow_submit merges --allow-submit AND JOBAGENT_ALLOW_SUBMIT (.env), so the startup
    # line, system prompt, and click-gate never disagree.
    agent = ComputerAgent(cfg, build_system_prompt(cfg.allow_submit))
    agent.run(args.task)


if __name__ == "__main__":
    main()
