<div align="center">

# simple-project-wiki

</div>

## What is simple-project-wiki

`simple-project-wiki` is a project knowledge base skill set designed for Codex, Claude Code, and other AI coding assistants.

It helps AI agents build and maintain a code-grounded `.wiki` knowledge base for a project. During daily development, the wiki acts as a fast navigation layer so the agent can locate architecture, modules, APIs, configuration, data models, and risk areas before verifying facts in the current source code.

The goal is to improve project understanding and reduce unnecessary token usage by avoiding repeated full-repository scans.

## Skill Set

The skill set is organized as multiple independent skills:

| Skill | Purpose |
|------|---------|
| `simple-project-wiki` | Shared policy, installation guidance, and ordinary wiki usage rules |
| `simple-project-wiki-init` | Initialize `.wiki` for a root project and detected subprojects |
| `simple-project-wiki-update` | Update existing `.wiki` from current source code |
| `simple-project-wiki-search` | Search `.wiki` first, then verify facts in source code |

These are skills, not plugins and not slash commands. In Codex, they should be callable from the `$` skill list.

Install all four sibling directories together. The init/search/update skills depend on shared scripts and references in `simple-project-wiki`.

## Knowledge Base Layout

By default, each project or subproject gets its own wiki:

```text
.wiki/
├── config.json
├── wiki-index.json
└── zh/
    └── content/
        ├── 项目概述.md
        ├── 快速开始.md
        ├── 故障排除指南.md
        ├── 架构设计/
        │   └── 架构设计.md
        ├── 核心模块/
        │   └── 核心模块.md
        ├── API接口文档/
        │   └── API接口文档.md
        ├── 数据模型/
        │   └── 数据模型.md
        ├── 配置管理/
        │   └── 配置管理.md
        ├── 安全与权限/
        │   └── 安全与权限.md
        ├── 构建部署/
        │   └── 构建部署.md
        └── 开发指南/
            └── 开发指南.md
```

The default language is Chinese (`zh/content`), but scripts read `.wiki/config.json` and can build other roots such as `en/content`.

Project-specific behavior belongs in sidecar config files, not in the shared skill:

```text
.wiki/
├── topic-overrides.json
├── project-aliases.json
├── search-hints.json
└── risk-profile.json
```

For monorepos, create one root `.wiki` and one `.wiki` for each detected subproject.

## Quickstart

### 1. Install the skills

Copy the skill directories into the skills directory used by your AI coding assistant.

Expected skill directories:

```text
simple-project-wiki/
simple-project-wiki-init/
simple-project-wiki-update/
simple-project-wiki-search/
```

For Codex, confirm that the skills appear in the `$` skill list.

For Claude Code, copy the same four directories under `.claude/skills/` or the user-level Claude skills directory, preserving the sibling layout:

```text
.claude/skills/
├── simple-project-wiki/
├── simple-project-wiki-init/
├── simple-project-wiki-update/
└── simple-project-wiki-search/
```

Codex examples use `$simple-project-wiki-*`. Claude Code users should invoke the equivalent `/simple-project-wiki-*` form when using slash-style skills.

### 2. Add project guidance for Codex

When installing for Codex, add this rule to the project `AGENTS.md`:

```markdown
## Project Wiki Usage

When querying, searching, locating, or analyzing this project, prefer the `simple-project-wiki` skills first. Use `.wiki` as the initial navigation and knowledge source, then verify all implementation facts against the current source code.
```

### 3. Add project guidance for Claude Code

When installing for Claude Code, add this rule to the project `CLAUDE.md`:

```markdown
## Project Wiki Usage

When querying, searching, locating, or analyzing this project, prefer the `simple-project-wiki` skills or equivalent project wiki workflow first. Use `.wiki` as the initial navigation and knowledge source, then verify all implementation facts against the current source code.
```

### 4. Initialize a wiki

Use:

```text
$simple-project-wiki-init
```

The agent should scan the project, detect subprojects, create `.wiki/config.json`, create `.wiki/<language>/content`, build `.wiki/wiki-index.json`, and fill documentation from current source code.

For Claude Code or weaker instruction-following agents, explicitly tell the agent to read `simple-project-wiki/references/agent-operation-manual.md` before writing wiki files. A TODO-only skeleton is not a completed wiki.

### 5. Search with the wiki

Use:

```text
$simple-project-wiki-search
```

The agent should search `.wiki/wiki-index.json` and relevant Markdown pages first, then verify all implementation facts in the current source code.

When a query is known, prefer:

```bash
python simple-project-wiki/scripts/search_wiki.py <project-root> "<query>" --json
```

### 6. Update an existing wiki

Use:

```text
$simple-project-wiki-update
```

The agent should compare current source file hashes with `.wiki/wiki-index.json`, update only affected pages, and rebuild the wiki index.

## Token-Saving Strategy

`simple-project-wiki` uses a low-token update strategy:

1. Read `.wiki/wiki-index.json` first instead of full wiki pages.
2. Use source citations to map wiki pages to source files.
3. Use `sha256` hashes as the final change detector.
4. Treat `mtime` only as diagnostic metadata.
5. Read only changed source files and candidate wiki pages.

The generated index also carries lightweight lookup fields such as aliases, tags, routes, symbols, config keys, and risk flags. These are navigation hints only; source code remains the final authority.

The index also records heading anchors and line ranges so agents can open only a relevant section instead of reading an entire page.

This avoids rereading unchanged project files and helps conserve tokens during large-project maintenance.

## Important Rules

- `.wiki` is a navigation and knowledge layer, not the final source of truth.
- Always verify implementation facts against current source code.
- Ignore `.qoder/repowiki`; do not migrate or rely on it as source of truth.
- Do not automatically update `.wiki` after code changes unless explicitly requested or enabled in `.wiki/config.json`.
- Do not expose secrets, tokens, passwords, certificates, or private endpoints in wiki content.
- Do not mark generated TODO placeholder pages as complete. Use strict readiness checks before reporting completion.

## Default Config

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
