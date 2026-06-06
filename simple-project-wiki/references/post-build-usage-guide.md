# Post-Build Usage Guide

Use this reference after `.spwiki` has been initialized and filled with source-grounded content.

## Daily Development Protocol

For any project question, analysis, review, or code change:

1. Search the root wiki index.
2. Search the relevant subproject wiki index.
3. Open the smallest set of relevant wiki pages or heading ranges returned by `heading_hits`.
4. Use `source_refs` to jump to source code.
5. Verify all implementation facts in source before answering or editing.
6. Trust source over wiki when they disagree.

## Fast Lookup Commands

Search all discovered wiki indexes:

```bash
python <skill-dir>/scripts/search_wiki.py <project-root> "<keyword or route or class>" --json
```

Plan update candidates after code changes:

```bash
python <skill-dir>/scripts/plan_wiki_update.py <project-root> --changed-file <path>
```

Check whether a wiki is structurally and content-wise ready:

```bash
python <skill-dir>/scripts/check_wiki_ready.py <project-root> --json --strict
```

For monorepos:

```bash
python <skill-dir>/scripts/check_wiki_ready.py <project-root> --json --strict --recursive
```

## Query Routing

- Architecture questions: read root `.spwiki/wiki-index.json`, then `架构设计` pages.
- API questions: search for route, controller, API wrapper, request DTO, or response DTO.
- Data questions: search entity, mapper, XML namespace, table, migration, or model name.
- Config questions: search config key, profile, port, endpoint, package command, or manifest.
- IM protocol questions: search command names, message type constants, WebSocket handlers, client IM modules.
- Risk questions: search `risk_flags`, then verify auth/payment/file/SQL/deserialization source.

## Answer Discipline

When answering from wiki-backed lookup:

- Say which source files were verified when the result depends on implementation details.
- Do not cite wiki as final truth when source code was inspected.
- If only wiki was inspected, say the answer is orientation-only and not source-verified.
- If source changed but wiki did not, recommend `$simple-project-wiki-update` or `/simple-project-wiki-update`.

## Maintenance Triggers

Refresh wiki pages after final code changes that affect:

- Public or internal APIs
- WebSocket protocol or message schema
- Database entities, mapper XML, or persistence behavior
- Authentication, authorization, payment, file I/O, SQL, deserialization, admin review, or secrets handling
- Build, deployment, profiles, ports, external services, or local setup
- Important user workflows or cross-subproject contracts

Do not refresh for:

- Formatting-only changes
- Temporary experiments
- Reverted changes
- Comment-only edits with no durable project knowledge change

## Project Guidance Snippet

Use this in `AGENTS.md` or `CLAUDE.md` after the wiki exists:

```markdown
## Project Wiki Usage

Before broad project search, inspect `.spwiki/wiki-index.json` at the root and relevant subprojects. Use search results and heading line ranges to open the smallest relevant wiki content. Use wiki pages only to navigate; verify implementation facts in current source code. If wiki and source disagree, trust source and treat the wiki as stale. Do not update `.spwiki` unless explicitly requested or `auto_update_after_code_change` is enabled.
```
