# Wiki Index Schema

`.wiki/wiki-index.json` is a machine-readable helper for searching and updating wiki pages. It is generated from Markdown content and should be rebuilt after `$simple-project-wiki-init`, `$simple-project-wiki-update`, or any explicit wiki update.

## Location

Each project has its own index:

```text
project/.wiki/wiki-index.json
project/.wiki/<language>/content/**/*.md
```

For monorepos, the root project and each subproject maintain separate indexes.

## Top-Level Fields

Schema version 2 is the current format:

```json
{
  "schema_version": 2,
  "language": "zh",
  "content_root": "zh/content",
  "project_root": "/abs/path/project",
  "project_name": "project",
  "generated_at": "2026-06-05T00:00:00+00:00",
  "generated_by": "simple-project-wiki/scripts/build_wiki_index.py",
  "pages": []
}
```

Readers should still tolerate schema version 1 indexes, but new indexes should be rebuilt as version 2.

## Page Fields

Each `pages[]` item contains:

- `path`: Markdown path relative to `.wiki`, such as `zh/content/架构设计/架构设计.md`.
- `title`: First `#` heading, or file stem if missing.
- `topic`: First directory under `zh/content`, or `root` for root-level pages.
- `summary`: Short text from the first meaningful paragraph after `<cite>` and the table of contents.
- `aliases`: Search aliases derived from title, topic, headings, and cited file stems.
- `tags`: Topic and stack/domain tags derived from page content and cited paths.
- `routes`: HTTP or route-like paths detected from Markdown.
- `api_endpoints`: Same shape as `routes`; kept as a semantic field for API-focused tools.
- `symbols`: File stems and code-like symbols mentioned in the page.
- `config_keys`: Dotted config keys detected in text.
- `risk_flags`: Risk labels such as `auth`, `payment`, `file-io`, `sql`, `deserialization`, `secrets`, or `admin`.
- `source_refs`: Source paths parsed from `<cite>` links and `file://...` links.
- `source_spans`: Source refs plus optional line anchors when present in links.
- `source_fingerprints`: Current metadata for each source ref at index-build time:
  - `path`: normalized source path.
  - `exists`: whether the source file existed.
  - `sha256`: SHA-256 hash when the source exists.
  - `mtime_ns`: file modification time in nanoseconds, for diagnostics and ordering only.
  - `size`: file size in bytes.
- `related_globs`: Directory globs derived from cited source parents (for example `src/main/java/com/demo/*`). `plan_wiki_update.py` treats a changed file matching any glob as an update candidate, so sibling-file changes can flag a page even when the exact file is not directly cited.
- `headings`: Markdown headings in the page, excluding the title, with `{level, title, anchor, line_start, line_end}` so agents can open a relevant section instead of reading the full page.

Project-specific lookup fields can be influenced by sidecar config:

- `.wiki/project-aliases.json`: domain aliases and synonyms used by search.
- `.wiki/search-hints.json`: synonyms, topic hints, and config-key prefixes.
- `.wiki/risk-profile.json`: project-specific risk flags and keywords.

## Search Strategy

Use these fields in order before opening full wiki pages:

1. `routes`, `api_endpoints`, `symbols`, `config_keys`, and `source_refs` for exact lookup.
2. `risk_flags` and `tags` for risk or domain lookup.
3. `title`, `aliases`, `topic`, `headings`, and `summary` for broader orientation.
4. Open only the best page or `headings[].line_start` to `line_end` ranges when possible.
5. Wiki page content only after the index narrows the target set.
6. Source code verification after wiki orientation.

## Maintenance Rules

- Build the index by parsing Markdown, not by asking the model to hand-write JSON.
- Do not include full document bodies in the index.
- Keep source refs exactly as relative paths when possible.
- Rebuild the index after initialization, `$simple-project-wiki-update`, or any explicit wiki page update.
- If a page has no citations, keep `source_refs` empty rather than inventing paths. Strict readiness should then fail until the page is filled with real evidence.
- Use sha256 comparison as the final decision for skipping source reads/page updates.
- Do not use mtime as a final skip criterion; mtime can be stale, preserved, or changed without content changes.
- Treat entity-level fields as lookup hints only; verify exact implementation details in source.
