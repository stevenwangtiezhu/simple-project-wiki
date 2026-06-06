# Uninstall Guide

Use this guide when the user asks to uninstall, remove, or disable the `simple-project-wiki` skill group.

Uninstalling has two independent parts. Do the one(s) the user asked for; confirm before deleting anything.

1. **Remove the skill itself** — the four sibling skill directories copied into the assistant's skills location.
2. **Remove the generated knowledge bases** — every `.spwiki/` folder this skill created inside target projects.

> Deleting a `.spwiki/` folder permanently removes the generated wiki content, its `config.json`, the `wiki-index.json`, and all sidecar config (`topic-overrides.json`, `project-aliases.json`, `search-hints.json`, `risk-profile.json`) for that project. Source code is never touched. The wiki is regenerable from source with `$simple-project-wiki-init`, but any hand-edited wiki prose is lost.

## Step 1 — Remove the skill directories

Delete these four sibling directories from wherever they were installed:

```text
simple-project-wiki/
simple-project-wiki-init/
simple-project-wiki-update/
simple-project-wiki-search/
```

For Claude Code this is usually under `.claude/skills/` (project-level) or the user-level Claude skills directory. For Codex, remove them from the skills directory that feeds the `$` skill list.

Also remove the "Project Wiki Usage" block from the project's `AGENTS.md` / `CLAUDE.md` if it was added during installation.

## Step 2 — Remove the generated `.spwiki/` folders

The knowledge base is a `.spwiki/` folder at each project/subproject root. A monorepo can have several.

First, **list** every `.spwiki/` that would be removed (no deletion):

```bash
python <shared-skill-dir>/scripts/uninstall_wiki.py <project-root>
```

Review the list with the user. Then **delete** them by re-running with `--delete`:

```bash
python <shared-skill-dir>/scripts/uninstall_wiki.py <project-root> --delete
```

The script only ever targets directories literally named `.spwiki`. It never deletes source files. It skips `.git`, `node_modules`, and other heavy folders while searching.

### Manual alternative

If you prefer not to run the helper, delete each `.spwiki` folder by hand. The folders are at the project root and at any subproject root that was initialized, for example:

```text
<project-root>/.spwiki/
<project-root>/<subproject>/.spwiki/
```

## After uninstall

- Ordinary code work no longer has a wiki to consult; the assistant falls back to normal source search.
- Nothing else in the project changes. Re-running `$simple-project-wiki-init` rebuilds `.spwiki/` from current source at any time.
