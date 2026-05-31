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

## Invoke Codex

Use the Bash tool with these settings:

- `timeout: 1200000`
- Foreground only: no `&`, `nohup`, `disown`, background subshells, or background task runners.
- Capture stdout directly; do not write Codex feedback to a file.
- Suppress stderr progress noise unless debugging a failure.

Run this from any directory; `-C` sets the Codex workspace root. `--sandbox read-only` keeps Codex read-only, so no approval flag is needed in `exec` mode. (If you ever need one, `-a`/`--ask-for-approval` is a top-level flag that must precede the `exec` subcommand: `codex -a never exec …`.)

Inline the plan's contents into the prompt via `$(cat "$PLAN_PATH")` — never ask Codex to open the plan by path itself, since it may silently read the wrong file and review the wrong content.

```bash
PROJECT_ROOT="/absolute/path/to/project/root"
PLAN_PATH="/absolute/path/to/plan.md"

cat <<CODEX_REVIEW_PROMPT | codex exec -C "$PROJECT_ROOT" \
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

- Rounds run.
- Critical issues found and plan changes made.
- Non-critical items applied, skipped, or awaiting decision.
- Invalid Codex feedback ignored, if relevant.
- Whether the plan is ready for implementation or still risky.

Do not paste long raw Codex output unless the user asks for it.

## Pitfalls

- Do not run Codex before saving the plan.
- Do not omit the Bash tool `timeout: 1200000`.
- Do not use shell `timeout`/`gtimeout` wrappers instead of the Bash tool timeout.
- Do not ask Codex to read the plan by path; inline it via `$(cat "$PLAN_PATH")` so Codex reviews exactly the intended content.
- Do not use `--full-auto` (removed from `codex exec`); rely on `--sandbox read-only`, which needs no approval flag.
- Do not pass `--ask-for-approval`/`-a` to `codex exec` — it is a top-level flag and errors as an "unexpected argument" if placed after `exec`.
- Do not background the process.
- Do not let Codex modify files.
- Do not auto-apply optional preferences.
- Do not exceed 3 rounds.
