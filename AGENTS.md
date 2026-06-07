# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this repo is

This repo is **the skill set itself**, not an application that uses it. It ships three sibling AI-agent workflow skills plus one shared resource directory that build and maintain a code-grounded `.spwiki/` knowledge base for *other* projects. There is no build step and no app to run; the deliverables are the Python scripts in `simple-project-wiki/scripts/`, the Markdown references in `simple-project-wiki/references/`, and the three workflow `SKILL.md` entry points.

When editing here, you are editing tooling that gets copied into another project's skills directory (`.Codex/skills/` for Codex, or the Codex `$` skill list). Keep all four directories installable as siblings — the init/update/search skills resolve shared code via the relative path `../simple-project-wiki/scripts/...`, so that layout must be preserved. The `simple-project-wiki/` directory is shared resources only; do not register it as a `$simple-project-wiki` command.

## Architecture

Three triggerable workflow skills share one resource directory that contains all executable code:

- `simple-project-wiki/` — shared policy + **all** scripts and references; no `SKILL.md` command entry point.
- `simple-project-wiki-init/` — bootstrap a new `.spwiki/` for a project/monorepo.
- `simple-project-wiki-update/` — refresh an existing `.spwiki/` after code changes.
- `simple-project-wiki-search/` — wiki-first lookup before source verification.

The scripts form a pipeline; data flows through JSON artifacts rather than shared process state:

1. `scan_project.py <root> -o scan.json` — detects the root project, nested subprojects, manifests, source roots, config files, and tech stack. Honors each project's `.gitignore` (root + subprojects) by default via `GitignoreMatcher`; `--no-gitignore` disables that. Output drives everything downstream.
2. `create_wiki_skeleton.py scan.json --write-config --build-index [--language <key>]` — reads `scan.json`, writes `.spwiki/config.json` + sidecar configs, generates the topic/page skeleton, optionally builds the first index. `--language` defaults to the detected system language (`detect_system_language` in `wiki_common.py`); whatever is chosen is written to config and is authoritative thereafter. **Skeleton pages are TODO placeholders — they are not a finished wiki.**
3. (Agent fills pages from real source code — this is the model's job, not a script's.)
4. `build_wiki_index.py <root>` — (re)builds `.spwiki/wiki-index.json` from the Markdown: records per-page sha256/mtime/size of cited source refs, heading anchors + line ranges, aliases, tags, routes, symbols, config keys, risk flags.
5. `check_wiki_ready.py <root> --json --strict --recursive` — the **gate**. Strict mode fails on TODO placeholders, missing `<cite>` blocks, missing/nonexistent source refs, too-short content, secret-like values, and mojibake (`???` runs / `�` from non-UTF-8 writes). Init/update must not report success until this passes.
6. `plan_wiki_update.py <root> [--changed-file PATH ...]` — low-token update planner: recomputes sha256 for cited source and emits only the pages that need attention.
7. `search_wiki.py <root> "<query>" --json` — queries `wiki-index.json` (titles, topics, `source_refs`, `heading_hits`) so agents open only relevant sections.
8. `uninstall_wiki.py <root> [--delete]` — lists (default) or deletes every generated `.spwiki/` folder under a project. Only touches directories named `.spwiki`; never source.

`wiki_common.py` is the shared core for every script: default config, `detect_system_language`/`SYSTEM_LANGUAGE_MAP`, the `zh`/`en` `LANGUAGE_PROFILES` (topic taxonomy + per-stack topic selection in `default_topic_keys`), risk/secret/mojibake regexes, the UTF-8 read/write helpers (`read_text_utf8`/`write_text_utf8`), the tokenizer (including CJK bigrams in `tokenize`/`cjk_bigrams`), and JSON sidecar loaders. Stack → topic mapping lives in the `*_TOPIC_KEYS` constants and `default_topic_keys`; that is where to add support for a new framework's topic structure.

## Key design invariants

- **Source code is the final authority; `.spwiki/` is only an orientation/navigation layer.** Every claim in a wiki page must be verifiable against current source via its `<cite>` source refs.
- **sha256 is the change detector, mtime is diagnostic only.** Never skip a page based on mtime alone (`build_wiki_index.py` records both; `plan_wiki_update.py` compares hashes).
- **Strict readiness is non-negotiable for init/update.** A TODO skeleton with a valid index is still incomplete.
- **Project-specific terms stay out of the skill code.** Domain aliases, topic overrides, search hints, and risk keywords belong in per-project sidecar files (`.spwiki/project-aliases.json`, `topic-overrides.json`, `search-hints.json`, `risk-profile.json`) loaded at runtime by `wiki_common.py`, never hard-coded into the Python.
- **Language is chosen once at init and locked.** No `--language` → system language; whatever lands in `.spwiki/config.json` governs every later page and update. Each language has its own `content_root` (`<lang>/content`). Built-in topic/page names exist only for `zh`/`en`; other keys scaffold with English names and the agent writes content in the target language.
- **All wiki files are UTF-8.** The `???`/`�` mojibake comes from writing non-ASCII through a Windows codepage; use `write_text_utf8` and the strict mojibake check guards against it.
- The scripts are pure standard-library Python 3 (uses `from __future__ import annotations`, walrus operators) with no third-party dependencies and no test suite. Verify changes by running a script against a sample project tree.

## Running the scripts

From inside the `simple-project-wiki` directory (paths are relative to the skill that calls them; the sibling skills prefix with `../simple-project-wiki/`):

```bash
python scripts/scan_project.py <project-root> -o scan.json
python scripts/create_wiki_skeleton.py scan.json --write-config --build-index   # add --language <key> to override the system language
python scripts/build_wiki_index.py <project-root>
python scripts/check_wiki_ready.py <project-root> --json --strict --recursive
python scripts/plan_wiki_update.py <project-root> --changed-file path/to/changed.py
python scripts/search_wiki.py <project-root> "<query>" --json
python scripts/uninstall_wiki.py <project-root>            # list .spwiki folders; add --delete to remove
```

## When editing the skills

- Workflow `SKILL.md` frontmatter (`name` + `description`) is the trigger contract an agent matches against — keep descriptions specific and aligned with the workflow steps below them.
- The agent-behavior rules for less reliable / Codex agents live in `references/agent-operation-manual.md` (batch checkpoints, stop conditions, strict completion). `references/claude-code-adapter.md` covers Claude Code path layout and trigger mapping.
- The workflow `SKILL.md` files and the README embed the same default `config.json` block and the same AGENTS.md/CLAUDE.md "Project Wiki Usage" install snippet — if you change one, update all copies so they stay consistent.
- `design/spwiki-design.md` is the canonical (not implemented) proposal for the next-generation `.spwiki` index/retrieval model: confirmed v2 bugs to fix first, then a code-entity-graph + evidence-graded fact-card model with compiled query plans and a trust ledger (efficiency + accuracy). It is a repo-evolution document and must NOT be copied into target projects' skills directories.
