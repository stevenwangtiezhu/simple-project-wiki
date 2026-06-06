# Simple Project Wiki Protocol

Use this protocol whenever a project already has `.wiki`, or when the user invokes `$simple-project-wiki-init`, `$simple-project-wiki-update`, or `$simple-project-wiki-search`.

## Daily Project Work

For project access, query, analysis, review, or modification tasks:

1. Check whether the root project or relevant subproject has `.wiki/wiki-index.json` or the configured `.wiki/<language>/content`.
2. If it exists, search the root wiki first, then the relevant subproject wiki. Prefer `search_wiki.py` for keyword, route, symbol, path, config-key, or risk lookups; use returned `heading_hits` to avoid opening full pages.
3. Use the wiki as a fast orientation manual only. Verify implementation facts in current source before answering or editing.
4. If wiki and source disagree, source code wins.
5. Ignore `.qoder/repowiki`; do not copy, migrate, or rely on it.
6. Do not update wiki documents automatically after code changes unless `.wiki/config.json` explicitly sets `auto_update_after_code_change` to `true`.

If `.wiki` is missing during an ordinary task, tell the user they can use `$simple-project-wiki-init`. Do not initialize automatically unless the user invoked that skill or explicitly asked to initialize the wiki.

## Initialization Skill

`$simple-project-wiki-init` means:

- Scan the root project and detected subprojects.
- Run a readiness check for each project.
- If a project already has the core structure, `.wiki/wiki-index.json`, and strict readiness passes, skip it.
- Otherwise create `.wiki/config.json`, sidecar project config files, create a `deep` `.wiki/<language>/content` skeleton, build `.wiki/wiki-index.json`, then generate complete first-version grounded Markdown content in batches.
- A TODO skeleton is not complete. Replace placeholders with source-grounded content before reporting completion.
- Do not overwrite existing wiki pages unless explicitly requested.

## Global Update Skill

`$simple-project-wiki-update` means:

- Scan the current root and subprojects.
- Prefilter likely update targets using `.wiki/config.json`, `.wiki/wiki-index.json`, source refs, changed files when known, topic mapping, and entity-level index fields such as routes, symbols, config keys, tags, and risk flags.
- Use `.wiki/search-hints.json` and `.wiki/risk-profile.json` for project-specific topic/risk routing.
- Compare current source sha256 values with `source_fingerprints` in `.wiki/wiki-index.json`; skip pages only when all associated source hashes are unchanged.
- Treat missing hashes, missing files, new refs, changed sha256 values, unlinked changed files, or project-shape changes as update candidates.
- Directly update stale Markdown pages, create missing pages, delete or merge pages that describe removed functionality, and rebuild `.wiki/wiki-index.json`.
- Report the pages changed and the reason in the final response. Do not write a changelog file.

## Code Change Maintenance

After code edits, do not maintain the wiki unless the user explicitly asks for it or `.wiki/config.json` has `auto_update_after_code_change: true`. When enabled, maintain the wiki only when all of these are true:

- The code change is final and kept.
- Validation is complete enough to report the change as done.
- The change affects behavior, APIs, configuration, data models, architecture, important workflows, security/risk posture, build/deploy commands, tests, or usage.

Do not update wiki for:

- Temporary experiments.
- Reverted changes.
- Unfinished or failed changes.
- Pure formatting or comment-only edits that do not change project knowledge.

## Impact Mapping

Use this order to find affected pages:

1. Run `plan_wiki_update.py` to produce candidate pages without reading the full wiki.
2. Read `.wiki/wiki-index.json` and find pages whose `source_refs` include changed files.
3. Search entity-level index fields (`routes`, `symbols`, `config_keys`, `risk_flags`, `tags`) before opening full pages.
4. Search only candidate `.wiki/<language>/content/**/*.md` pages for changed paths, class/component names, route paths, API names, table/entity names, config keys, command names, and module names.
5. Map change type to topics:
   - Controllers/routes/API wrappers -> `API接口文档` or `API接口层`
   - Entities/schemas/ORM mappings -> `数据库设计` or `数据模型设计`
   - Config/build files -> `配置管理`, `构建与部署`, or `部署与运维`
   - Auth/payment/file/SQL/security-sensitive flows -> `安全与权限` or `安全考虑`
   - Major services/components/views/stores -> `核心模块`, `页面视图组件`, `状态管理系统`, or stack-specific topics
6. Update root overview pages if the change affects project-wide architecture, startup, build, deployment, or cross-subproject contracts.

## Naming Rules

- Use localized directory and page names from `.wiki/config.json` language.
- Use `.wiki/<language>/content` for Markdown content, defaulting to `.wiki/zh/content`.
- Keep a same-name index page in every topic directory, such as `架构设计/架构设计.md`.
- Place `.wiki/wiki-index.json` at the `.wiki` root for each project.
- Place `.wiki/config.json` at the `.wiki` root for each project.

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

## Token-Saving Hash Strategy

- `build_wiki_index.py` stores sha256, mtime, and size for every cited source ref.
- `$simple-project-wiki-update` recomputes sha256 for associated source refs through `plan_wiki_update.py`.
- A page can be skipped only when all associated source sha256 values are unchanged.
- mtime is only a fast diagnostic or sorting signal. Never rely on mtime alone to skip a page.
- Script-side hashing does not consume model tokens, so prefer hashing source refs over asking the model to reread unchanged files.
- Entity-level index fields are lookup hints. They save tokens during discovery, but source code remains the final authority.

## Strict Readiness Gate

`check_wiki_ready.py --strict --recursive` must fail when:

- Required config, index, root pages, or same-name topic index pages are missing.
- A page lacks `<cite>`, source refs, or an index entry.
- A cited source ref no longer exists.
- Template TODO text or placeholder prose remains.
- The substantive body is too short to be useful.
- Secret-like values appear in wiki text.
