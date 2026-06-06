---
name: simple-project-wiki
description: Shared policy and installation guidance for code-grounded `.wiki` project knowledge bases. Use when Codex is asked to install, configure, adapt, or explain the simple-project-wiki skill group; add AGENTS.md or CLAUDE.md wiki guidance; choose project-specific `.wiki/*.json` configuration; or decide which sibling skill to use. For initialization use $simple-project-wiki-init; for refresh use $simple-project-wiki-update; for ordinary wiki-first lookup use $simple-project-wiki-search.
---

# Simple Project Wiki

This is the shared policy skill for the `simple-project-wiki` skill group. The group is a set of Codex Skills, not a plugin and not text commands:

- `$simple-project-wiki`: shared policy, installation guidance, and ordinary wiki usage.
- `$simple-project-wiki-init`: initialize `.wiki` for a root project and detected subprojects.
- `$simple-project-wiki-update`: refresh existing `.wiki` from current code.
- `$simple-project-wiki-search`: search and use existing `.wiki` before source verification.

Shared scripts and references live in this skill directory:

- `scripts/scan_project.py`
- `scripts/create_wiki_skeleton.py`
- `scripts/build_wiki_index.py`
- `scripts/check_wiki_ready.py`
- `scripts/plan_wiki_update.py`
- `scripts/search_wiki.py`
- `scripts/wiki_common.py`
- `references/wiki-structure.md`
- `references/wiki-generation-prompt.md`
- `references/wiki-maintenance-protocol.md`
- `references/wiki-index-schema.md`
- `references/quality-rules.md`
- `references/claude-code-adapter.md`
- `references/agent-operation-manual.md`
- `references/post-build-usage-guide.md`

## Wiki Contract

- Default content path: `.wiki/zh/content`; scripts also support `.wiki/en/content` and other language roots declared in `.wiki/config.json`.
- Each project gets its own `.wiki/config.json` and `.wiki/wiki-index.json`.
- Monorepos get one root wiki plus one wiki per detected subproject.
- Topic directories use localized display names and include a same-name index page, for example `架构设计/架构设计.md` or `Architecture/Architecture.md`.
- Project-specific terms, search aliases, topic overrides, and risk rules live in `.wiki/project-aliases.json`, `.wiki/search-hints.json`, `.wiki/topic-overrides.json`, and `.wiki/risk-profile.json`; do not hard-code project business terms in the skill.
- Ignore `.qoder/repowiki`; do not migrate, copy, or treat it as source of truth.
- `.wiki` is an orientation aid. Current source code is the final authority.

## Ordinary Project Work

For project access, query, search, analysis, review, or modification tasks:

1. Before broad repository grep, check for `.wiki/wiki-index.json` at the root and relevant subprojects.
2. If an index exists and the query is known, run `python scripts/search_wiki.py <project-root> "<query>" --json`.
3. Open only the top relevant pages or heading ranges returned by `heading_hits`.
4. Use `source_refs` to locate source files and verify every implementation fact before answering or editing.
5. If wiki and source disagree, trust source code and treat the wiki as stale.
6. If `.wiki` is missing, do not initialize it automatically during ordinary work; suggest `$simple-project-wiki-init`.
7. Do not update wiki after code changes unless the user explicitly asks, invokes `$simple-project-wiki-update`, or `.wiki/config.json` has `auto_update_after_code_change: true`.

For focused wiki lookup, use `$simple-project-wiki-search`.

After a wiki exists, use `references/post-build-usage-guide.md` when deciding how to search, answer, and maintain wiki-backed project knowledge.

## Installation Guidance

When installing this skill group for Codex, add this requirement to project `AGENTS.md`:

```markdown
## Project Wiki Usage

When querying, searching, locating, or analyzing this project, prefer the `simple-project-wiki` skills first. Use `.wiki` as the initial navigation and knowledge source, then verify all implementation facts against the current source code.
```

Chinese equivalent:

```markdown
## 项目知识库使用要求

对本项目进行查询、搜索、定位或分析时，执行全仓 grep 前先检查 `.wiki/wiki-index.json`；优先使用 `simple-project-wiki-search` 或 `search_wiki.py` 定位页面、heading 段和 `source_refs`，再回到当前源码验证所有实现事实。
```

When installing for Claude Code, add this requirement to project `CLAUDE.md`:

```markdown
## Project Wiki Usage

When querying, searching, locating, or analyzing this project, prefer the `simple-project-wiki` skills or equivalent project wiki workflow first. Use `.wiki` as the initial navigation and knowledge source, then verify all implementation facts against the current source code.
```

Chinese equivalent:

```markdown
## 项目知识库使用要求

对本项目进行查询、搜索、定位或分析时，应优先使用 `simple-project-wiki` 相关技能或等价的项目知识库工作流；先使用 `.wiki` 作为项目知识库和定位入口，再回到当前源码验证所有实现事实。
```

Only edit `AGENTS.md` or `CLAUDE.md` when the user asks for installation/configuration or explicitly asks to update those project guidance files.

For Claude Code path layout, trigger mapping, and low-compliance agent setup, read `references/claude-code-adapter.md`.

For initialization or update runs performed by less reliable agents, require `references/agent-operation-manual.md` before any wiki writes. That manual contains batch checkpoints, stop conditions, strict completion rules, and post-batch self-checks.

## Default Config

Every initialized project wiki should have `.wiki/config.json`:

```json
{
  "language": "zh",
  "content_root": "zh/content",
  "profile": "deep",
  "auto_update_after_code_change": false,
  "token_strategy": "prefilter_batch",
  "ignore_qoder": true,
  "index_schema_version": 2,
  "strict_ready_required": true
}
```

Optional project-specific sidecar files:

- `.wiki/topic-overrides.json`: override or append project-specific topics and page structures.
- `.wiki/project-aliases.json`: map domain terms to synonyms, modules, pages, routes, or symbols.
- `.wiki/search-hints.json`: define synonyms, topic hints, and config-key prefixes used by search/update scripts.
- `.wiki/risk-profile.json`: define project-specific risk flags and matching keywords.

## Hash Strategy

- `build_wiki_index.py` records sha256, mtime, and size for cited source refs.
- `plan_wiki_update.py` recomputes sha256 for associated source refs.
- Use sha256 as the final skip/update criterion.
- Treat mtime as diagnostic or sorting metadata only; never use mtime alone to skip a page.
- Script-side hashing saves model tokens because unchanged source files do not need to be read by the model.
- `wiki-index.json` includes entity-level fields such as tags, aliases, routes, symbols, config keys, risk flags, source fingerprints, and heading line ranges when scripts can derive them. Use those fields for lookup, then verify in source.

## References

- For structure choices: read `references/wiki-structure.md`.
- For generation prompts: read `references/wiki-generation-prompt.md`.
- For usage and maintenance rules: read `references/wiki-maintenance-protocol.md`.
- For index fields: read `references/wiki-index-schema.md`.
- For truthfulness/security checks: read `references/quality-rules.md`.
- For Claude Code adaptation: read `references/claude-code-adapter.md`.
- For strict agent behavior during init/update/search: read `references/agent-operation-manual.md`.
- For daily use after a wiki is built: read `references/post-build-usage-guide.md`.
