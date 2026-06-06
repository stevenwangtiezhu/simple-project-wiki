<div align="center">

# simple-project-wiki

</div>

## What is simple-project-wiki

`simple-project-wiki` is a project knowledge base skill set designed for Codex, Claude Code, and other AI coding assistants.

It helps AI agents build and maintain a code-grounded `.spwiki` knowledge base for a project. During daily development, the wiki acts as a fast navigation layer so the agent can locate architecture, modules, APIs, configuration, data models, and risk areas before verifying facts in the current source code.

The goal is to improve project understanding and reduce unnecessary token usage by avoiding repeated full-repository scans.

## Skill Set

The skill set is organized as multiple independent skills:

| Skill | Purpose |
|------|---------|
| `simple-project-wiki` | Shared policy, installation guidance, and ordinary wiki usage rules |
| `simple-project-wiki-init` | Initialize `.spwiki` for a root project and detected subprojects |
| `simple-project-wiki-update` | Update existing `.spwiki` from current source code |
| `simple-project-wiki-search` | Search `.spwiki` first, then verify facts in source code |

These are skills, not plugins and not slash commands. In Codex, they should be callable from the `$` skill list.

Install all four sibling directories together. The init/search/update skills depend on shared scripts and references in `simple-project-wiki`.

## Knowledge Base Layout

By default, each project or subproject gets its own wiki. The layout below shows an English (`en`) wiki; the folder and page names are localized to the configured language (a Chinese wiki uses Chinese names under `zh/content`):

```text
.spwiki/
├── config.json
├── wiki-index.json
└── en/
    └── content/
        ├── Project Overview.md
        ├── Quick Start.md
        ├── Troubleshooting Guide.md
        ├── Architecture/
        │   └── Architecture.md
        ├── Core Modules/
        │   └── Core Modules.md
        ├── API Documentation/
        │   └── API Documentation.md
        ├── Data Models/
        │   └── Data Models.md
        ├── Configuration/
        │   └── Configuration.md
        ├── Security and Permissions/
        │   └── Security and Permissions.md
        ├── Build and Deploy/
        │   └── Build and Deploy.md
        └── Development Guide/
            └── Development Guide.md
```

The content language is chosen when you initialize a wiki. If you do not specify one, the skill uses your operating system's language; you can override it at init (for example English or Korean). The chosen language is written into `.spwiki/config.json` and becomes authoritative: all later maintenance must use that same language, and each language lives in its own content root such as `.spwiki/en/content`, `.spwiki/zh/content`, or `.spwiki/kr/content`. The example above uses `en/content`; a Chinese wiki would use `zh/content` with Chinese page and topic names. All wiki files are written as UTF-8 so any language renders correctly.

Project-specific behavior belongs in sidecar config files, not in the shared skill:

```text
.spwiki/
├── topic-overrides.json
├── project-aliases.json
├── search-hints.json
└── risk-profile.json
```

For monorepos, create one root `.spwiki` and one `.spwiki` for each detected subproject.

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

When querying, searching, locating, or analyzing this project, prefer the `simple-project-wiki` skills first. Use `.spwiki` as the initial navigation and knowledge source, then verify all implementation facts against the current source code.
```

### 3. Add project guidance for Claude Code

When installing for Claude Code, add this rule to the project `CLAUDE.md`:

```markdown
## Project Wiki Usage

