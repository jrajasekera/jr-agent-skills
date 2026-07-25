# Claude Skills Collection

A Claude Code plugin marketplace with skills for API integrations, document processing, and database optimization.

## Installation

```bash
# Add the marketplace
/plugin marketplace add jrajasekera/jr-agent-skills

# Install the plugin (includes all skills)
/plugin install jr-agent-skills@jr-agent-skills
```

## Available Skills

### [article-extractor](./skills/article-extractor/)
Extract clean, readable content from web articles by removing navigation, ads, and other clutter. Supports multiple extraction methods and output formats.

### [codex-review](./skills/codex-review/)
Cross-agent review for design docs and implementation plans using Codex. Gets feedback on plans before implementation.

### [openrouter-api](./skills/openrouter-api/)
OpenRouter API integration for unified access to 400+ LLM models from 70+ providers through a single API.

### [pandoc-converter](./skills/pandoc-converter/)
Convert documents between common formats using Pandoc for consistent output and easy automation.

### [sqlite-optimization](./skills/sqlite-optimization/)
Optimize SQLite database performance through configuration, schema design, indexing, and query tuning.

### [venice-ai-api](./skills/venice-ai-api/)
Build, migrate, and debug Venice.ai API integrations — chat and Responses, live model discovery and routing, images, audio, video, embeddings, characters, key administration, billing, and wallet authentication.

### [z-ai-api](./skills/z-ai-api/)
Z.ai/ZhipuAI API integration for building applications with GLM models including chat, vision, image/video generation, and audio transcription.

## Structure

```
jr-agent-skills/
├── .claude-plugin/
│   ├── marketplace.json    # Marketplace registration
│   └── plugin.json         # Plugin metadata
├── skills/                 # All skill folders
│   ├── article-extractor/
│   ├── codex-review/
│   ├── openrouter-api/
│   ├── pandoc-converter/
│   ├── sqlite-optimization/
│   ├── venice-ai-api/
│   └── z-ai-api/
└── README.md
```

Each skill folder contains:
- `SKILL.md` - Skill documentation and usage instructions
- `scripts/` - Executable scripts (if applicable)
- `references/` - Detailed reference docs (if applicable)

## Migration from .skill Files

If you previously installed skills from the `packaged_skills/` directory, remove those and use the marketplace installation above instead.

## Author

Created by Jrajasekera
