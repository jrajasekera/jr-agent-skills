# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Claude Code plugin marketplace containing skills for API integrations, document processing, and database optimization. Distributed via the Claude Code plugin marketplace system — users install with `/plugin marketplace add jrajasekera/claude-skills`.

## Distribution

This repo is a single-plugin marketplace. The manifests are:
- `.claude-plugin/marketplace.json` — marketplace registration
- `.claude-plugin/plugin.json` — plugin metadata

When releasing changes, bump `version` in **both** files. Claude Code caches plugins by version.

There is no build step or test framework. Test skills manually with sample input.

## Skill Structure

```
skills/{skill-name}/
├── SKILL.md              # Required: YAML frontmatter + markdown content
├── scripts/              # Optional: executable helpers (bash/python)
└── references/           # Optional: detailed reference docs
```

### SKILL.md Format

```yaml
---
name: skill-name           # kebab-case, must match directory name
description: |             # When/how the skill triggers
  Trigger conditions...
---
# Content in markdown
```

`SKILL.md` is the source of truth for each skill. Always read it before modifying a skill.

## Conventions

- **Directories/scripts:** kebab-case (`article-extractor`, `extract-article.sh`)
- **Functions in scripts:** snake_case
- **Shell scripts:** `#!/usr/bin/env bash` with `set -euo pipefail`, 4-space indent
- **Commits:** Short imperative summaries (e.g., "Add sqlite-optimization skill"), not conventional commits
