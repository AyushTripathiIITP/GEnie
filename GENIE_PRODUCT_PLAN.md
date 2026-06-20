# GEnie — Phased Build Plan

## 1. The honest framing

The hard truths first: there is **no legal, sanctioned way to auto-apply on LinkedIn** — no public API, and auto-submitting violates the User Agreement (the exact contract+trespass theory LinkedIn won on in hiQ for $500K + an injunction that killed the company). The market is crowded and most incumbents are actively distrusted (AIApply BBB "F", JobCopilot billing complaints, Sonara's mid-search shutdown, LoopCV 1.0/5). And the technical core of the current repo — a local pyautogui + Opus computer-use loop — is slow, expensive (~$7.85/run), macOS-only, and doesn't scale to many users. **The wedge that survives all of this:** every incumbent either sprays untailored volume (1-2% callback, gets accounts banned) or does dumb autofill (Simplify) or uses slow humans (Scale.jobs, 25-47% callback). Nobody ships *agent-speed, genuinely-tailored, human-approved* applications that run in the user's own browser and never get them flagged. That's the gap, and it's exactly the posture this codebase was already built around.

## 2. Recommended architecture — pick: Browser Extension (Option A)

**Ship GEnie as a Chrome MV3 extension that runs in the user's own already-logged-in LinkedIn tab, backed by a thin cloud control plane.** This is the only option that is simultaneously low-ban-risk, cheap, and fast to ship. Execution happens on the user's real IP, real fingerprint, real session — none of the datacenter-IP/headless/replayed-cookie signals LinkedIn keys on fire — and we never touch a password. We replace the per-action Opus vision loop with cheap DOM selectors + a single text-LLM call per form (10-50x cheaper). We reject the cloud-Playwright SaaS (Option B) outright: it forces credential/session storage and datacenter egress — a product-existential ban risk plus a nine-figure PII honeypot. Crucially, **Option A is the local-executor slice of the eventual hybrid (Option D)**, so the cloud control plane we build for billing/sync/scoring is reused unchanged when we scale — we're not throwing work away.

## 3. The product in one line

> **GEnie applies for you, but never spams: every application is tailored, ATS-scored, and approved by you before it's sent — quality applications that get callbacks, not 500 blasts that get your account banned.**

**Target user:** Early-career / new-grad tech job seekers (SWE, data/ML, analyst, PM) applying to 50-300 roles, getting auto-rejected by ATS and afraid of LinkedIn bans. **Sharpest beachhead:** India tier-1/tier-2 grads and 0-3 YOE engineers targeting both Indian and remote/global roles, plus international students on visa clocks who literally cannot afford a burned application.

## 4. MVP scope

**v1 ships:**
- **Onboarding + resume parse** — upload PDF/DOCX, LLM extracts into the proven `master_profile` schema; user reviews/edits before continuing.
- **Profile + auto-growing Answer Bank** — key-value store for recurring screening Qs; new question asked once, saved forever, user-scoped. Hard rule: never inflate YOE, never fabricate, salary only when an explicit value exists.
- **Search/targeting config** — target_roles, seniority, keyword boosts, deal-breakers, locations, fit thresholds.
- **In-browser job discovery** — content script reads the JD from the page the user already sees; dedupes against tracker. No server-side scraping.
- **LLM fit scoring (0-10)** — role-family gate, +1/keyword, deal-breaker = auto-skip; returns score + one-line rationale; tags apply/maybe/skip.
- **Autofill** — maps fields to profile/answer-bank on LinkedIn Easy Apply + Greenhouse/Lever/Ashby; LLM drafts 2-4 sentence free-text answers grounded only in profile facts.
- **Human-review-before-submit (core invariant)** — fills the form, **stops at the final review step, never clicks Submit.** Flags uncertain fields.
- **Application tracker** — date/company/title/location/platform/url/fit_score/status/notes; dashboard + CSV export.
- **Pacing guardrails** — per-session/per-day caps, duplicate detection.
- **Web dashboard + auth** — manage profile/bank/config, view tracker, download extension.

**v1 deliberately does NOT:**
- Auto-submit / one-click "apply to 200 jobs" (ban + legal + trust).
- Server-side / headless scraping, proxy rotation, Playwright farm.
- Boards beyond LinkedIn + Greenhouse/Lever/Ashby (Workday/Taleo/iCIMS/Naukri/Indeed deferred — Workday mapping alone is a project).
- Per-job resume tailoring/generation, cover letters, multiple resume variants (single canonical resume in v1).
- Teams/multi-seat, mobile/Safari/Firefox, email/calendar integration, callback-rate analytics.
- The native pyautogui computer-use engine (later fallback for non-DOM flows only).

## 5. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Dashboard | Next.js (App Router) + React + TS + Tailwind + shadcn/ui | One TS codebase, fast to build |
| Browser piece | Chrome MV3 extension (TS, Vite + CRXJS), content script + side panel | Anti-ban: runs in user's real session |
| Backend | Next.js route handlers (serverless); FastAPI only if heavier LLM orchestration is needed later | Single-language, ship fast |
| DB | Postgres via Supabase (+ Row Level Security) | Collapses db+auth+storage; per-user isolation is config not code |
| Auth | Supabase Auth (magic-link + Google OAuth), JWT shared by dashboard + extension | No custom auth to maintain |
| Browser automation | MV3 content scripts (DOM detect/fill/scrape) — no headless, no Playwright, no stored credentials | The deliberate anti-ban architecture |
| LLM | Anthropic Claude — Opus for parse/final tailoring, Haiku/Sonnet for high-volume scoring; tool-use JSON schema; via existing LiteLLM proxy | Tiered model = cost control |
| Storage | Supabase Storage for canonical resume | One service |
| Queue | None in v1 (synchronous, human-paced); QStash/Postgres-backed later | No premature Celery/Redis |
| Hosting | Vercel (dashboard+API) + Supabase cloud + Chrome Web Store | No infra to run |
| Payments | Stripe (Checkout + Portal), wired only at paid launch; carry `stripe_customer_id` from day 1 | Don't let billing slow first ship |

## 6. Migration: reuse vs rewrite

**Reuse (the durable IP — all platform-agnostic):**
- `jobagent/profile/master_profile.yaml` + `answer_bank.yaml` — the data model; maps ~1:1 onto DB tables. "Ask once, append forever" becomes a scoped upsert.
- `jobagent/search_config.yaml` — fit-scoring algo (role gate, +1/keyword, threshold buckets), deal-breakers, pacing caps → per-user editable settings.
- `jobagent/engine/run.py` `build_system_prompt` (lines 66-113) — prompt skeleton kept verbatim (role framing, START-OF-SESSION steps, **credential-wall STOP rule**, conditional submit_rule); only the data source changes from YAML files to DB rows.
- `jobagent/engine/run.py` `open_linkedin_jobs` (lines 20-36) — LinkedIn search-URL builder (Easy Apply `f_AL=true`, recency `f_TPR`, the learned "no `f_E` filter" rule). Drop the `open -a Chrome` subprocess; keep URL logic.
- `jobagent/engine/agent.py` submit interlock (`_ACTUATING`/`_CLICKS` sets lines 18-27, `_confirm` lines 130-147) + `config.py` `allow_submit` (80-82) — becomes a server-side per-tenant policy flag; the gate logic is the human-in-the-loop guarantee.
- `jobagent/skill/apply/SKILL.md` — already written against Chrome DOM tooling (`form_input`, `file_upload`, `get_page_text`); this is the orchestration playbook and proof the DOM path works. Better foundation than the computer-use loop.
- `jobagent/tracker/applications.csv` schema + dedupe-by-url rule → applications table, columns/status enum as-is.

**Rewrite (single-user/local assumptions that can't survive multi-tenancy):**
- `jobagent/engine/actions.py` — pyautogui/mss/pbcopy clicks on the operator's physical Mac → DOM operations (fill/click/upload) in the extension. Retire the clipboard hack, corner-slam failsafe, Retina math.
- `jobagent/engine/screen.py` — local-screenshot + coordinate scaling → gone on the DOM path (keep only as a pattern if a visual fallback is ever needed).
- `run.py` `_load_dotenv` + single `ANTHROPIC_API_KEY`/`os.environ` config → auth layer + per-tenant settings rows + a **platform-owned** LLM key with per-tenant usage metering.
- Hardcoded local file paths + the one Ayush profile → multi-tenant tables keyed by `user_id` + object storage per resume.
- CLI argparse + `input()` confirm prompts → web/extension UI; the blocking `input()` submit gate becomes an async approve/skip/discard event over the network.

## 7. Phased roadmap

**Phase 0 — This week (extract + de-risk the vertical slice):**
- Lock the DOM/extension architecture decision in writing; demote pyautogui to optional fallback.
- Refactor `engine/agent.py` loop into transport-agnostic `run_session(model_client, actuator, policy)` — keep the pyautogui actuator behind the interface so nothing breaks.
- Design multi-tenant schema (users, profiles, answer_bank, search_configs, applications); write a one-tenant migration that loads Ayush's existing YAML/CSV as the first seeded user (real fixture, proves round-trip).
- Rewrite `build_system_prompt` to interpolate from a tenant record, not files. Stand up auth + secrets skeleton, move the LLM key to a platform key.
- Build a thin DOM actuator; run **one real LinkedIn Easy-Apply session end-to-end for the seeded user, stopping at the submit gate.** Replace `input()` with an async approval event + a stub web review screen.

**Phase 1 — MVP (~4-6 wks):** Ship every bullet in §4. Private beta via unpacked extension. Deliverable: a stranger uploads a resume → discovers/scores/autofills → reviews → submits manually → sees it in the tracker. Target metric instrumented from day 1: **fully-loaded cost per *approved* application.**

**Phase 2 — Monetize (~wks 6-12):** Chrome Web Store listing. Wire Stripe (Free/Pro/Pro+). Add per-job resume + cover-letter tailoring (Pro), recruiter/referral-outreach drafts (Pro+), follow-up nudges. Build the callback-rate dashboard (the "sell outcomes not effort" differentiator). Add Naukri/Wellfound for the India beachhead.

**Phase 3 — Scale (post-PMF):** Lift the cloud control plane fully out (this is Option D — the extension is already its local executor). Central selector map (fix LinkedIn DOM breaks once for all users), global pacing policy, batch scoring queue (QStash). Conquer the hard surfaces — Workday, multi-page/login-gated, government/enterprise — where everyone breaks; make it the headline. Add H1B/visa eligibility filtering, mobile review-and-approve, Firefox port.

## 8. Pricing + unit-economics reality

| Tier | Price | Includes |
|---|---|---|
| **Free** | $0 | 10 tailored, human-approved apps/mo; ATS fit-score + keyword match; 1 base resume. All-Haiku. Acquisition + proof. |
| **Pro** | $19/mo ($144/yr) · India ₹599/mo (₹4,999/yr) | ~60 apps/mo (soft daily cap), per-job resume + cover-letter tailoring, full ATS opt, multi-platform, tracker + nudges. |
| **Pro+** | $39/mo ($290/yr) · India ₹1,499/mo | ~150 apps/mo, Opus tailoring every app, recruiter/referral drafts, interview prep, callback-rate "quality guarantee." |

**The brutal math:** the current Opus loop is ~$7.85/run. A $19 Pro user doing 60 apps at pure Opus = **~$471 in compute — wildly underwater.** Pure-Opus-per-app is non-viable at consumer prices. **The fix is non-negotiable:** a tiered pipeline — Haiku for parse/dedup/first-draft/form-fill (~$1.57/run), Opus reserved *only* for the final tailoring pass on apps the user actually approves. The human-in-the-loop gate is **the cost control as much as the anti-spam moat**: it caps real spend to applications that get sent, so most Free-tier compute is never spent. Pro only works if **blended cost ≤ $0.20-0.30 per app** (aggressive Haiku + prompt-caching the profile/resume + batching). Pro+ is where Opus-heavy tailoring is affordable. **Headline metric to drive down before scaling paid acquisition: fully-loaded cost per *approved* application — not cost per run.**

## 9. Legal/safety guardrails (day 1)

- **Mandatory human-in-the-loop on every submit.** Product pre-fills and drafts; the human clicks Send. This is the single biggest risk reducer — it's the only posture LinkedIn has *not* enforced against, and it defeats the "human-impossible velocity" ban trigger.
- **Client-side only, in the user's own logged-in browser.** Never log in on our servers. **Never store LinkedIn passwords or exfiltrate session tokens — ever.**
- **Throttle to human-plausible rates; cap volume hard.** Nowhere near 100/hr. Refuse unattended bulk runs.
- **Minimize automation artifacts.** No fingerprint-spoofing, residential proxies, or CAPTCHA-solvers — deploying evasion tooling is read by courts as deliberate bad faith.
- **Quality-gated, not volume-gated.** Score fit, refuse low-fit applications; never inflate YOE or fabricate; salary only when a value exists.
- **PII compliance up front.** Treat resumes as regulated PII: explicit granular revocable consent, one-click delete/export, encryption at rest, sub-processor inventory + DPAs. Ayush is India-based → align to **DPDP 2023/Rules 2025** (free/specific/informed consent, easy withdrawal, breach reporting, retention) *and* GDPR/CCPA for EU/CA users — **before launch.**
- **Disclose the legal reality plainly.** Tell users automating LinkedIn may breach its UA and risk their account, they run it on their own session, they retain final click authority. Market "you-approve-every-send," never "auto-apply to 200 jobs."
- **Kill switches.** Detect LinkedIn challenge/CAPTCHA/restriction states → halt for that user, never solve/evade. Treat any LinkedIn friction as a stop signal. Log consent + actions.

## 10. Top 3 risks + the one thing that kills it

1. **Selector brittleness.** LinkedIn DOM changes break autofill on every UI revision. Mitigation: a centralized selector map (Phase 3) so you fix once for all users; graceful "flag for manual entry" on any unmatched field.
2. **Unit economics underwater.** If blended cost can't get to ≤$0.20-0.30/approved-app, Pro is a money-loser. Mitigation: ruthless Haiku tiering + prompt-caching + the human gate as a spend cap; instrument cost-per-approved-app from day 1.
3. **Trust/distribution in a scammy category.** Buyers are burned and skeptical. Mitigation: transparent flat pricing, no dark patterns, easy cancel/export, and founder build-in-public posting *callback-rate proof* — win on trust, which no incumbent can claim.

**The single biggest thing that could kill it:** LinkedIn classifying the extension itself as "prohibited software" and detecting it via **DOM-injection artifacts** — flagging or banning users *even at human velocity and even with a human clicking Submit.* The whole product rests on "human-in-the-loop autofill has never been enforced against," but extensions are independently fingerprintable. If LinkedIn decides to nuke assistive extensions wholesale (as it has the legal right and growing incentive to do amid the AI-application flood), the core surface evaporates. The hedge: minimize injection footprint, lead with the ATS boards (Greenhouse/Lever/Ashby) where terms are friendlier, and keep LinkedIn as human-in-the-loop *assist* rather than the sole channel — so a LinkedIn crackdown wounds but doesn't kill.