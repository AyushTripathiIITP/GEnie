# GEnie — AI job-application copilot

An agent that finds matching jobs, scores them, and fills out applications from a single
source of truth about you — so applying becomes review-and-send instead of an afternoon of
copy-paste. Started as a personal tool; the plan to turn it into a real product is in
[GENIE_PRODUCT_PLAN.md](GENIE_PRODUCT_PLAN.md).

Everything reads from the same profile + answer bank, so whichever way you run it, the
answers stay consistent and the answer bank grows over time (new screening questions are
asked once, then saved forever).

## Two ways to run it today

**1. `/apply` skill — Claude Code + the Claude in Chrome extension** (human-in-the-loop)
Drives your real, logged-in Chrome via DOM tools to search LinkedIn, score fit, and pre-fill
Easy Apply / ATS forms. Cheaper and more reliable than computer use. Run it with:
```
/apply
```
(or "apply to jobs"). See [skill/apply/SKILL.md](skill/apply/SKILL.md).

**2. Computer-use engine — standalone Python** (`engine/`)
A self-hosted Claude computer-use loop: screenshot your Mac → ask the Claude API where to
click/type → actuate with `pyautogui` → repeat. Useful when you want a self-contained binary
rather than the Chrome extension. Full docs in [engine/README.md](engine/README.md).
```bash
cd ~/windflow/prsnl
python -m jobagent.engine.run --keywords "AI Engineer" --location "Bengaluru"
```
It opens a pre-filtered LinkedIn Easy Apply search in Chrome, pauses for you to log in if
needed (never types your password), then applies. Confirm-each-action by default; `--auto`
and `--allow-submit` (or the `JOBAGENT_*` keys in `engine/.env`) make it fully autonomous.

## Config & data (shared by both)

| Path | What it is |
|---|---|
| `profile/master_profile.yaml` | Single source of truth about you. Edit this, everything follows. |
| `profile/answer_bank.yaml` | Reusable answers to screening questions; grows automatically. |
| `search_config.yaml` | Target roles, keywords, deal-breakers, fit threshold, pacing. |
| `tracker/applications.csv` | Every application: company, fit score, status, notes. |
| `resume/Ayush_Tripathi_Resume.pdf` | Canonical resume uploaded into forms. |
| `engine/` | The standalone computer-use engine (its own README + `.env`). |
| `GENIE_PRODUCT_PLAN.md` | Roadmap for turning this into the GEnie product. |

## First-time setup

1. Fill the TODOs in `master_profile.yaml → logistics:` (notice period, expected CTC,
   relocation, preferred locations) — forms ask these constantly and the agent won't guess them.
2. For the engine: `pip install -r engine/requirements.txt`, then `cp engine/.env.example
   engine/.env` and add a Claude API key (direct `ANTHROPIC_API_KEY`, or a LiteLLM proxy via
   `LITELLM_*`). Pick the model with `JOBAGENT_MODEL` — `claude-opus-4-8`/`claude-sonnet-4-6`
   for accuracy, `claude-haiku-4-5` for cost. Grant Terminal **Screen Recording** +
   **Accessibility** in System Settings ▸ Privacy.

## Why human-in-the-loop (and why it matters for the product)

LinkedIn prohibits automated submission and detects it well — a restricted account is worse
than slow applications. Keeping a human on the final Send is both the safety posture and the
cost control (you only spend LLM tokens on applications that actually get sent). It's also
GEnie's market wedge: tailored, approved applications that get callbacks — not 200 blasts
that get the account banned. See the plan for the full reasoning.
