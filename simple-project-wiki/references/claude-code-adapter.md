# Claude Code Adapter

Use this reference when installing or adapting `simple-project-wiki` for Claude Code.

## Purpose

The shared package is written to be portable across Codex and Claude Code, but the two tools discover and trigger skills differently. Keep the shared package conservative, then add Claude-specific behavior in the Claude installation copy or in `CLAUDE.md`.

## Install Layout

For Claude Code, install all four sibling package directories together. Only `simple-project-wiki-init`, `simple-project-wiki-search`, and `simple-project-wiki-update` are triggerable skills; `simple-project-wiki` is a shared resource directory.

```text
.claude/
└── skills/
    ├── simple-project-wiki/
    ├── simple-project-wiki-init/
    ├── simple-project-wiki-search/
    └── simple-project-wiki-update/
```

User-level installation may use the Claude Code user skills directory instead. Keep the sibling relationship because the init/search/update skills resolve shared scripts and references through `../simple-project-wiki`. Do not add a `SKILL.md` or slash command registration to the shared `simple-project-wiki/` directory.

## Trigger Mapping

Codex examples in this package use:

```text
$simple-project-wiki-search
$simple-project-wiki-init
$simple-project-wiki-update
```

In Claude Code, use the equivalent slash-style trigger when available:

```text
/simple-project-wiki-search
/simple-project-wiki-init
/simple-project-wiki-update
```

If Claude Code auto-selects skills from frontmatter, the same `name` and `description` fields should still be enough to identify the relevant skill.

There is intentionally no `/simple-project-wiki` trigger. For general wiki policy, use the installed references in `simple-project-wiki/references/` or invoke the specific init/search/update workflow.

## CLAUDE.md Guidance

Add only a small always-on rule to `CLAUDE.md`; keep detailed procedures in the skill references:

```markdown
## Project Wiki Usage

When querying, searching, locating, or analyzing this project, prefer the `simple-project-wiki-search` workflow or equivalent project-wiki lookup process first. Use `.spwiki` as the initial navigation source, then verify implementation facts against current source code. For initialization or refresh, follow the relevant workflow skill's agent operation manual and do not accept TODO-only pages as complete.
```

## Low-Compliance Agent Setup

For agents that may skip steps, put the request in this shape:

```text
Use /simple-project-wiki-init.
Before writing files, read references/agent-operation-manual.md.
Work in batches. After each batch, report:
1. Pages completed
2. Source files verified
3. Remaining TODO or missing citations
Do not mark the wiki complete until strict readiness and index rebuild pass.
```

For search tasks:

```text
Use /simple-project-wiki-search.
First run search_wiki.py or read .spwiki/wiki-index.json.
Then open only the most relevant wiki pages.
Then verify every implementation fact in source code before answering.
```

For Claude-specific copies, prefer deterministic paths:

```text
python ${CLAUDE_SKILL_DIR}/../simple-project-wiki/scripts/search_wiki.py <project-root> "<query>" --json
python ${CLAUDE_SKILL_DIR}/../simple-project-wiki/scripts/check_wiki_ready.py <project-root> --json --strict --recursive
```

## Side-Effect Rules

- Init and update skills write `.spwiki`; invoke them only when the user explicitly asks.
- Search is read-only and should be the default workflow during ordinary development.
- If creating a Claude-only copy and Claude Code supports side-effect metadata, mark init/update as manual-invocation skills such as `disable-model-invocation: true`. Do not add Claude-only frontmatter to the shared resource directory.

## Compatibility Notes

- `agents/openai.yaml` files in the workflow skill directories are Codex/OpenAI UI metadata, not Claude subagent definitions.
- Claude subagents, if used, should be separate Markdown agent files in Claude's agent directory.
- Prefer one search-oriented Claude subagent for read-only lookup. Avoid autonomous init/update subagents unless the user explicitly requests a documentation maintenance run.
