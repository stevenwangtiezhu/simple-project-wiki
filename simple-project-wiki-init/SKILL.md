---
name: simple-project-wiki-init
description: Initialize code-grounded `.spwiki` project knowledge bases for a project or monorepo. Use when the user asks to initialize, create, bootstrap, generate the first version of, or set up project wiki documentation, AI knowledge bases, RepoWiki-style docs, `.spwiki` folders, or wiki skeletons for root projects and subprojects.
---

# Simple Project Wiki Init

Use this skill to initialize `.spwiki` knowledge bases. This is a Codex Skill entry, not a plugin and not a text command.

Shared resources are in `../simple-project-wiki`:

- `../simple-project-wiki/scripts/scan_project.py`
- `../simple-project-wiki/scripts/create_wiki_skeleton.py`
- `../simple-project-wiki/scripts/build_wiki_index.py`
- `../simple-project-wiki/scripts/check_wiki_ready.py`
- `../simple-project-wiki/references/wiki-structure.md`
- `../simple-project-wiki/references/wiki-generation-prompt.md`
- `../simple-project-wiki/references/quality-rules.md`
- `../simple-project-wiki/references/agent-operation-manual.md`
- `../simple-project-wiki/references/claude-code-adapter.md`

## Non-Negotiable Rules

- First run `python ../simple-project-wiki/scripts/check_wiki_ready.py <project-root> --json --strict --recursive`.
- Do not report initialization complete until strict readiness passes for every intended root/subproject wiki.
- A skeleton with TODO placeholders is incomplete, even when indexes exist.
- Every completed page must have `<cite>`, existing source refs, substantive content, and no secret-like values.
- For weak or Claude Code agents, read `../simple-project-wiki/references/agent-operation-manual.md` before writing.

## Workflow

1. Run the strict recursive readiness check. If all intended wikis are ready, do not reinitialize.
2. Run `python ../simple-project-wiki/scripts/scan_project.py <project-root> --output <scan.json>` to detect the root project, subprojects, manifests, source roots, config files, docs, and stack.
3. Read `../simple-project-wiki/references/wiki-structure.md` and choose `deep` by default; use `light` or `balanced` only if the user asks or the project is small.
4. Run `python ../simple-project-wiki/scripts/create_wiki_skeleton.py <scan.json> --write-config --build-index`; pass `--language <key>` only when the user asks for a specific language.
5. Use `.spwiki/topic-overrides.json`, `.spwiki/project-aliases.json`, `.spwiki/search-hints.json`, and `.spwiki/risk-profile.json` for project-specific topics, aliases, hints, and risks. Keep the skill itself project-generic.
6. Fill generated pages in batches from current source code using `../simple-project-wiki/references/wiki-generation-prompt.md` and the batch checkpoints in `../simple-project-wiki/references/agent-operation-manual.md`.
7. Each page must include real source citations in a `<cite>` block. Do not invent files, APIs, tables, commands, tests, or deployment mechanisms.
8. Rebuild each project index with `python ../simple-project-wiki/scripts/build_wiki_index.py <project-root>` after content is written.
9. Run `python ../simple-project-wiki/scripts/check_wiki_ready.py <project-root> --json --strict --recursive` again and report what was initialized.

## Output Contract

- Content path: `.spwiki/<language>/content` from `.spwiki/config.json`.
- Config path: `.spwiki/config.json`.
- Index path: `.spwiki/wiki-index.json`.
- Sidecar config paths: `.spwiki/topic-overrides.json`, `.spwiki/project-aliases.json`, `.spwiki/search-hints.json`, `.spwiki/risk-profile.json`.
- Monorepos get one root wiki plus one wiki per detected subproject.
- Existing files are protected by default. Use overwrite behavior only if the user explicitly requests it.
- A TODO skeleton is not a completed wiki. Fill or report it as incomplete.

## Default Config

```json
{
  "language": "zh",
  "content_root": "zh/content",
  "profile": "deep",
  "auto_update_after_code_change": false,
  "token_strategy": "prefilter_batch",
  "index_schema_version": 2,
  "strict_ready_required": true
}
```

## Verification

- Check that cited files exist.
- Check that `.spwiki/wiki-index.json` contains pages and source fingerprints.
- Check that topic directories have same-name index pages in the configured language/content root.
- Check strict readiness so missing citations, missing source refs, missing cited files, short content, secret-like values, and TODO placeholders do not pass as complete.
- Summarize initialized root/subproject wikis and any skipped already-ready wikis.

## Required Final Template

```text
Mode: init
Wiki roots checked:
Wiki indexes searched:
Wiki pages opened:
Source files verified:
Strict readiness:
Remaining TODO:
Result:
```
