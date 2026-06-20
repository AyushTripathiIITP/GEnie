# Computer-use engine

A self-hosted version of the Claude browser-extension loop. Instead of an MCP, **your own
Python program** drives your real Mac: it screenshots the screen, sends the image to the
Claude API with the computer-use tool, Claude replies with where to move the cursor / what
to click / what to type, and the engine actuates it with `pyautogui`. Then it screenshots
again and repeats — the "agent loop."

```
 ┌─────────┐  screenshot   ┌───────────────┐  action (click/type/…)  ┌──────────┐
 │  your   │ ────────────▶ │  Claude API   │ ──────────────────────▶ │ pyautogui│
 │  Mac    │ ◀──────────── │ (computer     │                         │ executes │
 │ screen  │  next frame   │  tool)        │ ◀──── tool_result ───── │ on screen│
 └─────────┘               └───────────────┘   (new screenshot)      └──────────┘
```

## How it maps to what you asked for
1. It hits the screen where LinkedIn is open (in Chrome).
2. It screenshots, and asks the Claude API where to move the cursor and which button to hit.
3. It moves the cursor and clicks/types — then loops.

## Setup (one time)
```bash
cd ~/windflow/prsnl
python3 -m venv .venv && source .venv/bin/activate      # or reuse the existing venv
pip install -r jobagent/engine/requirements.txt
cp jobagent/engine/.env.example jobagent/engine/.env     # then paste your ANTHROPIC_API_KEY
```

**macOS permissions** — the first run will prompt for these; grant them in
System Settings ▸ Privacy & Security:
- **Screen Recording** (so it can screenshot) — for your terminal app (Terminal/iTerm).
- **Accessibility** (so it can move the mouse / type) — same app.

## Run
Open Chrome on a LinkedIn job, then:
```bash
cd ~/windflow/prsnl
python -m jobagent.engine.run --task "Apply to the LinkedIn job open in Chrome"
```

### Modes
- **Default (`step`)** — pauses before every click/type/key and asks you to confirm. Safe.
- **`--auto`** — runs unattended up to `--max-steps`. Faster, but it acts without asking.
- **`--allow-submit`** — permits clicking the final Submit/Apply. **Omitted by default**: the
  engine fills the form and stops at the submit button for you to review and click. This is
  the safe default for LinkedIn (auto-submitting violates their ToS and risks your account).

Abort anytime by **slamming the mouse into a screen corner** (pyautogui failsafe), or Ctrl-C.

## Key facts (so you can tune it)
- Model: `claude-opus-4-8` (computer-use capable). **Not** `claude-fable-5` — Fable 5 isn't on
  the computer-use supported list and the API will reject the tool.
- Tool: `computer_20251124`, beta header `computer-use-2025-11-24`.
- Retina scaling is handled in `screen.py`: it captures physical pixels, downscales to a
  model image (`--long edge` ≤ 2576 on Opus 4.8), and maps Claude's coordinates back to the
  logical points `pyautogui` clicks in. Single primary display assumed.

## Files
| File | Role |
|---|---|
| `config.py` | Model, beta header, tool version, scaling + safety knobs (env-overridable) |
| `screen.py` | Retina-aware capture + the three-coordinate-space scaling |
| `actions.py` | Translates Claude's actions into `pyautogui` calls (clicks, keys, type-via-clipboard, scroll, zoom) |
| `agent.py` | The Claude API loop + the per-action confirmation gate |
| `run.py` | CLI; loads your profile/answer bank into the system prompt |

## Honest caveats
- LinkedIn prohibits automation and detects it. Running this against LinkedIn — especially
  with `--auto --allow-submit` — risks account restriction. The safe path is `step` mode with
  submit blocked, so you stay the one clicking Submit.
- Computer use is slower and pricier per application than the DOM-based `/apply` skill. This
  engine exists because you wanted to build the screenshot-driven loop yourself; for day-to-day
  volume the `/apply` skill (Chrome MCP) is cheaper and more reliable.