When querying, searching, locating, or analyzing this project, prefer the `simple-project-wiki` skills or equivalent project wiki workflow first. Use `.spwiki` as the initial navigation and knowledge source, then verify all implementation facts against the current source code.
```

### 4. Initialize a wiki

Use:

```text
$simple-project-wiki-init
```

The agent should scan the project, detect subprojects, create `.spwiki/config.json`, create `.spwiki/<language>/content`, build `.spwiki/wiki-index.json`, and fill documentation from current source code.

The scan honors each project's `.gitignore` (root and subprojects), so ignored files and directories — build output, caches, vendored dependencies — are not treated as project source.

To pick a language, tell the agent which one you want (for example "initialize the wiki in English" or "initialize the wiki in Korean"). If you do not specify a language, the system language is used. The language is then locked in `.spwiki/config.json` and reused for every later update.

#### Specifying a language at initialization

Under the hood the agent runs the skeleton script with a `--language <key>` argument. You can name the language in plain words and let the agent map it, or pass the key directly:

```bash
python simple-project-wiki/scripts/create_wiki_skeleton.py <scan.json> --write-config --build-index --language en
```

Omit `--language` to use the detected system language. Common language keys:

| Language | `--language` key | Content root |
|----------|------------------|--------------|
| Chinese (Simplified) | `zh` | `.spwiki/zh/content` |
| English | `en` | `.spwiki/en/content` |
| Korean | `kr` | `.spwiki/kr/content` |
| Japanese | `ja` | `.spwiki/ja/content` |
| French | `fr` | `.spwiki/fr/content` |
| German | `de` | `.spwiki/de/content` |
| Spanish | `es` | `.spwiki/es/content` |
| Portuguese | `pt` | `.spwiki/pt/content` |
| Russian | `ru` | `.spwiki/ru/content` |
| Italian | `it` | `.spwiki/it/content` |

Built-in topic and page names are localized for `zh` and `en`. Other keys produce a valid wiki under their own content root with English topic names as scaffolding; the agent then writes the actual page content in the chosen language. Any key works — pass the code you prefer — and once written to `.spwiki/config.json` it is locked for all later maintenance.

For Claude Code or weaker instruction-following agents, explicitly tell the agent to read `simple-project-wiki/references/agent-operation-manual.md` before writing wiki files. A TODO-only skeleton is not a completed wiki.

### 5. Search with the wiki

Use:

```text
$simple-project-wiki-search
```

The agent should search `.spwiki/wiki-index.json` and relevant Markdown pages first, then verify all implementation facts in the current source code.

When a query is known, prefer:

```bash
python simple-project-wiki/scripts/search_wiki.py <project-root> "<query>" --json
```

### 6. Update an existing wiki

Use:

```text
$simple-project-wiki-update
```

The agent should compare current source file hashes with `.spwiki/wiki-index.json`, update only affected pages, and rebuild the wiki index.

## Uninstall

Uninstalling has two parts. Do whichever the user wants.

### 1. Remove the skill directories

Delete the four sibling skill directories from wherever they were installed (for Claude Code, usually `.claude/skills/`; for Codex, the directory feeding the `$` skill list):

```text
simple-project-wiki/
simple-project-wiki-init/
simple-project-wiki-update/
simple-project-wiki-search/
```

Also remove the "Project Wiki Usage" block from the project `AGENTS.md` / `CLAUDE.md` if it was added at install time.

### 2. Remove the generated knowledge bases

**Uninstalling deletes the `.spwiki` folder.** Each initialized project or subproject has a `.spwiki/` knowledge base; removing the skill is not complete until those are deleted if you want them gone.

First list every `.spwiki` that would be removed (nothing is deleted):

```bash
python simple-project-wiki/scripts/uninstall_wiki.py <project-root>
```

Then delete them:

```bash
python simple-project-wiki/scripts/uninstall_wiki.py <project-root> --delete
```

The helper only removes directories named `.spwiki` (project root and subprojects); it never touches source code. You can also delete each `.spwiki/` folder by hand. Deleting a `.spwiki/` permanently removes that project's generated wiki pages, `config.json`, `wiki-index.json`, and sidecar config; it can be regenerated from source with `$simple-project-wiki-init`. See `simple-project-wiki/references/uninstall-guide.md` for the full procedure.

## Token-Saving Strategy

`simple-project-wiki` uses a low-token update strategy:

1. Read `.spwiki/wiki-index.json` first instead of full wiki pages.
2. Use source citations to map wiki pages to source files.
3. Use `sha256` hashes as the final change detector.
4. Treat `mtime` only as diagnostic metadata.
5. Read only changed source files and candidate wiki pages.

The generated index also carries lightweight lookup fields such as aliases, tags, routes, symbols, config keys, and risk flags. These are navigation hints only; source code remains the final authority.

The index also records heading anchors and line ranges so agents can open only a relevant section instead of reading an entire page.

This avoids rereading unchanged project files and helps conserve tokens during large-project maintenance.

## Important Rules

- `.spwiki` is a navigation and knowledge layer, not the final source of truth.
- Always verify implementation facts against current source code.
- The scan respects each project's `.gitignore`; ignored files and directories are not documented as source.
- The wiki language is fixed at initialization (your choice, otherwise the system language) and locked in `.spwiki/config.json`; all later maintenance uses that language, and each language lives in its own `.spwiki/<language>/content` root.
- All wiki files are written as UTF-8 so every language renders correctly; strict readiness fails on `???`/`�` mojibake.
- Do not automatically update `.spwiki` after code changes unless explicitly requested or enabled in `.spwiki/config.json`.
- Do not expose secrets, tokens, passwords, certificates, or private endpoints in wiki content.
- Do not mark generated TODO placeholder pages as complete. Use strict readiness checks before reporting completion.

## Default Config

`language` and `content_root` reflect the language chosen at initialization (the system language when unspecified). An English wiki looks like:

```json
{
  "language": "en",
  "content_root": "en/content",
  "profile": "deep",
  "auto_update_after_code_change": false,
  "token_strategy": "prefilter_batch",
  "index_schema_version": 2,
  "strict_ready_required": true
}
```
