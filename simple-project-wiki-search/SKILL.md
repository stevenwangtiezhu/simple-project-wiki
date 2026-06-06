---
name: simple-project-wiki-search
description: Search and use existing `.spwiki` project knowledge bases before source-code verification. Use for project queries, locating files/modules/APIs/configs, understanding architecture, analyzing code impact, or starting code modifications when `.spwiki` may exist.
---

# Simple Project Wiki Search

Use this skill for wiki-first project lookup. This is a Codex Skill entry, not a plugin and not a text command.

Shared resources are in `../simple-project-wiki`:

- `../simple-project-wiki/scripts/scan_project.py`
- `../simple-project-wiki/scripts/search_wiki.py`
- `../simple-project-wiki/references/wiki-maintenance-protocol.md`
- `../simple-project-wiki/references/wiki-index-schema.md`
- `../simple-project-wiki/references/post-build-usage-guide.md`
- `../simple-project-wiki/references/agent-operation-manual.md`

## Workflow

1. Before broad repository grep, check for `.spwiki/wiki-index.json` and the configured `.spwiki/<language>/content` at the project root.
2. If the repository is a monorepo, also check likely subproject roots.
3. Run `python ../simple-project-wiki/scripts/search_wiki.py <project-root> "<query>" --json` when the user provides a keyword, route, path, symbol, config key, or risk topic.
4. Search `.spwiki/wiki-index.json` first for titles, topics, summaries, heading line ranges, `source_refs`, aliases, tags, routes, API endpoints, symbols, config keys, and risk flags.
5. Open only the most relevant `.spwiki/<language>/content/**/*.md` pages or `heading_hits` ranges.
6. Use wiki results to identify likely source files, modules, routes, configs, entities, commands, risks, or dependencies.
7. Verify all implementation facts in current source code before answering, editing, or making claims.
8. If wiki and source disagree, source code wins.

For lower-compliance agents, read `../simple-project-wiki/references/agent-operation-manual.md` and follow the Search Workflow section.

## Missing Wiki

If `.spwiki` does not exist during ordinary project work:

- Do not initialize automatically.
- Tell the user they can use `$simple-project-wiki-init` to initialize a project knowledge base.
- Continue with normal source-code search if the user asked for the current task to proceed.

## Code Changes

- Do not update wiki after code changes by default.
- If the user asks to maintain wiki, or `.spwiki/config.json` has `auto_update_after_code_change: true`, use `$simple-project-wiki-update` rules.
- Use wiki pages only as orientation; never skip source verification.

## Required Final Template

```text
Mode: search
Wiki roots checked:
Wiki indexes searched:
Wiki pages opened:
Source files verified:
Strict readiness:
Remaining TODO:
Result:
```
