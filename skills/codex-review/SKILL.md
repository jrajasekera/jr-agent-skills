---
name: codex-review
description: Review non-trivial design docs or implementation plans with Codex before coding; validate feedback; fix critical plan issues; ask about non-critical choices. Also triggers when the user says "use codex-review", "ask Codex", or "get Codex feedback".
when_to_use: Use after creating or updating a design doc, implementation plan, architecture/refactor/migration/rollout plan, or when the user says "use codex-review", "ask Codex", or "get Codex feedback". Auto-run for non-trivial plans; ask first for trivial single-file or docs-only changes. Do not use if the user says to skip review.
---

# Codex Review

## Principle

Use Codex as an independent reviewer, not as an authority. Claude owns the plan, verifies every finding against the repository and user requirements, then decides what to change.

## Trigger Rules

Run automatically after drafting or materially changing a plan for:

- Multi-file implementation work.
- New features, refactors, migrations, rollouts, or architecture decisions.
- Security, auth, permissions, payments, billing, schemas, data handling, concurrency, performance-sensitive code, or dependency changes.
- Any task where a flawed plan could waste significant implementation time.

Ask before running for trivial work:

- Typos, small copy edits, simple config changes, docs-only edits, or a tiny single-file helper with no API/data-flow impact.

Never run if the user says to skip Codex review or proceed without additional review.

## Before Invoking Codex

1. Ensure the plan exists as a file. If it only exists in chat, write or update the plan file first.
2. Ensure the plan has concrete repository details: file paths, modules, functions, commands, tests, migration steps, constraints, and non-goals.
3. Determine:
   - `PROJECT_ROOT`: absolute path to the repository or project root.
   - `PLAN_PATH`: absolute path to the plan file. Its contents are inlined into the prompt (see below), so an absolute path keeps `cat` working regardless of the current directory.
4. Remove secrets, tokens, credentials, private keys, and unrelated user data from the prompt.
5. If the plan is vague, improve it before asking Codex to review it.

## Where Codex Review Is Most (and Least) Useful

Codex is strongest at checking a plan against concrete code: whether file paths, frameworks, APIs, and patterns actually exist; missing or incompatible dependencies; architectural mismatches; and references to non-existent routes, models, or functions.

Codex adds little value — and may return shallow feedback — when the plan references external systems it cannot access (third-party APIs, databases, services), is highly abstract with few concrete code references, or targets a greenfield project with no existing code to compare against. If feedback comes back shallow, add concrete file paths, symbols, or snippets to the plan and re-run rather than trusting a thin review.

## Select Model and Effort

Do not use the Codex defaults. Pick a review tier for every run by scoring the plan on two independent axes, then map to a model and reasoning effort.

**Complexity** — how hard the plan is to reason about:

| Level | Signals |
|---|---|
| Low | One file or one small module, one obvious approach, no new dependencies, no cross-cutting behavior. |
| Moderate | A few files inside one subsystem, some genuinely new logic or a new dependency, but follows established repo patterns. |
| Substantial | Several files crossing a subsystem boundary, a new component or interface other code will depend on, or logic with enough branching or state that correctness is not obvious by inspection. |
| High | Many files or several subsystems, new abstractions or architecture, concurrency/async, schema or data migration, multi-step rollout. |
| Extra-high | Cross-cutting redesign, distributed or stateful coordination, large migration with backfill, novel algorithm, or correctness that cannot be checked locally. |
| Extreme | Several extra-high signals at once, a design with no established pattern to copy in this repo or its ecosystem, or failure modes that cannot be enumerated up front. |

**Impact** — what happens if the plan is wrong:

| Level | Signals |
|---|---|
| Minor | Caught immediately, trivially reversible, confined to local dev, docs, or tooling. |
| Moderate | Costs rework or a broken feature branch; user-visible bug on a non-critical path; reversible with a normal fix. |
| Significant | Breaks a feature real users depend on, or forces a coordinated revert; recoverable within a normal release cycle but visible outside the team. |
| Severe | Production breakage, degraded experience for real users, hard-to-reverse interface or schema change, or significant wasted implementation time. |
| Critical | Data loss or corruption, security/auth/privacy/payments exposure, irreversible migration, outage, or money and compliance consequences. |
| Catastrophic | Unrecoverable data destruction, a breach exposing user data or secrets, or a failure whose blast radius reaches past this system to customers, partners, or regulators. |

**Tier mapping:**

