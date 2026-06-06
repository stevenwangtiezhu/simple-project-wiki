---
name: simple-project-wiki-update
description: Update existing `.spwiki` project knowledge bases from current source code with low-token sha256 prefiltering. Use when the user asks to refresh, sync, update, repair, maintain, reconcile, or globally regenerate project wiki documentation after code changes.
---

# Simple Project Wiki Update

Use this skill to update existing `.spwiki` knowledge bases. This is a Codex Skill entry, not a plugin and not a text command.

Shared resources are in `../simple-project-wiki`:

- `../simple-project-wiki/scripts/scan_project.py`
- `../simple-project-wiki/scripts/build_wiki_index.py`
- `../simple-project-wiki/scripts/check_wiki_ready.py`
- `../simple-project-wiki/scripts/plan_wiki_update.py`
- `../simple-project-wiki/scripts/search_wiki.py`
- `../simple-project-wiki/references/wiki-maintenance-protocol.md`
- `../simple-project-wiki/references/wiki-index-schema.md`
- `../simple-project-wiki/references/quality-rules.md`
- `../simple-project-wiki/references/agent-operation-manual.md`

## Workflow

1. If this is running in Claude Code or with a low-compliance agent, read `../simple-project-wiki/references/agent-operation-manual.md` before writing files.
2. Check `.spwiki/config.json` and `.spwiki/wiki-index.json` for the root project and relevant subprojects.
3. Run `python ../simple-project-wiki/scripts/check_wiki_ready.py <project-root> --json --strict --recursive` to see existing readiness failures before editing.
4. Run `python ../simple-project-wiki/scripts/scan_project.py <project-root> --output <scan.json>` when project shape may have changed.
5. Run `python ../simple-project-wiki/scripts/plan_wiki_update.py <project-root>` and include `--changed-file <path>` when known.
6. Use `.spwiki/search-hints.json` and `.spwiki/risk-profile.json` as project-specific topic/risk routing hints. Do not hard-code project-specific terms in the skill.
7. Use sha256 comparison as the final skip/update criterion. If all cited source hashes are unchanged and no changed-file/topic/symbol hint applies, skip the page without reading full source.
8. Treat changed sha256, missing source, missing old hash, new refs, missing wiki pages, unlinked changed files, `related_globs` hits, or project shape changes as update candidates.
9. Read only candidate wiki pages and the associated changed/new source files unless broader impact is clear.
10. Update stale Markdown, create missing pages, and delete or merge pages that only describe removed functionality.
11. Rebuild `.spwiki/wiki-index.json` with `python ../simple-project-wiki/scripts/build_wiki_index.py <project-root>` after updates.
12. Run `python ../simple-project-wiki/scripts/check_wiki_ready.py <project-root> --json --strict --recursive` before reporting completion.
13. Report updated/skipped pages and reasons. Do not create wiki changelog files.

## Maintenance Rules

- Do not update wiki automatically after code changes unless the user asks or `.spwiki/config.json` explicitly has `auto_update_after_code_change: true`.
- Update wiki only for final, kept, validated changes that affect behavior, APIs, configuration, data models, architecture, important workflows, risk/security posture, build/deploy, tests, or usage.
- Do not update wiki for temporary experiments, reverted work, unfinished failures, pure formatting, or comment-only edits.

## Token Strategy

- Prefer `.spwiki/wiki-index.json` as the low-token search entry, using heading line ranges to avoid reading full pages when possible.
- Prefer `plan_wiki_update.py` before opening full wiki pages.
- mtime is diagnostic only. Never use mtime alone to skip a page.
- sha256 unchanged means the cited source content is unchanged and the page can usually be skipped.

## Verification

- Check cited paths still exist or update citations.
- Rebuild index and confirm source fingerprints changed as expected.
- Verify changed implementation facts against source before finalizing wiki edits.
- Strict readiness must pass before reporting completion; otherwise report the remaining failure lists.

## Required Final Template

```text
Mode: update
Wiki roots checked:
Wiki indexes searched:
Wiki pages opened:
Source files verified:
Strict readiness:
Remaining TODO:
Result:
```
