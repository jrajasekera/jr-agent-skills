# jr-agent-skills

This is a single-plugin Claude Code marketplace of documentation-first skills,
not an application. There is no shared runtime, build, or central test suite.
`AGENTS.md` is the canonical repository guide; root `CLAUDE.md` links to it.

## Where to work

- `README.md` lists published skills and installation instructions. Update it
  when adding, removing, or changing the public scope of a skill.
- `skills/<skill-name>/SKILL.md` defines triggers, dependencies, and behavior.
  Read the target skill fully before editing, then its relevant linked references.
- Optional `scripts/` contain helpers; `references/` hold detailed documentation.
  Keep changes within the requested skill and preserve its established scope.
- `.claude-plugin/plugin.json` describes the plugin;
  `.claude-plugin/marketplace.json` registers it with local source `./`.

## Authoring

- Use kebab-case skill directories. Begin `SKILL.md` with YAML frontmatter;
  `name` must match the directory, and `description` must identify when to use it.
- Keep the entrypoint concise and link supporting material from it. Preserve
  relative references so the skill remains usable after installation.
- Existing shell helpers use Bash, `#!/usr/bin/env bash`, `set -euo pipefail`,
  four-space indentation, and kebab-case filenames. Python helpers use
  snake_case filenames/functions; follow the target helper's conventions.
- API skills own their discovery and source-verification workflows. Verify
  changing model IDs, capabilities, pricing, and API behavior through those
  workflows; do not turn catalog snapshots into permanent repository rules.
- Keep credentials in environment variables, never in examples or outputs.

## Validation

Run commands from the repository root. For documentation changes, use
`git diff --check` and verify referenced paths, frontmatter, and commands against
the live tree. There is no global dependency installation to perform.

These help checks run without network calls or conversion/extraction work:

```bash
bash skills/article-extractor/scripts/extract-article.sh --help
python3 skills/pandoc-converter/scripts/convert.py --help
python3 skills/openrouter-api/scripts/discover_models.py --help
python3 skills/openrouter-api/scripts/inspect_openapi.py --help
python3 skills/venice-ai-api/scripts/discover_models.py --help
```

For changed Bash helpers, run `bash -n <script>`. For behavioral changes, also
exercise representative input according to the skill; help output alone is not
behavioral validation. Live API calls, dependency installers, and article URLs
are not offline smoke tests. Report the exact checks and remaining gaps.

## Metadata and commits

- For a release, keep `plugin.json`'s `version`, marketplace `metadata.version`,
  and the `jr-agent-skills` entry in marketplace `plugins[].version` aligned.
  Parse both manifests after editing. Do not bump versions for every docs edit.
- Preserve unrelated changes and stage explicit task-owned paths. `AGENTS.md`
  is already tracked despite the matching `.gitignore` rule; keep it tracked.
- Keep `CLAUDE.md` a relative symlink to `AGENTS.md`, not a second instructions
  copy. Check it with `test -L CLAUDE.md` and `readlink CLAUDE.md`.
- Use a short imperative commit subject; include validation and any breaking
  behavior in the change description. Push only when requested.
