# Agent Operation Manual

Use this manual when an agent may have weak instruction following, when a wiki is being initialized or refreshed, or when the user asks for detailed project knowledge-base construction.

## Non-Negotiable Rules

1. `.spwiki` is a navigation layer, not source of truth.
2. Source code is the final authority.
3. Do not invent APIs, tables, queues, commands, tests, deployment scripts, or security posture.
4. Do not reproduce secrets, tokens, passwords, private keys, certificates, or private endpoints.
5. Do not accept TODO-only pages as complete.
6. Do not update `.spwiki` during ordinary code work unless explicitly requested or enabled by `.spwiki/config.json`.
7. Rebuild `.spwiki/wiki-index.json` after any wiki content change.
8. Write every `.md`, `.json`, and config file as UTF-8 (no other codepage). This is what prevents the `???` mojibake that appears when CJK/Korean/other non-ASCII text is written through a Windows console codepage (cp936/cp1252). When your tooling writes through a shell, set UTF-8 explicitly (for example `PYTHONUTF8=1`, `chcp 65001`, or an editor "Save as UTF-8"). Never commit content that already shows runs of `?` or the `�` replacement character; `check_wiki_ready.py --strict` now fails on those.
9. Honor the configured language. Once `.spwiki/config.json` records a `language`, every page, topic name, and update must use that language. Do not mix languages or silently switch. Each language lives in its own content root (`.spwiki/<language>/content`, e.g. `.spwiki/zh/content` or `.spwiki/kr/content`).
10. Respect `.gitignore`. `scan_project.py` skips files and directories ignored by the project's `.gitignore` (root and subprojects) by default. Do not document or cite generated/ignored artifacts (build output, caches, vendored deps) as project source.

## Required Self-Check Loop

At the start of any init/update/search run, write down the mode:

```text
Mode: init | update | search
Project root: <absolute or repo-relative root>
Wiki roots to check: root first, then relevant subprojects
Source verification required: yes
```

After every batch of 3-5 pages, or after every major search step, check:

```text
Evidence check:
- Every implementation claim cites an existing source file.
- Every cited path exists.
- No TODO remains in pages marked complete.
- No secrets were copied into the wiki.
- No mojibake (`???` runs or `�`) in any page; files saved as UTF-8.
- Every page is in the language recorded in .spwiki/config.json.
- Strict readiness failure lists are empty before completion.
- Index rebuild/check still needs to run: yes/no
```

If any item fails, fix it before continuing.

## Init Workflow

Use this for `$simple-project-wiki-init` or `/simple-project-wiki-init`.

1. Run readiness check:

```bash
python <shared-skill-dir>/scripts/check_wiki_ready.py <project-root> --json --strict --recursive
```

If a wiki is ready and strict checks pass, do not reinitialize it.

2. Scan project shape:

```bash
python <shared-skill-dir>/scripts/scan_project.py <project-root> --output <scan.json>
```

Confirm detected subprojects before writing. For monorepos, expect one root wiki plus one wiki per subproject unless the user narrows scope.

3. Create skeleton only when needed:

```bash
python <shared-skill-dir>/scripts/create_wiki_skeleton.py <scan.json> --write-config --build-index
```

Language selection: if the user named a language, pass `--language <key>` (for example `--language en` or `--language kr`). If the user did not specify one, omit `--language` and the script defaults to the detected system language. Whatever is chosen is written into `.spwiki/config.json` and becomes authoritative — every later page and update must use it. Re-running without `--force` preserves the existing config language, so the language never silently changes.

4. Fill pages in batches. For each page:

- Read the existing TODO page.
- Identify the smallest set of source files needed.
- Replace TODO sections with code-grounded content.
- Keep `<cite>` focused on files actually inspected.
- Add risk notes for auth, payment, file I/O, SQL, deserialization, admin, and secrets when source evidence supports them.
- Use `.spwiki/project-aliases.json`, `.spwiki/search-hints.json`, `.spwiki/topic-overrides.json`, and `.spwiki/risk-profile.json` for project-specific behavior instead of changing the shared skill.

5. Rebuild indexes:

```bash
python <shared-skill-dir>/scripts/build_wiki_index.py <project-root>
```

Repeat for each subproject wiki.

6. Run strict readiness:

```bash
python <shared-skill-dir>/scripts/check_wiki_ready.py <project-root> --json --strict --recursive
```

Do not report the wiki complete if strict readiness fails.

## Update Workflow

Use this for `$simple-project-wiki-update` or `/simple-project-wiki-update`.

1. Check readiness for the root and relevant subprojects.
2. Determine changed files from the user, `git diff --name-only`, or explicit paths.
3. Run the update planner:

```bash
python <shared-skill-dir>/scripts/plan_wiki_update.py <project-root> --changed-file <path>
```

Repeat `--changed-file` for multiple paths.

4. Read only candidate pages and associated changed source files.
5. Update pages only for durable behavior, API, config, data model, architecture, workflow, security, build, deploy, testing, or usage changes.
6. Rebuild index and run strict readiness.

## Search Workflow

Use this for `$simple-project-wiki-search` or `/simple-project-wiki-search`.

1. Run the search helper first when an index exists:

```bash
python <shared-skill-dir>/scripts/search_wiki.py <project-root> "<query>" --json
```

2. Open only the top relevant wiki pages or returned heading line ranges.
3. Follow `source_refs` to current source files.
4. Verify implementation facts in source.
5. If wiki and source disagree, answer from source and mention that the wiki appears stale.

## Required Final Template

Use this shape for init, update, and search so skipped steps are visible:

```text
Mode:
Wiki roots checked:
Wiki indexes searched:
Wiki pages opened:
Source files verified:
Strict readiness:
Remaining TODO:
Result:
```

## Stop Conditions

Stop and ask for clarification only when:

- Multiple project roots are plausible and choosing one would write unwanted `.spwiki` files.
- A wiki exists but appears hand-edited or conflicts with current source in a broad way.
- Required source files are missing and the user asked for a complete wiki rather than a best-effort partial update.

Otherwise, make conservative assumptions and continue.