| Tier | Complexity / Impact | Model | Effort |
|---|---|---|---|
| 1 | Low / Minor | `gpt-5.6-terra` | `medium` |
| 2 | Moderate / Moderate | `gpt-5.6-sol` | `low` |
| 3 | Substantial / Significant | `gpt-5.6-sol` | `medium` |
| 4 | High / Severe | `gpt-6-astra` | `low` |
| 5 | Extra-high / Critical | `gpt-6-astra` | `medium` |
| 6 | Extreme / Catastrophic | `gpt-6-astra` | `high` |

**Resolving the gray areas.** The two axes rarely land on the same level, and plans rarely sit cleanly inside one description. Apply these rules in order:

1. Score the axes independently, then take the **higher** of the two tiers. A simple change to a payments path is a high-impact review, not a low-complexity one.
2. When a plan sits between two levels on an axis, **round up**. The cost of one tier too high is a slower review; the cost of one tier too low is a missed critical flaw.
3. Impact overrides complexity at the top: **critical impact is always at least tier 5, and catastrophic impact is always tier 6**, no matter how small the diff looks.
4. Anything touching auth, permissions, payments, billing, PII, secrets, data migrations, or destructive/bulk deletion is **at least tier 3**.
5. Multi-file or multi-subsystem work is **at least tier 2** — never send it to tier 1.
6. Tier 1 is reserved for plans that were borderline worth reviewing at all (a trivial single-file change the user asked to review anyway). If you would have auto-run the review under the trigger rules, it is tier 2 or above.
7. If the plan cannot be scored confidently — vague, unfamiliar subsystem, unclear blast radius — that uncertainty *is* risk. Use tier 3.
8. An explicit user request for a specific model or effort wins over this whole section.

The floors in rules 4-7 are minimums, not ceilings. Score the axes first; a plan that scores higher than its floor uses the higher tier.

State the chosen tier and the one-line reason before invoking, e.g. `Tier 5 (astra/medium): auth session schema change across 6 files.`

## Invoke Codex

Use the Bash tool with these settings:

- `timeout: 1200000`
- Foreground only: no `&`, `nohup`, `disown`, background subshells, or background task runners.
- Capture stdout directly; do not write Codex feedback to a file.
- Suppress stderr progress noise unless debugging a failure.

Run this from any directory; `-C` sets the Codex workspace root. `--sandbox read-only` keeps Codex read-only, so no approval flag is needed in `exec` mode. (If you ever need one, `-a`/`--ask-for-approval` is a top-level flag that must precede the `exec` subcommand: `codex -a never exec …`.)

Inline the plan's contents into the prompt via `$(cat "$PLAN_PATH")` — never ask Codex to open the plan by path itself, since it may silently read the wrong file and review the wrong content.

Pass the tier explicitly with `-m` and `-c model_reasoning_effort=…`. Both flags are required on every run so the review never silently inherits whatever is in `~/.codex/config.toml`.

```bash
PROJECT_ROOT="/absolute/path/to/project/root"
PLAN_PATH="/absolute/path/to/plan.md"

# From the tier table above. Never omit these two.
CODEX_MODEL="gpt-6-astra"     # gpt-5.6-terra (t1) | gpt-5.6-sol (t2-3) | gpt-6-astra (t4-6)
CODEX_EFFORT="medium"         # medium (t1) | low (t2) | medium (t3) | low (t4) | medium (t5) | high (t6)

cat <<CODEX_REVIEW_PROMPT | codex exec -C "$PROJECT_ROOT" \
  -m "$CODEX_MODEL" \
  -c model_reasoning_effort="$CODEX_EFFORT" \
  --sandbox read-only \
  --skip-git-repo-check \
  --ephemeral \
  - 2>/dev/null
You are reviewing an implementation plan for correctness, feasibility, and fit with the existing codebase.

Project root: $PROJECT_ROOT

Review tasks:
1. Read the plan provided at the end of this prompt (between the PLAN START / PLAN END markers).
2. Inspect the repository as needed.
3. Verify that the plan matches actual files, frameworks, APIs, naming, tests, and project conventions.
4. Find missing steps, incorrect assumptions, security risks, migration risks, rollout risks, test gaps, and references to non-existent code.
5. Do not modify files.
6. Do not ask follow-up questions.
7. Output only the final review in the format below.

Format:
## Critical
- [C1] Title — Issue, impact, evidence from the repo, and concrete fix. Use file paths or symbols when possible.

## Important
- [I1] Title — Issue, impact, evidence, and suggested fix.

## Optional
- [O1] Title — Improvement, tradeoff, and when it is worth doing.

## Looks Good
- Note sound parts of the plan. If there are no concerns, write: "No concerns found."

--- PLAN START ---
$(cat "$PLAN_PATH")
--- PLAN END ---
CODEX_REVIEW_PROMPT
```

