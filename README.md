# jobagent — human-in-the-loop job application copilot

Claude Code + the Claude in Chrome extension drive your real, logged-in browser to find
and pre-fill job applications. You review and click Submit. Nothing applies on its own.

## Run a session

```
/apply
```

(or just say "apply to jobs"). Default: LinkedIn Easy Apply, Data/ML/AI roles, up to 15
applications per session, 2 sessions/day.

## Files

| File | What it is |
|---|---|
| `profile/master_profile.yaml` | Single source of truth about you. Edit this, everything follows. |
| `profile/answer_bank.yaml` | Reusable answers to screening questions. Grows automatically — new questions get asked once, saved forever. |
| `search_config.yaml` | Target roles, keywords, deal-breakers, fit threshold, pacing. |
| `tracker/applications.csv` | Every application: company, fit score, status. |
| `resume/Ayush_Tripathi_Resume.pdf` | Canonical resume uploaded into forms. |

## Before your first session — fill in the TODOs

`master_profile.yaml → logistics:` notice period, expected CTC, relocation, preferred
locations. Forms ask these constantly; the agent will refuse to guess them.

## Why human-in-the-loop

LinkedIn/Wellfound ban automated submission and detect it well — a restricted account is
worse than slow applications. With prefill, your cost per application drops to a
~10-second review, and quality stays high enough to actually get callbacks.
