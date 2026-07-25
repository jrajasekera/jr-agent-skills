# Repository Guidelines

## Overview

`jr-agent-skills` is a Claude Code plugin marketplace containing standalone
skills for API integrations, document processing, review workflows, and
database optimization. It has no shared application runtime, build system, or
central test suite; each skill is its own documentation-first package.

The marketplace is published through:

- `.claude-plugin/marketplace.json` — marketplace registration
- `.claude-plugin/plugin.json` — plugin metadata

When releasing a changed plugin, keep the root `plugin.json` version aligned
with the marketplace plugin entry's `version` (and its metadata version).
Claude Code caches plugins by version.

## Repository Layout

```text
skills/<skill-name>/
├── SKILL.md              # required skill definition and instructions
├── scripts/              # optional executable helpers
└── references/           # optional detailed documentation
```

The top-level [README.md](README.md) lists the published skills and their
installation flow. The relevant `SKILL.md` is the source of truth for each
skill's behavior, triggers, dependencies, and validation procedure; read it
fully before modifying that skill.

## Skill Authoring Rules

- Keep each skill in `skills/<kebab-case-name>/`.
- `SKILL.md` must begin with YAML frontmatter. Its `name` must be kebab-case
  and match the directory name.
- Make trigger descriptions precise enough to select the skill without making
  unrelated requests trigger it.
- Put executable helpers in `scripts/` and longer supporting material in
  `references/`; link to references from `SKILL.md` when users need them.
- Preserve an existing skill's established conventions and scope. Do not
  silently turn a documentation-only skill into a dependency-heavy package.

## Shell and Script Conventions

- Use Bash for shell helpers: `#!/usr/bin/env bash` and `set -euo pipefail`.
- Use four-space indentation in shell scripts.
- Use kebab-case for directories and script filenames; use descriptive
  snake_case names for shell functions.
- Never add tokens, keys, or example secrets to skills, scripts, logs, or
  committed output. Read credentials from environment variables where needed.

## Validation

There is no repository-wide test command. Validate the smallest affected
surface and record the exact command in the change or pull request notes.

- Documentation-only changes: run `git diff --check` and verify paths, links,
  frontmatter, and commands against the live tree.
- Script changes: run the script's documented help or a safe representative
  invocation. Avoid network calls, paid APIs, or destructive operations unless
  the task explicitly requires them.
- Manifest changes: parse both JSON files and confirm the root plugin version,
  marketplace plugin-entry version, and marketplace metadata version stay
  aligned.

For the article extractor, useful manual checks include:

```bash
skills/article-extractor/scripts/extract-article.sh "https://example.com/article"
skills/article-extractor/scripts/extract-article.sh "https://example.com/article" --format txt
```

## Git Workflow

- Preserve unrelated working-tree changes. This repository may contain local
  agent and editor state that must not be included in a skill change.
- Commit only the files in scope; inspect staged paths before committing.
- Use short, imperative commit subjects, such as `Add sqlite-optimization skill`.
  Conventional Commit prefixes are not required here.
- For a pull request, include a concise description, the validation command(s),
  and a sample output path when the change produces one. Call out breaking
  behavior changes clearly.

## Agent Guidance

- Start nontrivial work by checking `git status` and the relevant `SKILL.md`.
- Prefer `rg` or `rg --files` for repository searches.
- Keep changes focused on the requested skill or repository metadata; avoid
  unrelated formatting and refactors.
- If a task needs a third-party API, CLI, SDK, model catalog, pricing, or
  other volatile external fact, verify it from the source required by that
  skill instead of relying on memory.