## Validate Feedback

For each Codex item, verify before acting:

- Does the referenced file, symbol, route, command, test, schema, or dependency actually exist?
- Does the concern follow from the codebase and the plan?
- Does it conflict with explicit user requirements?
- Is it critical, important, optional, invalid, or out of scope?

Ignore hallucinated or out-of-scope feedback. Do not change the plan just because Codex suggested it.

## Triage and Action

| Bucket | Meaning | Action |
|---|---|---|
| Critical | Likely implementation failure, broken tests, data loss, security/privacy risk, migration failure, wrong architecture, or user-requirement violation. | Fix the plan immediately. |
| Important | Valid improvement to correctness, maintainability, rollout safety, or test coverage, but not clearly blocking. | Apply if obvious and low-risk; otherwise ask. |
| Optional | Style, polish, alternative approach, extra hardening, or nice-to-have. | Ask or leave as a recommendation. |
| Invalid / out of scope | Hallucinated, already handled, irrelevant, or contrary to requirements. | Ignore; mention briefly only if useful. |

When applying feedback, edit the original plan/design doc. Do not create a separate feedback file.

## Asking About Non-Critical Choices

Prefer one grouped question for non-critical choices:

```text
Codex raised these non-critical options. Which should I apply?

1. [Short label] — [concrete change and tradeoff]
2. [Short label] — [concrete change and tradeoff]
3. Skip non-critical changes — Continue with critical fixes only.
```

Use `AskUserQuestion` if available; otherwise ask in chat. Use separate questions only for independent, high-impact choices. Always include a skip option.

## Review Rounds

Default flow:

1. Run round 1.
2. Validate and triage feedback.
3. Fix valid critical issues in the plan.
4. Ask about non-critical choices if needed.
5. Re-run only if valid critical issues were fixed.
6. Stop when a round has no valid critical issues, or after 3 total rounds.

Rules:

- Maximum 3 rounds total.
- Re-use the round 1 tier for later rounds, with one exception: if the findings show the plan is riskier than you scored it (unnoticed migration, security surface, or blast radius), escalate one tier for the next round. Never de-escalate mid-review.
- If the user requests a specific number of rounds, respect it but cap at 3.
- Do not re-run for optional or stylistic feedback only.
- If round 3 still has valid critical issues, stop and summarize the remaining risk.
- Respect the task boundary: if the user asked for review only, do not proceed to implementation.

## Failure Handling

If `codex exec` fails, times out, returns no usable stdout, or the CLI is unavailable:

1. Retry once with the same foreground command and Bash timeout.
2. If the prompt may be too large, retry once with a shorter prompt that still includes the plan path and structured output request.
3. If it still fails, ask:

```text
Codex review failed after one retry. How would you like to proceed?

1. Skip Codex review and continue with my own review.
2. Try Codex again.
3. Stop here so you can inspect the Codex setup locally.
```

Do not claim Codex reviewed the plan if the command failed or returned unusable output.

## Report Back

After the final review round, summarize:

- Rounds run, and the tier (model + effort) used for each.
- Critical issues found and plan changes made.
- Non-critical items applied, skipped, or awaiting decision.
- Invalid Codex feedback ignored, if relevant.
- Whether the plan is ready for implementation or still risky.

Do not paste long raw Codex output unless the user asks for it.

## Pitfalls

- Do not run Codex before saving the plan.
- Do not omit `-m` and `-c model_reasoning_effort=…`; falling back to the config default silently reviews a critical plan at the cheapest setting.
- Do not put `model_reasoning_effort` after the `-` stdin marker or pass it as `--reasoning-effort`; it is a `-c` config override and must precede `-`.
- Do not pick tier 1 to save time on work that met the auto-run trigger rules.
- Do not de-escalate the tier between rounds.
- Do not omit the Bash tool `timeout: 1200000`.
- Do not use shell `timeout`/`gtimeout` wrappers instead of the Bash tool timeout.
- Do not ask Codex to read the plan by path; inline it via `$(cat "$PLAN_PATH")` so Codex reviews exactly the intended content.
- Do not use `--full-auto` (removed from `codex exec`); rely on `--sandbox read-only`, which needs no approval flag.
- Do not pass `--ask-for-approval`/`-a` to `codex exec` — it is a top-level flag and errors as an "unexpected argument" if placed after `exec`.
- Do not background the process.
- Do not let Codex modify files.
- Do not auto-apply optional preferences.
- Do not exceed 3 rounds.
