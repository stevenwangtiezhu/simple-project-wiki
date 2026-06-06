# Quality Rules

Apply these checks before considering a generated wiki complete.

## Source Grounding

- Every implementation claim must be traceable to a real file.
- Every cited path must exist.
- Do not invent line numbers. Use line anchors only after inspecting the file.
- Keep `<cite>` lists focused on files actually used by the document.
- Prefer current source files over generated artifacts, dependency folders, or stale docs.
- Every completed page should have a `<cite>` block and non-empty `source_refs` in `.wiki/wiki-index.json`.

## Truthfulness

- Do not claim tests, CI, Docker, migrations, APIs, queues, schemas, auth flows, or deploy scripts exist unless the repository shows them.
- If a feature appears partially implemented, say so.
- If a file is decompiled, vendored, generated, or a local binary dependency, label that status.
- Distinguish project-specific facts from general best practices.

## Security

- Do not reproduce secrets, credentials, private keys, tokens, certificates, webhook URLs, database passwords, or production endpoints.
- It is acceptable to document that hardcoded sensitive configuration exists and name the file path.
- For auth, payment, file I/O, SQL, deserialization, and admin features, include risk notes when code evidence supports them.
- Strict readiness fails on secret-like assignments in wiki text; describe risk without copying values.

## Structure

- Every topic directory should have a same-name index page.
- Root-level docs should orient the reader before diving into modules.
- Deep module pages should explain responsibilities, data flow, dependencies, and modification risks.
- Avoid empty template sections. If a section has no project evidence, either omit it or say the capability was not found.
- Do not mark generated TODO placeholders as complete content.
- Each project wiki should have `.wiki/wiki-index.json`, rebuilt after explicit wiki updates.
- Each project wiki should have `.wiki/config.json` with `auto_update_after_code_change` defaulting to `false`.
- Content should live under `.wiki/<language>/content`, controlled by `.wiki/config.json`.
- Project-specific aliases, search hints, topic overrides, and risk rules should live in `.wiki/project-aliases.json`, `.wiki/search-hints.json`, `.wiki/topic-overrides.json`, and `.wiki/risk-profile.json`.
- Ignore `.qoder/repowiki`; `.wiki` is maintained from current source code.

## Maintenance

- During ordinary project work, use `.wiki` for orientation before verifying facts in source code.
- Do not update wiki automatically after code changes unless `.wiki/config.json` explicitly enables it.
- For `$simple-project-wiki-update`, prefilter candidate pages before reading wiki content.
- Use source sha256 changes from `.wiki/wiki-index.json` as the final skip/update criterion.
- Do not use mtime alone to skip a wiki page.
- Use citation and topic mapping to find affected pages.
- Create missing pages when new modules, APIs, configs, or workflows need durable documentation.
- Delete or merge pages that only describe removed functionality.
- Do not create wiki changelog files; summarize maintenance in the final response.
- Run `check_wiki_ready.py --strict` before reporting a generated or updated wiki as complete.
- Use `check_wiki_ready.py --strict --recursive` for monorepos.

## Review Checklist

- The wiki exists at `.wiki/zh/content`.
- Or the wiki exists at the configured `.wiki/<language>/content`.
- The wiki config exists at `.wiki/config.json`.
- The wiki index exists at `.wiki/wiki-index.json`.
- Strict readiness passes; no TODO placeholder pages remain.
- Strict readiness passes; no missing `<cite>`, empty `source_refs`, missing cited files, short pages, unindexed pages, or secret-like wiki content remains.
- The root project and every intended subproject have their own wiki.
- `项目概述.md` names the stack, entrypoints, project structure, and major modules.
- `快速开始.md` uses commands and requirements from actual manifests/docs.
- API docs cite controllers/routes/client API wrappers that exist.
- Database/model docs cite schemas, entities, migrations, ORM mappings, or model files.
- Build/deploy docs cite package/build/config files.
- Security docs cite real auth/config/file/network/payment code.
