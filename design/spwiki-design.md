# .spwiki Index & Retrieval Redesign — Canonical Design

> **Status:** Design proposal. Not implemented. This is the single canonical, self-contained spec for the next-generation `.spwiki` index and retrieval model. It merges and supersedes the three prior design notes (`spwiki-v3-design.md`, `spwiki-v4-design.md`, `spwiki-v3-design-cx.md`), which are retired in favor of this document. No runtime behavior changes until the migration in §16 is executed.
> **Scope:** (1) a short list of confirmed *current* (v2) defects to fix first; (2) a disruptive restructuring of the index from "prose pages → regex-scraped row index" into a **code-entity graph of atomic, evidence-graded fact cards** with **compiled query plans** and a **trust ledger**; the goals are an order-of-magnitude lower query token cost on the expensive query classes **and** measurable, decaying retrieval accuracy.
> **Audience:** Maintainers of the `simple-project-wiki` skill set (this repo). A repo-evolution document — **must NOT be copied into target projects' skills directories** (it is not user-facing skill guidance; it does not belong under `simple-project-wiki/references/`).

This document is fully self-contained: every JSON schema, the `<fact>` grammar, and every gate rule are stated here in full. There are no "see the other doc" deferrals.

---

## 0. How to read this document

- **§1** is the immediate, low-risk work: confirmed v2 bugs, fixable today without any schema change. Ship these first.
- **§2–§3** state the problem and the thesis.
- **§4–§13** are the full target design (the "graph model"): invariants, artifacts, every schema, the evidence/accuracy model, compiled queries, the trust ledger.
- **§14–§19** are execution: the gate, the per-script change contract, costs/risks/rejected ideas, the strangler-fig migration, and the **empirical validation plan** that must produce real numbers before the large surgery.

Terminology: the current shipped model is called **rows** (`index_model: "rows"`, the flat `pages[]` `wiki-index.json`). The new model is called **graph** (`index_model: "graph"`). The graph model is **opt-in**; rows remains the default so existing wikis are untouched.

---

## 1. Phase 0 — confirmed current (v2) defects to fix first

These were verified against the live source tree (file:line evidence below). They are **independent of the redesign**, small, and individually testable. Fix and ship them before any schema work — they improve correctness immediately and de-risk everything after.

### 1.1 Init skill forces Chinese, overriding the system-language default — **high (multilingual correctness)**
`simple-project-wiki-init/SKILL.md:35` instructs running `create_wiki_skeleton.py … --language zh` unless the user asks otherwise. But the script default is detect-then-lock (`create_wiki_skeleton.py:229`, `args.language or detect_system_language()`), and the invariant (`AGENTS.md`, `agent-operation-manual.md:71`) is "no `--language` ⇒ system language, then locked." The skill contradicts the invariant and silently forces zh.
**Fix:** remove the default `--language zh` from the init skill; pass `--language` only when the user names a language.

### 1.2 Exact-phrase search scoring compares against the expanded token soup, not the raw query — **high (search quality)**
`search_wiki.search()` builds `expanded_query = " ".join(tokens)` from `expand_query_terms` output (tokens are deduped and **sorted by length**, `wiki_common.tokenize:618-622`), then passes it as `query` to `score_page` (`search_wiki.py:191,202`), where the high-value exact bonus is `query_l in text` (`search_wiki.py:125`). The reordered join almost never equals the user's phrase, so the exact-phrase bonus is effectively dead for multi-word queries.
**Fix:** pass the **raw** query for the phrase bonus; use expanded tokens only for per-token scoring.

### 1.3 Short ASCII tokens substring-match inside unrelated words — **medium (false positives)**
`score_page` uses bare `token in text` (`search_wiki.py:129`). Short tokens like `id`/`db` match inside `guide`/`validate`, inflating score and reasons.
**Fix:** require word-boundary match for sub-3-char ASCII tokens; **keep** CJK bigram substring behavior (intentional in `tokenize`).

### 1.4 Dead documentation reference — **medium (doc defect)**
`AGENTS.md:60` points to `references/Codex-adapter.md`, which does not exist (the file is `claude-code-adapter.md`). Likely residue of a Claude→Codex search/replace.
**Fix:** repoint to the existing adapter, or add the named file.

### 1.5 Generation prompt is hard-coded Chinese — **medium, high for non-zh wikis**
`wiki-generation-prompt.md` bakes `.spwiki/zh/content` (lines 6,10-11,81) and a `中文` style rule (line 72). A weak agent initializing an `en`/`kr` wiki follows it verbatim → Chinese pages in the wrong content root, contradicting the locked config language.
**Fix:** parameterize to `<language>`/`<content_root>` from `config.json`; state that page language must match config. (Same applies to the Chinese-heavy examples in `wiki-structure.md:52-142`, lower severity.)

### 1.6 Two small, optional v2 wins worth folding in
- **Kotlin coverage gap:** `scan_project.py:341-349` adds `kotlin` to the stack, but `default_topic_keys` (`wiki_common.py:368-389`) never keys on it → pure-Kotlin projects get only the generic scaffold. Add `kotlin` to the backend stack set.
- **`source_spans` is dead data:** generated (`build_wiki_index.py:110,295`) and documented (`wiki-index-schema.md:51`) but consumed by nothing. It is simply deletable. (Do not confuse it with the *live* change-detector `source_fingerprints`, which the graph model migrates into per-card baselines + `fingerprints.json` — §8/§17.)

> Phase 0 is **prerequisite**, not part of the schema break. The graph model below assumes 1.1–1.5 are fixed.

---

## 2. Why the redesign — the ceilings of the rows model

The current model is **"prose pages → regex-scraped weak row index."** Three structural ceilings follow that no weight-tuning removes:

1. **The retrieval unit is the page.** Even with heading line-ranges, an agent ultimately *opens a page*. "How does login work" spans the controller page + security page + config page → three reads.
2. **The index is a derivative of prose.** `routes`/`symbols`/`config_keys` come from regexes (`build_wiki_index.py:32-39,239-253`) guessing whatever the model happened to write. Accuracy is bounded by narrative style, and **truth is assumed, never checked** — a page that says "validates the token" over code that never validates passes every current check.
3. **A query is many round-trips.** `search_wiki.py --json` is one verbose round-trip per call; the index reloads the full `pages[]` each time; the most expensive real questions ("what breaks if I change X", "how does X work end-to-end", "where is X configured/tested/secured") force several lookups plus agent-side assembly.

There is also a **fourth, accuracy ceiling** the rows model cannot address at all: the index has no notion of *whether a claim was ever true* or *against what source state it was last confirmed*, so stale and wrong documentation are indistinguishable from correct documentation at query time.

The redesign changes the **retrieval unit**, the **physical data model**, and adds a **verification substrate** — not just the weights.

---

## 3. Thesis and the model in one picture

> **Thesis.** Make `.spwiki` a **store of *evidenced* facts with compiled query plans and a decaying trust ledger**, not a store of *asserted* prose to be re-verified by hand. Then: the retrieval unit is an atomic fact card bound to an exact source range; accuracy is measured at build time with machine-checkable evidence; the expensive structural query classes resolve in one fetch; and re-verification is a one-region hash check, not a page re-read.

Three pillars, each tied to a user-stated priority:

- **Pillar A — Code-entity graph + atomic fact cards (efficiency, base model).** Pages decompose into atomic cards, each bound to a `path#Lx-Ly` range; cards link to real code entities (symbols/routes/config keys) forming a graph; a tiny load-once `map.json` lets the agent navigate in-context; a postings/BM25 index replaces the O(pages×tokens×fields) scan. This is the order-of-magnitude cut for normal lookups.
- **Pillar B — Compiled query plans (efficiency leap on the expensive classes).** The structurally-common query *shapes* (blast-radius, how-it-works, typed-neighbors) are precompiled into **answer bundles** — deterministically-selected sets of existing card ids — returned in one fetch with no agent-side traversal. A flag-based **structured query** path (`--entity/--relation/--route/--config`) gives a precise, false-positive-free alternative to free text.
- **Pillar C — Evidence grading + trust ledger + freshness decay (accuracy).** Each card is admitted only with machine-checkable **evidence** (structural entailment + dual-source corroboration), graded `verified`/`orientation`/`suspect`; a **ledger** records the source state each card was last verified against; search surfaces a **freshness** state per hit so stale/suspect knowledge is never presented as fresh truth, and re-verification costs one region hash.

The whole picture:

```text
authored page (<fact> blocks)
        │  build: deterministic extraction + entailment + corroboration
        ▼
   ┌────────────── .spwiki/graph/ ──────────────┐
   │ map.json      load-once roster + answers     │  HOT  (search)
   │ postings.json inverted index (BM25)          │  HOT
   │ cards.json    atomic facts + evidence + grade │  HOT (statement/src/grade)
   │ entities.json code-entity graph + typed edges │  HOT (for structured query)
   │ bundles.json  compiled query plans            │  WARM (structural queries)
   │ ledger.json   per-card verification state      │  COLD (update + re-verify)
   │ concepts.json learned co-occurrence clusters   │  optional
   └─────────────────────────────────────────────┘
        │  query: map → (structured|free-text|bundle) → cards (+freshness) → 1 source range if needed
        ▼
   answer assembled from cards, each pointing at exact source to verify
```

**Honest scope of the win.** Pillar A delivers the big token cut for ordinary lookups (≈4× vs the rows model — see §13). Pillars B/C deliver the leap on the *expensive structural query class* and on *accuracy*; for a single trivial fact lookup the token count is roughly at parity with a graph-only model — the added value there is the *graded, fresh* accuracy signal, not fewer tokens. The document never claims another 4× on trivial lookups.

---

## 4. Invariant compliance matrix

The eight hard invariants (from `AGENTS.md`/`CLAUDE.md`). The most dangerous misreading is "a verification ledger means we now trust the wiki" — row 1 is the contract that forbids it.

| # | Invariant | Stance |
|---|-----------|--------|
| 1 | Source is final authority; `.spwiki` is navigation only | **Strengthened, with a hard rule.** Every card/evidence item carries a `path#Lx-Ly` to open. The ledger records *when/against-what-source-state* a claim was last confirmed **so re-verification is cheap, never so it can be skipped.** `fresh` means "cited bytes identical to last check → a one-hash confirm suffices," not "trust the text." `verified` is a build-time evidence grade, not a license to cite the wiki as truth. |
| 2 | No project-specific terms hard-coded in Python | Preserved. Edge relations, evidence kinds, and bundle shapes are a *fixed generic* vocabulary; entities/cards/corroboration are extracted from project content; concept clusters are learned from the corpus. Domain aliases/risks/hints stay in sidecars. |
| 3 | Language chosen once, locked, per-language `content_root` | Preserved. All graph artifacts live under language-neutral `.spwiki/graph/`; card/statement text is the config language; structured-query keys are language-neutral entity ids; map localizes topic titles via `localized_topic_title`. |
| 4 | UTF-8; gate fails on mojibake | Preserved. All graph JSON via `write_text_utf8`/`ensure_ascii=False`; mojibake check extends to card/ledger/bundle text fields. |
| 5 | sha256 final change detector; mtime diagnostic | Preserved & deepened. Whole-file sha256 stays the authoritative file-change signal; `region_hash` is an additional narrower signal; freshness derives from both; mtime stays a re-hash skip gate only. |
| 6 | Pure stdlib Python 3, no deps, no build step | Preserved. Postings/BM25 = dicts + arithmetic; traversal = BFS over an adjacency dict; corroboration = set intersection; entailment = `re`/substring; hashing = `hashlib`; freshness = hash compare. No third-party libs. |
| 7 | Strict readiness gate non-negotiable | **Extended** with graph + accuracy checks (§14). Unentailed `verified` cards, unlabeled contradictions, dangling evidence ranges, bundle-provenance drift, and region-hash inconsistency all fail the gate. |
| 8 | Four sibling dirs; `../simple-project-wiki` resolution; no umbrella command | Preserved. Only files inside `.spwiki/` change; no new command entry point; structured query is a *flag* on the existing `search_wiki.py`. |

---

## 5. Artifact layout

```text
.spwiki/
├── config.json                 # adds "index_model":"graph", "schema_version":3, "accuracy_profile":"corroborated"
├── topic-overrides.json        # unchanged sidecars
├── project-aliases.json
├── search-hints.json
├── risk-profile.json
├── <language>/
│   └── content/…*.md           # authored pages, now carrying <fact> blocks (§9) — unchanged location
└── graph/                      # the new index; replaces the monolithic wiki-index.json (kept as compat shim during migration)
    ├── map.json                # HOT, load-once: roster + topic tree + answers tier (highest-trust inline cards)
    ├── entities.json           # HOT (structured query): node table + typed edges
    ├── cards.json              # HOT: atomic fact cards + per-region baseline hashes + evidence[] + grade
    ├── postings.json           # HOT: inverted index (BM25)
    ├── bundles.json            # WARM: compiled query plans (blast-radius / how-it-works / typed-neighbors)
    ├── fingerprints.json       # COLD: per-FILE {sha256,size,mtime_ns,exists} — change-detector for plan_wiki_update + missing_cited_refs
    ├── ledger.json             # COLD: per-card verification audit (verified_at, grade-at-build, evidence_count) — history/audit only
    └── concepts.json           # optional: learned co-occurrence clusters (weak semantic expansion)
```

**Three temperatures** (this is *why* the model can carry more metadata while the search hot path shrinks — audit/update data lives cold):
- **Hot (search):** `map.json` → `postings.json` / structured query → `cards.json`. Freshness is computable here because each card carries its own baseline `file_sha256`+`region_hash` (§6.4); the hot path re-hashes only the cited files of the hits actually returned (bounded by `--limit`). Never loads `ledger.json` or bundles.
- **Warm (structural queries):** `bundles.json`, fetched only for impact / how-it-works / neighbor queries.
- **Cold (update + re-verify):** `fingerprints.json` (per-file change detection, the `source_fingerprints` successor read by `plan_wiki_update.py` and `missing_cited_refs`) and `ledger.json` (verification audit/history). Neither is on the hot path.

> **Resolved (red-team Theme 1/3).** Baseline hashes are denormalized onto each card so freshness needs no ledger read on the query path; the per-FILE change-detector fields the cold consumers require (`exists`/`size`/`mtime_ns`) live in `fingerprints.json`, NOT the per-card ledger (whose shape cannot serve them). See §6.4, §6.7, §20.

For large monorepos `map.json` is **layered**: a root map lists subprojects with their own `graph/map.json` paths; the agent loads the root map (≪ everything) and descends on demand → 2 loads, not N searches.

---

## 6. Full JSON schemas

All schemas below are complete and authoritative. Field order in real files is not significant. All examples use a Spring/JWT login flow for consistency.

### 6.1 `config.json`

```jsonc
{
  "language": "zh",
  "content_root": "zh/content",
  "profile": "deep",                       // depth profile (unchanged): light|balanced|deep
  "index_model": "graph",                  // "rows" (current default) | "graph" (this design)
  "accuracy_profile": "corroborated",      // "none" | "structural" | "corroborated"  (grading strength, §10)
  "auto_update_after_code_change": false,
  "token_strategy": "prefilter_batch",
  "index_schema_version": 3,               // bumped 2 -> 3
  "strict_ready_required": true
}
```
`index_model` defaults to `"rows"`; a project opts into the graph model explicitly (`--index-model graph` at init, or re-init). `accuracy_profile` selects how strict grading is: `none` = no evidence (graph model without Pillar C), `structural` = entailment only, `corroborated` = the two-source rule (§10).

### 6.2 `map.json` — load-once navigator (+ answers tier)

Target size **1–3 KB for a medium project.** No card bodies (except the small answers tier), no fingerprints, no per-line data.

```jsonc
{
  "schema_version": 3,
  "kind": "map",
  "project_name": "demo",
  "language": "zh",
  "generated_at": "2026-06-07T00:00:00+00:00",   // stamped at build write time; display/order only
  "project_summary": "≤300 char one-paragraph orientation, lifted from the overview page lead <fact>.",
  "stack": ["spring-boot", "mybatis"],
  "topic_tree": [
    { "key": "security", "title": "安全与权限", "page_id": "p_security",
      "card_count": 12, "children": ["认证与授权", "安全配置"] }
  ],
  "entity_roster": {
    // name -> id, plus kind. Names ONLY here — no source/hash. This is what the agent matches intent against in-context.
    "symbol": { "AuthService": "e_s_authservice", "JwtUtil": "e_s_jwtutil" },
    "route":  { "POST /login": "e_r_post_login", "GET /users": "e_r_get_users" },
    "config": { "jwt.expire": "e_c_jwt_expire" }
  },
  "answers": [
    // NAVIGATION POINTERS to the N highest-degree verified cards — NOT a zero-fetch answer surface.
    // Inlines {card_id, src} ONLY: no statement text, no grade. The agent must fetch the card (cards.json)
    // and recompute freshness before relying — preserving the §11.3 'pointer, not answer' firewall and
    // invariant 1 (a card's text is never served as actionable truth without a freshness check).
    // Selection = entity-degree among verified cards (freshness is constant-at-build, so it is NOT a tiebreak; see §20).
    { "card_id": "c_8f2a", "src": "src/auth/AuthService.java#L40-L88" }
  ],
  "counts": { "entities": 84, "cards": 211, "pages": 19, "verified": 140, "orientation": 60, "suspect": 11 }
}
```

> **Resolved (red-team Theme 2).** The original answers tier inlined `statement`+`grade:verified` and §11/§12 billed it as zero-fetch — which, after any post-build drift, served a stale assertion as verified truth (the §16.3-rejected claimed-answer surface, in the over-trust direction). It is now a pointer list: `{card_id, src}` only. The "hottest-fact" win becomes "one fetch + one region-hash confirm" (still far cheaper than a page read), not "zero fetch." See §11.4, §20.

### 6.3 `entities.json` — the code-entity graph

```jsonc
{
  "schema_version": 3,
  "kind": "entities",
  "nodes": {
    "e_s_authservice": {
      "kind": "symbol",                    // symbol|route|config|region|file
      "name": "AuthService",
      "subkind": "class",                  // class|function|method|hook|const|controller|… (best-effort)
      "src": "src/auth/AuthService.java",  // file-level for a whole-file symbol; region nodes carry #Lx-Ly
      "origin": "source",                  // "source" (verified by scan) | "text" (only mentioned in prose)
      "region_hash": null,                 // null for whole-file nodes; sha256 of the byte range for region nodes
      "card_ids": ["c_8f2a", "c_1b03"],
      "topic": "security",
      "edges": [
        { "rel": "calls", "to": "e_s_jwtutil" },
        { "rel": "reads-config", "to": "e_c_jwt_expire" },
        { "rel": "serves-route", "to": "e_r_post_login" }
      ]
    },
    "e_r_post_login": {
      "kind": "route", "name": "POST /login", "method": "POST", "path": "/login",
      "src": "src/auth/AuthController.java#L22-L31", "origin": "source",
      "region_hash": "9c1e7a…", "card_ids": ["c_8f2a"], "topic": "security", "edges": []
    },
    "e_c_jwt_expire": {
      "kind": "config", "name": "jwt.expire",
      "src": "src/main/resources/application.yml#L14-L14", "origin": "source",
      "region_hash": "44ab…", "card_ids": ["c_1b03"], "topic": "configuration", "edges": []
    }
  }
}
```
**Fixed edge-relation vocabulary** (generic, language-neutral — invariant 2): `calls`, `reads-config`, `writes-config`, `serves-route`, `persists`, `extends`, `implements`, `imports`, `test-covers`, `documented-by`, `risk`. Edges are best-effort navigation hints, never authoritative. `origin:"source"` (verified by the scanner, §15) outranks `origin:"text"` (only mentioned in prose).

### 6.4 `cards.json` — atomic fact cards with evidence

```jsonc
{
  "schema_version": 3,
  "kind": "cards",
  "cards": {
    "c_8f2a": {
      "statement": "登录使用 JWT，token 在 AuthService.login() 中签发，有效期由 jwt.expire 配置控制。",
      // regions[] is the authoritative citation list — supports MULTI-SRC cards (§9). Each entry carries its
      // OWN baseline hashes so freshness is computable on the hot path WITHOUT loading the ledger (§5, §11.2).
      "regions": [
        { "src": "src/auth/AuthService.java#L40-L88",   // MANDATORY, MUST carry a line range
          "file_sha256": "ab12…",                        // whole-file baseline at build (raw bytes, §8)
          "region_hash": "9c1e7a4f…",                    // baseline hash of the cited byte range (§8)
          "region_bytes": 1180 }                         // length, so a relocation search can re-find the region (§8 drift rule)
      ],
      "entities": ["e_s_authservice", "e_c_jwt_expire", "e_r_post_login"],
      "topic": "security",
      "page_id": "p_security",
      "page_anchor": "认证与授权",
      "risk_flags": ["auth"],
      "grade": "verified",                            // verified | orientation | suspect  (§10) — SINGLE source of truth; ledger mirrors it
      "evidence": [
        { "kind": "defines-symbol", "src": "src/auth/AuthService.java#L40-L88",
          "region_hash": "9c1e7a…", "polarity": "support", "detector": "structural",
          "note": "AuthService.login declared in region" },
        { "kind": "test-covers", "src": "src/test/auth/AuthServiceTest.java#L18-L33",
          "region_hash": "be77…", "polarity": "support", "detector": "corroborating",
          "note": "test references AuthService.login" }
      ]
    }
  }
}
```
A card is **the minimal independently-citable assertion**. "A page" becomes `render([card_ids for that page])`. An answer to "how does login work" = ~5 cards (~800 chars) spanning 3 pages, **zero pages opened**, each card pointing at a ~40-line source range. `grade` and `evidence` are Pillar C (§10).

> **Resolved (red-team Theme 1).** `src`+`region_hash` became `regions[]` so a single card may cite multiple files/ranges (the §9 multi-src grammar) with per-region baselines; each region carries `file_sha256` (so the hot path can compute `fresh` without the ledger) and `region_bytes` (so the §8 drift rule can relocate a moved region). `grade` here is the **single source of truth**; `ledger.json` only mirrors it for audit (§6.7), and the gate cross-checks the two (§14 `ledger_grade_mismatch`).

### 6.5 `postings.json` — inverted index

Replaces the rows-model O(pages×tokens×fields) substring scan with postings intersection + BM25-style scoring.

```jsonc
{
  "schema_version": 3,
  "kind": "postings",
  "doc_count": 211,                        // number of cards (BM25 N)
  "avg_doc_len": 18.4,                      // avg card token length (BM25 avgdl)
  "df": { "jwt": 7, "login": 5, "token": 9 },
  "postings": {
    // term -> [ [target_id, field_code, term_freq], … ]
    // field_code: 0=statement 1=entity-name 2=route 3=config 4=topic 5=risk 6=page-title 7=heading
    "jwt":   [["c_8f2a", 0, 2], ["c_1b03", 0, 1], ["e_s_jwtutil", 1, 1]],
    "login": [["c_8f2a", 0, 1], ["e_r_post_login", 2, 1]]
  }
}
```
Tokenization reuses `wiki_common.tokenize` (incl. CJK bigrams) verbatim. Field codes carry the rows-model weight intent as BM25 field boosts. Enables what the rows model cannot: boolean, field-scoped, and negated queries (`auth -test`, `route:/login`).

### 6.6 `bundles.json` — compiled query plans (Pillar B)

```jsonc
{
  "schema_version": 3, "kind": "bundles",
  "blast_radius": {
    "e_s_jwtutil": {
      "depth": 2,
      "card_ids": ["c_8f2a", "c_1b03", "c_77e1"],
      "entity_ids": ["e_s_authservice", "e_r_post_login", "e_c_jwt_expire"],
      "generated_from": "entities.json@<sha>"   // provenance; regenerated whenever the graph changes
    }
  },
  "how_it_works": { "e_s_authservice": { "card_ids": ["c_8f2a", "c_1b03"] } }
}
```
A bundle is a **deterministically-selected set of existing card ids produced by a graph traversal** — no generated prose, no paraphrase. It is the precompiled result of a SELECT, not a stored answer (the firewall that keeps it invariant-1-clean — §12.2). Regenerated whenever the graph topology changes (the `generated_from` provenance hash over `entities.json`); bounded to top-degree entities, the rest traverse on demand. Bundle **membership** is a pure function of `entities.json` (edge topology + each node's `card_ids`), so the entities-hash provenance is sound for membership; per-member **grade/freshness** are NOT cached in the bundle — the agent resolves them live from `cards.json` at fetch (§11.4), so a stale grade can never reach the agent via a bundle. (Card deletion changes `entities.json` → provenance mismatch → regen, so dangling members are caught.)

### 6.7 `ledger.json` — per-card verification audit (Pillar C, COLD)

Audit/history only. The card's authoritative grade and baseline hashes live in `cards.json` (§6.4); the ledger **mirrors** the grade for the update/re-verify path and records when each card was last verified. It does **not** drive freshness (that is computed on the hot path from `cards.json`, §11.2) and it does **not** serve the per-file change detector (that is `fingerprints.json`, §6.7b).

```jsonc
{
  "schema_version": 3, "kind": "ledger",
  "cards": {
    "c_8f2a": {
      "verified_at": "2026-06-07T00:00:00+00:00",   // provenance/display only — NOT a freshness input
      "grade": "verified",                            // MIRROR of cards.json grade; gate fails on mismatch (§14 ledger_grade_mismatch)
      "evidence_count": { "support": 2, "contradict": 0 }
    }
  }
}
```
`verified_at` is stamped from the build's own clock and used only for display ordering (avoids `Date.now()` non-determinism in scripts). Freshness is computed from **hashes, not time** (§11.2).

### 6.7b `fingerprints.json` — per-FILE change detector (COLD; the `source_fingerprints` successor)

The rows model stored `source_fingerprints` per page; the cold consumers (`check_wiki_ready.missing_cited_refs`, `plan_wiki_update.old_fingerprint_map`/`current_fingerprint`) need a per-FILE table keyed by path with `exists`/`size`/`mtime_ns` — fields the per-card ledger cannot provide. v-graph keeps that contract in its own artifact:

```jsonc
{
  "schema_version": 3, "kind": "fingerprints",
  "files": {
    // path -> the same fields rows-model source_fingerprints carried, so both cold consumers port over directly.
    "src/auth/AuthService.java": { "sha256": "ab12…", "size": 4821, "mtime_ns": 1733500000000000000, "exists": true },
    "src/main/resources/application.yml": { "sha256": "44ab…", "size": 612, "mtime_ns": 1733400000000000000, "exists": true }
  }
}
```
`mtime_ns` powers the build's "skip re-hash when size+mtime unchanged" shortcut (already proven in `plan_wiki_update.current_fingerprint`); `sha256` is the authoritative whole-file change detector (invariant 5); `exists:false` is what `missing_cited_refs` keys on for the strict gate.

> **Resolved (red-team Theme 3).** The original §6.7 ledger stored `file_sha256`/`region_hash` and was named the relocation target for `source_fingerprints` — but its per-card shape lacks `exists`/`size`/`mtime_ns` and is not path-keyed, so neither cold consumer could read it. Split into (a) `fingerprints.json` (per-file, serves the change-detector contract verbatim) and (b) `ledger.json` (per-card audit). See §20.

### 6.8 `concepts.json` — learned weak-semantic expansion (optional)

```jsonc
{
  "schema_version": 3, "kind": "concepts",
  "clusters": {
    "login":  ["authentication", "jwt", "token", "认证"],
    "refund": ["payment", "wallet", "提现"]
  }
}
```
Built by counting term co-occurrence within cards (PMI-style, pure arithmetic) — learned from *this* corpus, so not hard-coded vocabulary (invariant 2). Used as a *low-weight* query-expansion layer under explicit sidecar synonyms (`expand_query_terms`). Closes part of the no-embeddings gap without a dependency. Recommended for `deep`+`graph`.

---

## 7. The retrieval unit and why it beats pages

The page is replaced by the **card** as the unit of retrieval, and by the **entity** as the unit of navigation. Three structural properties follow that the rows model cannot reach:

- **Cross-page assembly.** A card is independent of page layout, so one answer is assembled from cards across many pages — page-bound retrieval cannot do this.
- **Region-level precision.** Every card carries `path#Lx-Ly`, so the agent opens a ~40-line range, not a page.
- **One-load navigation.** `map.json` is small enough to sit in context; the agent matches intent against the roster in-context (this is also how semantic recall happens without embeddings) and then issues one precise fetch.

---

## 8. `region_hash` — region-level change detection

The single structure that makes **retrieval cheap and update precise** at once, and the freshness primitive for Pillar C. (Note: this replaces the live per-file change detector `source_fingerprints`, now `fingerprints.json` §6.7b — NOT the already-dead `source_spans`, which is simply deleted, §1.6.)

**Definition — one byte normalization for BOTH hashes (pinned).** To make whole-file and region hashes commensurable, both are computed over the **same** byte stream:
```
canonical_bytes(file) = utf-8 encoding of  normalize_newlines( decode_utf8_sig( raw_file_bytes ) )
                        # decode utf-8-sig (strip BOM), CRLF/CR → LF, re-encode utf-8. NO errors='ignore'.
file_sha256  = sha256( canonical_bytes(file) )                       # supersedes raw-byte sha256_file for graph mode
region_bytes = the lines x..y slice of canonical_bytes(file)         # inclusive
region_hash  = sha256( region_bytes )
```
This is a **deliberate, documented change** from the rows-model raw-byte `sha256_file` (which strips no BOM and does not normalize newlines): in graph mode both signals must use `canonical_bytes` or a BOM/CRLF-only churn could make `file_sha256` change while `region_hash` matches (or vice-versa). `errors='ignore'` is **forbidden** here — dropping invalid bytes could leave a region_hash unchanged after a real in-region edit (false `region-stable`, the over-trust direction). The build and the live re-verify path **MUST** call one shared routine; §14 adds a self-consistency cross-check. Whole-file `file_sha256` remains the authoritative file-change signal (invariant 5); `region_hash` is an **additional, narrower** signal.

- **Query use.** Cards/entities give the exact `path#Lx-Ly` → one precise read.
- **Update use.** `plan_wiki_update` recomputes `region_hash` only for changed files' cards: file sha256 unchanged ⇒ all its cards unchanged (fast path); file changed ⇒ a card is stale **only if its region changed** (edits elsewhere in the file leave it untouched).
- **Re-verify use.** A card whose file changed but whose `region_hash` matches is `region-stable` → confirm by hashing one region, no source re-read (§11).

**Line-drift rule — guards BOTH directions (corrected).** If earlier lines shift, the absolute range `[x..y]` now addresses *different* source lines. Two hazards, both handled:
- *Mismatch direction (under-trust, safe):* a drift-induced `region_hash` mismatch may only *raise* attention (mark stale), never *suppress* an update — it can never cause a missed change.
- *Match direction (OVER-trust, the dangerous one):* a raw offset `[x..y]` whose bytes coincidentally equal the stored `region_hash` after the whole file changed (common for 1-line citations, import blocks, repeated getters) must **not** be blindly trusted as `region-stable`. Rule: when `file_sha256` changed, before declaring `region-stable`, **relocate** the region by searching the current file for the stored `region_bytes` (length recorded in `cards.json regions[].region_bytes`, §6.4): (a) found at the same offset → `region-stable`; (b) found at a *different* offset → new state **`region-moved`** (cheap to re-point, but the `src` line numbers are now wrong and must be rewritten on next build); (c) not found → `stale`. This closes the §11.2 over-trust hole that the old "downgrade-on-positive-match only" wording explicitly authorized.

---

## 9. `<fact>` syntax

The page-level `<cite>` discipline is extended to **sentence-level `<fact>`** blocks, from which the build extracts cards **deterministically** (not by regex-guessing prose).

```markdown
## 认证与授权

<fact src="src/auth/AuthService.java#L40-L88"
      asserts="symbol:AuthService.login; route:POST /login; config:jwt.expire"
      risk="auth">
登录使用 JWT，token 在 login() 中签发，有效期由 jwt.expire 配置控制。
</fact>

<fact src="src/auth/AuthController.java#L22-L31">
登录入口是 POST /login，由 AuthController.login 处理。
</fact>
```

**Grammar & rules:**
- `src` **required** and **must include a line range** (`#Lx-Ly` or `#Lx`). A `<fact>` without a range is a gate failure (stricter than the current file-only `<cite>`, which the generation prompt allows at `wiki-generation-prompt.md:56`).
- Multiple `src` allowed, space-separated (`src="a.py#L1-L9 b.py#L4-L8"`) → one card with multiple `regions[]` (§6.4). Safe to space-split because a `path#Lx-Ly` token contains no spaces.
- `asserts` (optional): **semicolon-separated** typed claims (`symbol:`/`route:`/`config:`/`table:`). Semicolon — not space — because a route value contains a space (`route:POST /login`), so a space-split would mangle it into `route:POST` + an orphan `/login`. Each claim is `type:value`, value trimmed. The build **checks each** against the cited region and **searches the project for a corroborating second site** (§10). A malformed `asserts` (no `:`, unknown type) is a loud gate failure (`fact_assert_unparseable`, §14), never a silent downgrade.
- Omitting `asserts` ⇒ the build infers candidate claims by matching statement tokens against the **scan-built entity roster** (§6.2/§15), not against name-shape regexes — so a lowercase method like `login` or a CJK-embedded identifier is still recognized. Inferred-only cards can reach `orientation`, rarely `verified`.
- `asserts` is **never trusted blindly** — an `asserts="symbol:Foo"` whose symbol is absent from the cited region yields a `contradiction` and a `suspect` card. Authors cannot fake a grade.
- `risk="auth payment"` optional, space-separated; merged with `risk-profile.json` matching.
- Body is one assertion in the **config language** (invariant 3). One `<fact>` = one card.
- Page-top `<cite>` remains valid and required (back-compat). In the graph model, a **non-exempt** content page that yields **zero** cards fails the gate — the graph-model analogue of a TODO skeleton. **Exempt:** the required root_docs pages (Overview / Quick Start / Troubleshooting) and any page carrying an explicit `<!-- spwiki:orientation -->` marker — these are legitimately prose and need not anchor a line-range fact (see §14 `pages_without_facts`).

> **Resolved (red-team Theme 4).** `asserts` was space-separated yet its own route value contains a space — ambiguous; now semicolon-separated with a hard `fact_assert_unparseable` gate. `pages_without_facts` would have made the gate *unsatisfiable* for required prose root pages (required to exist, rejected for having no fact) — now exempted. No-`asserts` inference is pinned to the scan entity roster instead of the suffix-only `SYMBOL_RE` that misses `login`. See §20.

---

## 10. Pillar C(1) — the evidence model & grading (accuracy)

Accuracy is **evidence-graded**, not boolean. An evidence item is a typed, located, machine-checkable support-or-contradiction for a card's claim (schema in §6.4).

**Fixed, generic evidence-kind vocabulary** (invariant 2):

| kind | polarity | stdlib detection |
|------|----------|------------------|
| `defines-symbol` | support | asserted symbol occurs as a *declaration* **in `region_bytes` of the cited region** (per-language declaration regex anchored to the symbol name — NEW per-language work, §15; the *technique* mirrors `scan_project`'s per-language regex probes but is **not** a reuse of `detect_dynamic_entrypoints`, which is a whole-file entrypoint sniffer). A name occurrence that is not a declaration yields at most `references-symbol`, never `defines-symbol`. |
| `references-symbol` | support (corroborating) | symbol *used* (non-declaration) at a site **in a different file** from the structural support |
| `declares-route` | support | route literal/annotation present in the cited region |
| `binds-config` | support / contradict | config key read/written in region. **contradict only** when the card's `asserts="config:K"` names a key K that is absent from the project's scan-built config inventory (§15) — never from bare grepping arbitrary regions |
| `test-covers` | support (corroborating) | a test file references the asserted symbol/route |
| `call-site` | support (corroborating) | another entity's region (different file) calls the asserted symbol (from `calls` edges) |
| `risk-keyword` | **support-only (weak)** | risk term from `risk-profile.json` present in region. **May NEVER, by itself, produce a `contradict`/`suspect`** — lexical presence of `auth` is equally consistent with "does auth" and "does NOT do auth" (it appears in comments, imports, identifiers). Support signal only. |
| `author-fact` | support | the author wrote it in `<fact>` (always present; weakest alone) |
| `contradiction` | contradict | a **structural** opposition only — currently: (a) `binds-config` contradict (asserted `config:K` absent from the config inventory), or (b) an asserted `route:`/`symbol:` absent as a declaration anywhere in the scan inventory. Bare lexical presence is NOT a contradiction source. |

**Deterministic grading rule** (selected by `accuracy_profile`):
- `verified` ⟺ **for the same asserted claim**, ≥1 `support` from a **structural** detector (`defines-symbol`/`declares-route` in the cited region) **AND** ≥1 `support` from an **independent corroborating** site, where *independent* means **a different file** (not merely a different line range — a sibling method in the same file/class/commit carries no independent information). This is the **two-source rule** (`corroborated` profile). The two signals must reference the **same** asserted token (both about `symbol:AuthService.login`), not two different tokens that each happen to exist. Under `structural` profile, the structural support alone yields `verified`.
- `orientation` ⟺ only `author-fact`, a single structural mention, or two signals about *different* tokens; plausible but uncorroborated.
- `suspect` ⟺ **any** `contradict` evidence present (which, per the table, is now a *structural* opposition, not a lexical hit), regardless of support count. Surfaced loudly; never silently dropped.

This is the core accuracy gain: a card claiming behavior the code does not exhibit either fails to reach `verified` (no same-claim cross-file corroboration) or is flagged `suspect` (structural contradiction) — neither of which the rows model can detect.

> **Honest bound (must never be overstated).** This is *structural* entailment — "the named symbol/route/key is declared in the cited region AND the same token is independently corroborated in another file." It is **not** semantic proof; a card asserting a *relationship between two entities that both exist* can still be wrong about the relationship and reach `verified`, and a `verified` card can be subtly wrong about *behavior*. The grade **narrows** the error surface and flags the worst cases; it does **not** remove the agent's final source check (invariant 1). For relational claims, prefer an `asserts` whose corroborating site contains *both* tokens (e.g. B referenced inside A's declared region) so the relationship — not just co-existence — is what got corroborated.

**Why this can't be gamed.** The grade is computed by the build from the `<fact>` block, not authored. A weak agent writing a plausible-but-wrong fact gets `orientation` (no same-claim cross-file corroboration) or `suspect` (structural contradiction), and the gate (§14) blocks a wiki whose `verified`-claimed cards don't reproduce from their stored `evidence[]` — exactly as `PLACEHOLDER_RE` enforces the TODO floor today. (Scope: the gate's anti-gaming guarantee is against a *prose `<fact>`*; a hand-edited `cards.json` with fabricated-but-self-consistent `evidence[]` is out of the gate's reach — the agent's source check, invariant 1, is the final backstop. §14 makes this boundary explicit.)

> **Resolved (red-team Theme 4).** Independence was "different file/region" → a same-file sibling could self-corroborate; now "different **file**", and the two signals must be about the **same** asserted token (the old rule corroborated entity *existence*, not the asserted *relationship*). `risk-keyword` could manufacture a `suspect` from the substring `auth` appearing anywhere in a region (false-flagging correct "no auth" facts); it is now **support-only**, and `contradiction` is restricted to structural absence against the scan inventory. `defines-symbol` no longer cites the whole-file `detect_dynamic_entrypoints` as its model — it is region-scoped declaration detection, explicitly new work. See §20.

---

## 11. Pillars B & C(2) — compiled queries, structured access, trust ledger, freshness

### 11.1 Compiled query plans + structured access (Pillar B)

Three deterministic graph queries (stdlib BFS over `entities.json`), precomputed for top-degree entities and on demand otherwise:

| Plan | Definition | Replaces |
|------|-----------|----------|
| **blast-radius**(E) | BFS over the **reverse** adjacency (in-edges) of `calls` + `serves-route` + `reads-config` from E, with an explicit **visited-set** (each entity expanded once; depth = first/shortest reach) and a depth cap. **Lower-bound, advisory** (see completeness note). | "what breaks if I change E" → several searches + manual assembly |
| **how-it-works**(E) | E's own cards + 1-hop forward-edge neighbor cards, in a **fixed documented order** (defines-symbol cards first, then edge-rel priority `serves-route`>`calls`>`reads-config`>…, ties by grade then `src`) | "explain E end-to-end" → multiple page opens |
| **neighbors**(E, rel) | typed-edge neighbors for a relation | "where is E configured/tested/secured" → repeated lookups |

**Reverse adjacency & cycles (specified, not assumed).** `entities.json` stores **forward** edges only (§6.3). At build time the indexer materializes a reverse adjacency by inverting all forward edges (an O(E) pass), and §14 adds a `graph_edge_asymmetry` check that every reverse edge has a matching forward edge. Traversal is BFS with a visited-set keyed by entity id, so a cyclic call graph (A→B→A) terminates and assigns correct shortest-depth; the depth cap bounds *size*, not termination.

**Completeness bound (blast-radius is a lower bound).** Edges are best-effort (`origin:source` from the scanner, or `origin:text`), so the reverse closure can have **false negatives** (an unrecorded caller is silently absent). blast-radius therefore traverses **`origin:source` edges only by default** (`--include-text-edges` to opt in) and is surfaced to the agent as *"known dependents — not exhaustive; verify by source search before relying,"* never as a complete "what breaks" answer.

**Structured query interface** — a tiny, parser-free, flag-based extension to `search_wiki.py` (no DSL; language-neutral entity ids):
```bash
search_wiki.py <root> --entity JwtUtil --relation impact     # → blast-radius bundle
search_wiki.py <root> --entity AuthService --relation how    # → how-it-works bundle
search_wiki.py <root> --route "POST /login"                  # → exact route entity + cards
search_wiki.py <root> --config jwt.expire                    # → exact config entity + cards
search_wiki.py <root> --risk auth --fresh                    # → risk cards, freshest first
search_wiki.py <root> "free text"                            # → postings/BM25 path (unchanged)
```
The structured path hits the entity roster directly ⇒ **zero lexical false positives** (the short-token noise of §1.3 cannot occur here) and one lookup. The **answers tier** in `map.json` (§6.2) lists pointers to the hottest verified cards; consuming one costs **one card fetch + one region-hash confirm** (§11.4), not zero fetches — far cheaper than a page read, but never a zero-check trust.

### 11.2 Trust signal & freshness (Pillar C)

Each card carries its own baseline `file_sha256`+`region_hash` per region in `cards.json` (§6.4), so **freshness is computed on the hot path without loading `ledger.json`** (§5): for each returned hit, re-hash exactly its cited file(s) — bounded by `--limit`, O(hits) hashes, not the whole corpus — and compare to the card's stored baselines. **Freshness is surfaced on every hit:**

| State | Condition | Agent action |
|-------|-----------|--------------|
| `fresh` | current file_sha256 == card's baseline file_sha256 (all regions) | citation current; a one-hash confirm is optional |
| `region-stable` | file changed but the stored `region_bytes` are still found **at the same offset** (current region_hash == baseline) | **cheap win:** cited region byte-identical; confirm by hashing one region, no source re-read |
| `region-moved` | file changed and the stored `region_bytes` are found **at a different offset** (§8 relocation) | region intact but `src` line numbers are stale; re-point (cheap), don't trust the old line numbers |
| `stale` | file changed and the stored `region_bytes` are **not found** | must re-read the cited range and re-verify before relying |
| `missing` | the cited file does not exist at its path (renamed/deleted) | citation target is gone; locate the moved file via rename correlation (§16.2) or drop the card — do **not** re-read the old range |
| `suspect` | card grade is `suspect` (structural contradiction, §10) | do not rely; re-read source; likely fix the card |

For a **multi-src card**, freshness is the **worst state across its regions** (a card is `fresh` only if every region is fresh), and the hit names which `src` is degraded. **Live trust = grade × freshness:** a `verified` card that is currently `stale`/`missing`/`suspect` must be presented as *"verified-at-build but now <state>"*, **never** as plain `verified` — the stored grade is a build-time verdict, not a live one (§10 grade is frozen; only a rebuild re-grades). This makes accuracy **visible and decaying**, and the verification budget is spent only on `stale`/`region-moved`/`missing`/`suspect` cards.

> **Resolved (red-team Theme 1).** Freshness was defined as a `ledger.json` compare while §5 forbade the hot path from loading the ledger (uncomputable as written) — baselines now live on the card. Added the missing `missing`/`region-moved` states (a rename used to masquerade as `stale` pointing at a vanished range). Made `region-stable` relocate the bytes instead of trusting a raw offset (closing the line-drift over-trust hole). Defined multi-src freshness (worst-case) and "verified-but-stale" so a frozen `verified` grade is never shown as live truth. See §20.

### 11.3 The hard distinction that keeps Pillar B invariant-1-clean

A **bundle is not a cached/generated answer.** It is a deterministically-selected set of existing card ids from a graph traversal — pointers to cards that themselves point to source. "Here are the cards the call graph says are impacted" is a query *result*; "here is a paragraph answering your question" is fabrication. Bundles are the former; the latter (`answers[]` prose / FAQ synthesis) is explicitly rejected (§16.3). A bundle's **membership** cannot drift *from the graph* (it is a pure function of `entities.json`, regenerated on topology change via the `generated_from` hash, §6.6). Its members' **source-currency** is NOT certified by that hash — it is carried per-card by the freshness computed at fetch (§11.2/§11.4); the agent must re-verify any non-`fresh` member. A bundle's `how-it-works` **ordering** carries no claim beyond the fixed §11.1 ordering rule, and `blast-radius` is an explicit **lower bound** (§11.1), so neither encodes an unfalsifiable editorial answer.

### 11.4 Consuming the `map.json` answers tier (no zero-fetch trust)

The answers tier (§6.2) inlines `{card_id, src}` **pointers only** — no statement text, no grade. To use one, the agent fetches the card from `cards.json` and computes its freshness (§11.2) exactly as for any hit; it then applies live trust (grade × freshness). This costs one fetch + one region hash — cheaper than a page read, but it preserves invariant 1: an inlined pointer is never an actionable answer, and a card that has gone `stale`/`missing` since build cannot be served as `verified`. (The earlier "zero-fetch, inlined verified statement" design recreated the §16.3 claimed-answer surface; removed — see §20.)

---

## 12. Retrieval flow & budget

### 12.1 Flow

```
rows model:  search → page → search → page …                         (7+ round-trips, ~12k tok)

graph model, ordinary lookup:
   load map (once, in context) → reason → postings/structured → fetch cards → maybe 1 source range   (2–3 rt, ~3k tok)

graph model, structural question (impact / how-it-works / neighbors):
   load map (answers tier may already answer)            # 0 extra fetch for hottest facts
     → structured query maps to a bundle id
     → fetch ONE bundle (card-id set) → fetch its member cards → compute freshness for each (re-hash cited files of members)
     → trust `fresh` cards; relocate/`region-stable` confirm by one hash; re-read only `stale`/`region-moved`/`missing`
   done                                                  # 1–2 round-trips, assembly precompiled
```

### 12.2 Budget

| | rows | graph (ordinary) | graph (structural) |
|---|------|------------------|--------------------|
| search round-trips | ~4 (×10 hits ×~300) | 1 map (~1.5k) + 1 card fetch (~800) | 1 bundle + member-card fetch |
| pages opened | ~3 ×~1000 | 0 (+1 source range ~300) | 0 |
| agent-side assembly | manual | minimal | **precompiled** |
| hottest-fact lookups | 1 fetch | 1 fetch | **1 card fetch + 1 region-hash confirm (answers-tier pointer)** |
| re-verification / card | page re-read (~1k) | region read | **`fresh`: ~0; `region-stable`/`region-moved`: 1 hash; only `stale`/`missing` re-read** |
| false-positive re-tries | lexical noise | reduced | **0 on structured path** |
| accuracy signal | none | graded | **graded × freshness, per hit** |
| **total (typical task)** | **~12k** | **~3k** | **~2k + precompiled assembly + O(hits) region hashes** |

**The honest framing:** the big multiplicative cut (≈4×) is rows→graph for ordinary lookups. The further leap is concentrated on the **structural query class**, the **elimination of agent-side assembly and false-positive re-tries**, the **collapse of re-verification cost**, and a real **accuracy** signal. Raw tokens for a single trivial lookup are ~parity between graph-ordinary and graph-structural — the doc does not pretend otherwise. Freshness costs **O(hits) source-file hashes** (script-side, zero model tokens), not zero — surfaced honestly here rather than hidden (§11.2).

---

## 13. Worked example (end-to-end)

Question: *"If I change `JwtUtil`, what's affected, and is the wiki's answer current?"*

1. Map already in context. Agent issues `--entity JwtUtil --relation impact`.
2. One bundle fetch returns `blast_radius[e_s_jwtutil]` (an `origin:source` lower bound, §11.1): card ids `c_8f2a` (AuthService.login), `c_1b03` (jwt.expire binding), `c_77e1` (POST /login route). Agent fetches the member cards and computes freshness per card (§11.2).
3. `c_8f2a` is `fresh` → trust its `src` (AuthService.java#L40-L88). `c_1b03` is `region-stable` → one region-hash confirm. `c_77e1` is `stale` → re-read AuthController.java#L22-L31. Had a file been renamed, that card would surface `missing` (not a misleading `stale`).
4. Agent answers with three impacted sites — flagged as *known dependents, not exhaustive* (§11.1 lower bound) — having opened **one** source range, with live trust (grade × freshness) per claim.

Rows-model equivalent: grep/search for `JwtUtil`, open 3+ pages, manually trace call relationships, no freshness signal, ~4× the tokens.

---

## 14. The strict readiness gate (full)

The gate stays non-negotiable (invariant 7). The graph model's gate is the **union** of all current checks plus graph and accuracy checks.

> **CRITICAL — do this FIRST, before any migration step (red-team Theme 3).** Today `index_valid` requires `schema_version in {1,2}` (`check_wiki_ready.py:206`) **and** every strict sub-check is gated `if strict and index_valid` (`:218`). So the instant the build writes `schema_version: 3`, `index_valid` turns False and **the placeholder / secret / mojibake / cite scans silently stop running** — a version bump becomes a loss of all strict coverage (a safety regression). The very first migration action (alongside Phase 0, before step 1) MUST: (a) widen `index_valid` to accept `{1,2,3}` and branch by `index_model` (`rows`→validate `pages[]`; `graph`→validate the `graph/` artifact set for the current stage); and (b) **decouple the content sub-checks (placeholder/secret/mojibake/cite) from `index_valid`** so a schema/index problem can never disable them. `create_wiki_skeleton` must not stamp schema 3 until the gate accepts it.

**Stage-aware (red-team Theme 3).** Graph artifacts arrive incrementally (§17). The gate reads a migration-stage marker (config `graph_stage`, or presence-detection of the artifact set) and only runs a graph/accuracy check once its prerequisite artifacts exist — so a legitimately partial graph mid-migration is valid, not "broken." Each §17 step states its green criteria.

**Retained from the current (rows) gate:** required config/index/root pages + same-name topic index pages; `<cite>` present; no TODO placeholder (`PLACEHOLDER_RE`); body length ≥ `MIN_STRICT_BODY_CHARS` (160); no secret-like values; no mojibake; no unindexed pages; no empty `source_refs`; cited files exist (`missing_cited_refs`, served from `fingerprints.json` §6.7b in graph mode).

**Added — graph structure:**

| Check | Fails when |
|-------|-----------|
| `cards_without_range` | a `<fact>`/card `src` lacks a line range |
| `cards_missing_region` | a cited range doesn't exist in the current file (out of bounds) |
| `cards_dangling_entity` | a card references an entity id absent from `entities.json` |
| `fact_assert_unparseable` | a `<fact> asserts` claim has no `:` or an unknown type (the §9 grammar) |
| `pages_without_facts` | a **non-exempt** content page yields zero cards (root_docs pages and `<!-- spwiki:orientation -->` pages are exempt, §9) |
| `graph_edge_asymmetry` | a materialized reverse edge has no matching forward edge in `entities.json` (or vice-versa) |
| `bundle_provenance_stale` | `bundles.json.generated_from` ≠ current `entities.json` hash (catches topology drift + deleted-member cards, since deletion changes `entities.json`) |
| `map_oversized` | `map.json` over soft budget (warn, not block) — protects load-once |

**Added — accuracy (Pillar C):**

| Check | Fails when |
|-------|-----------|
| `cards_unentailed_verified` | a `verified` card's grade is not re-derivable from its stored `evidence[]` via the §10 rule (audits self-consistency of build output; the gate does **not** re-run detectors against source — that is the build's job, §10 "Why this can't be gamed") |
| `cards_contradiction_unlabeled` | a card has structural `contradict` evidence but is not graded `suspect` |
| `evidence_dangling_region` | an evidence `src` range doesn't exist in the current file |
| `evidence_region_subset` | a `support` evidence item's `src` is neither within the card's cited region nor a declared out-of-region corroborating site (enforces "in the cited region" rather than assuming it) |
| `ledger_region_mismatch` | a card's `regions[].region_hash` ≠ recomputed at build (build-time consistency) |
| `ledger_grade_mismatch` | `ledger.json` grade ≠ `cards.json` grade for a card, or `evidence_count` disagrees with the `evidence[]` tally (closes the cross-file drift hole; `cards.json` is the single source of truth) |
| `hash_routine_disagreement` | the build and re-verify hashing routines disagree on a sample file (enforces the §8 single-normalization rule) |

**`map_answers` validity (corrected).** The answers tier holds `{card_id, src}` pointers (§6.2), so the gate check is `map_answers_not_verified` — fails when a pointed-to card is not `verified` at build, plus `map_answers_dangling` (pointer to an absent card). It does **not** check freshness: freshness is meaningless at build time (every card is fresh-by-construction the instant after build), and is instead enforced at *consumption* time (§11.4). (The original `map_answers_not_fresh` was a build-time tautology — red-team Theme 1/2.)

**Accuracy profile (reported; conditionally blocking).** The gate emits `{verified, orientation, suspect}` counts (freshness is a runtime signal, not a build-gate metric). Default **blocks on `suspect` in risk-flagged cards** (auth/payment/file-io/sql/deserialization/admin/secrets) **and**, when `accuracy_profile: corroborated`, on `verified == 0` for a non-trivial graph (so an all-`orientation` wiki cannot be silently certified "ready" — red-team Theme 4). A stricter "≥X% verified for risk-flagged cards" floor is configurable (resolves Q8 toward a default-on floor).

---

## 15. Per-script change contract

No code here — this is the contract for the implementation PR. All changes stay inside the existing scripts (invariant 8).

| Script | Responsibility in the graph model |
|--------|-----------------------------------|
| `wiki_common.py` | Add: `canonical_bytes`/`region_bytes` reader + `region_hash` + the **single shared** file/region hashing routine (§8); `<fact>` parser (semicolon `asserts`, §9); per-language **region-scoped declaration** detectors (NEW; declaration regexes applied to `region_bytes` — the *technique* mirrors `scan_project`'s per-language regex probes, but is **not** a reuse of the whole-file `detect_dynamic_entrypoints`); evidence grader (same-token, cross-file two-source rule, §10); reverse-adjacency builder + BFS-with-visited-set traversal; BM25 scorer; co-occurrence concept builder; freshness computation (from `cards.json` baselines, incl. region relocation); fingerprints/ledger I/O; `graph/` path helpers. Reuse `tokenize`, `write_text_utf8`, sidecar loaders, risk keywords unchanged. |
| `scan_project.py` | Emit a **full-tree, uncapped** verified symbol/route/config inventory (`origin:"source"`) into a `.spwiki/`-readable artifact that `build_wiki_index` consumes — it seeds entities **and** is the corroboration substrate. *New* work, and a **correctness prerequisite, not a tunable*: the inventory must NOT inherit `iter_source_files`' `max_files=200`, the `SOURCE_DIR_NAMES` allowlist, or per-probe `break` (those would deterministically miss call-sites/tests → false `orientation`). Must include test directories. Gitignore behavior unchanged. |
| `create_wiki_skeleton.py` | When graph: seed `<fact>` stubs with `asserts` placeholders **pre-filled from the scan inventory** (so the agent edits real typed claims rather than inventing them — makes the `verified` path the path of least resistance, red-team Theme 4), TODO-marked so the gate still blocks unfilled stubs. Write `index_model`/`accuracy_profile` config — but **schema 3 only after the gate accepts it** (§14 CRITICAL). |
| `build_wiki_index.py` | When graph: parse `<fact>`+`asserts` → run region-scoped entailment + cross-file corroboration → emit `cards.json` (+`regions[]` baselines +evidence +grade), `entities.json` (+materialized reverse adjacency), `fingerprints.json` (per-file), `ledger.json` (per-card audit, grade mirrors cards.json), `bundles.json`, `postings.json`, `map.json` (+answers-tier pointers), `concepts.json`. Reuse prior per-file hashes via the mtime+size shortcut. Emit the back-compat `wiki-index.json` shim (defined contents below) until the gate is schema-3-taught. |
| `search_wiki.py` | When graph: structured-query flags (`--entity/--relation/--route/--config/--risk/--fresh`); bundle fetch + member-card fetch; compute & surface freshness per returned hit from `cards.json` baselines (re-hash only the hits' cited files); compact default + `--verbose`. Free-text path = postings/BM25. **The Phase-0 rows fixes (§1.2/§1.3) ship as their own change with re-baselined rows ranking — NOT bundled into the graph PR** (they touch shared `tokenize`/`score_page`, red-team Theme 3). |
| `plan_wiki_update.py` | When graph: freshness-driven candidates (stale/region-moved/missing/suspect first); region-level staleness; rename correlation by file/region hash; new-module detection. Reads `fingerprints.json` (per-file, the `old_fingerprint_map`/`current_fingerprint` successor) + ledger. Move `DEFAULT_TOPIC_HINTS` to sidecar + localize, **keeping the built-in defaults as a fallback when no sidecar is present so rows-mode behavior is unchanged** (invariant 2/3, red-team Theme 3). |
| `check_wiki_ready.py` | **First:** widen `index_valid` to `{1,2,3}` + branch by `index_model`, and decouple content sub-checks from `index_valid` (§14 CRITICAL). Then add §14 graph + accuracy checks, stage-awareness, and emit the accuracy profile. |
| `uninstall_wiki.py` | Unchanged (still removes `.spwiki/` wholesale). |

**Back-compat `wiki-index.json` shim — defined contents.** Until the gate is schema-3-aware, the build also emits a rows-shaped `wiki-index.json` via a deterministic cards→pages projection: for each `page_id`, emit `{path, source_refs = unique(file part of each card's regions[].src), source_fingerprints = per-file {path, exists} resolved from fingerprints.json}` plus the top-level `{schema_version (a value the gate accepts during transition), content_root, pages[]}`. A gate-parity test asserts the retained rows checks (`missing_cited_refs`, `pages_missing_source_refs`, unindexed reconciliation) pass on the shim. Without this projection the "gate stays green" promise (§17) is unbacked.

---

## 16. Costs, risks, rejected ideas

### 16.1 Costs
- **Build cost rises** (entailment + corroboration search + bundle precompute). Acceptable: init may spend more (standing priority); all script-side, zero model tokens.
- **Authoring burden rises** (`asserts` hints). Optional — omitting them caps a card at `orientation`; weak agents are backstopped by the gate.
- **Script complexity rises sharply** beyond the current single-file simplicity. Real tension with "scripts stay simple." Mitigation: the graph model and `accuracy_profile` are **opt-in**; `rows`/`light` projects never touch any of it.

### 16.2 Risks
- **Structural ≠ semantic entailment** (§10 bound). Mitigation: never claim proof; keep the agent's source check as final; grades narrow, not eliminate, error.
- **False `suspect` flags** (e.g. a fact about genuinely untested code). Mitigation: `orientation` (unsupported) is distinct from `suspect` (contradicted); only *contradiction* triggers `suspect`; `suspect` blocks only risk-flagged cards by default.
- **Bundle staleness/explosion.** Mitigation: provenance hash + regenerate-with-graph; precompute only top-degree entities; depth cap + visited-set (§11.1).
- **Ledger/freshness misread as "skip verification."** Mitigation: invariant-1 row + N4; `fresh` means "cheap to confirm," never "don't confirm"; the answers tier is pointers, not actionable text (§11.4).
- **Line-drift false confidence.** Mitigation: the §8 rule guards **both** directions — mismatch may only raise attention, and a positive region match after a whole-file change must be confirmed by **relocating** the stored `region_bytes` (→ `region-stable`/`region-moved`/`stale`), never trusted at a raw offset.
- **Doc drift across copies.** This merged doc exists precisely because three overlapping notes would drift (the repo already warns about duplicated config blocks at `AGENTS.md:61`). Keep this the single source.

### 16.3 Rejected — do NOT build
- **Generated/paraphrased answer storage** (FAQ synthesis, `answers[]` as prose, **or inlining card statement text into the map answers tier as actionable truth**). Drifts toward a claimed-answer surface (invariant 1). Bundles (pointers, not prose) and the pointer-only answers tier replace it; §11.3/§11.4 are the firewall.
- **Cross-session answer cache.** Self-rotting; conflicts with source-authority/anti-staleness. The freshness mechanism is the *anti-cache*: it assumes drift and surfaces it.
- **Time-based freshness decay.** `verified_at` is display-only; freshness is hash-derived. Time can't tell you if code changed; a hash can. Also avoids `Date.now()` non-determinism.
- **A real query DSL/grammar.** Parser = complexity + ambiguity. Flag-based structured queries only.
- **Embeddings/vectors.** Breaks stdlib-only (invariant 6). Semantic recall = load-once map + in-context reasoning + learned concept clusters.

---

## 17. Migration (strangler-fig; each step ships and is verified alone)

Phase 0 (§1) ships first and independently. **Then, before step 1, the CRITICAL gate fix (§14): widen `index_valid` to `{1,2,3}` and decouple content sub-checks from it** — otherwise stamping schema 3 silently disables secret/mojibake scanning. Then:

1. **Map (no answers tier yet).** Additive artifact: roster + topic_tree + counts only. The answers tier is deferred to step 4b (it needs `verified` grades from step 3 and freshness from step 4 — it cannot exist at step 1). Measure load-once + the round-trip win immediately.
2. **Postings + structured queries** (`--entity/--route/--config`). Verify zero false positives on the structured path vs free-text; verify ranking parity with the rows model on a fixed query set. (Phase-0 §1.2/§1.3 rows-scorer fixes ship *before* this, separately, with re-baselined rows ranking.)
3. **Cards + evidence model + grading** (+ the scan inventory that feeds corroboration, §15). Cards overlay pages (pages still render as today); gate gains `cards_*`, `fact_assert_unparseable`, `cards_unentailed_verified`, `ledger_grade_mismatch`. Verify grades are re-derivable from `evidence[]`.
4. **Per-card baselines + freshness + `fingerprints.json`** (region_hash/per-file fingerprints take over change detection from the live `source_fingerprints`; delete the already-dead `source_spans` — distinct fields, §8). Verify `region-stable` re-verification is hash-only, `region-moved`/`missing` states fire correctly, and out-of-range edits don't flag the page.
4b. **Answers tier** (pointers to verified cards, consumed per §11.4). Now that grades + baselines exist, add the `{card_id, src}` pointer list to `map.json` and the `map_answers_not_verified`/`map_answers_dangling` gate checks.
5. **Bundles** (reverse-adjacency + visited-set traversal precompute). Verify provenance regenerates on topology change, A↔B cycle fixture terminates, blast-radius is surfaced as a lower bound.
6. **(Terminal, optional)** pages become a render of cards, or keep the permanent triad: *page = author surface, card = retrieval surface, fingerprints/ledger = change+trust surface.*

**Gate after each step:** `check_wiki_ready.py --strict --recursive` stays green via stage-awareness (§14) — each step's prerequisite-gated checks only, plus the back-compat shim (§15) keeping the retained rows checks satisfied throughout.

**Field-naming correctness (red-team Theme 3).** `source_spans` (line ranges) is **dead** today (no consumer) — delete it at any step, it is *not* the change detector. `source_fingerprints` (sha256+size+mtime) is the **live** change detector read by `missing_cited_refs` and `old_fingerprint_map`; step 4 migrates *that* field into per-card `regions[]` baselines + `fingerprints.json`, preserving `exists`/`size`/`mtime_ns`. Do not conflate the two.

---

## 18. Empirical validation plan

Both the efficiency and accuracy claims are **quantities**, and quantities must be measured on real code, not asserted. This section is the processed answer to "should the stress-tests run after building, on the real project?" — **yes, but staged, and split by who can actually answer each question.**

### 18.1 Two distinct activities, opposite in time

- **Design-flaw hunting — BEFORE writing code.** A small adversarial review (agent red-team is appropriate here) targets *logic* defects in the design, not rates: e.g. rename+edit defeating `region_hash` correlation; `suspect` policy false-killing legitimately-untested code; bundles not handling call-graph cycles; the answers-tier inlining a card that later goes stale. These are reasoning checks; catching them before implementation avoids building on a flawed design.
- **Quantitative stress-tests — AFTER building, on real repos.** The three concerns you named are all *rates/sizes* and **only real runs can answer them**. An agent can name a failure mode; it cannot produce the *rate*.

### 18.2 The three quantitative tests — staged so a bad result wastes little

Build per the strangler-fig steps and measure at the earliest step that exposes each metric:

| Concern | Earliest step that exposes it | What to measure | Needs ground truth? |
|---------|-------------------------------|-----------------|---------------------|
| **Bundle size/depth explosion** in large monorepos | after step 1–2 + one graph build (no accuracy pillar needed) | bundle byte size distribution; edge-degree distribution; depth-D closure sizes; `map.json` size vs the load-once budget | no |
| **Corroboration false-positive/negative rate** | after step 3 (grading) on one real repo | of cards the build grades `verified`, how many a human/oracle judges wrong; of cards downgraded to `orientation`/`suspect`, how many were actually fine | **yes** |
| **`suspect` blocking consequences** | after step 3 | how many real authored cards get `suspect`; how many are true contradictions vs false alarms; impact on the gate pass rate | yes |

Staging matters: bundle explosion is measurable with **no** accuracy work, so if bundles blow up you've spent only steps 1–2, not the whole of Pillar C.

### 18.3 Ground truth is required for the accuracy tests

"False-positive rate" presupposes a known *correct* grade. Reserve effort to **hand-label (or use a trusted oracle on) a sampled subset** of cards as actually-correct / actually-wrong, then score the build's grades against that label. This step is **not** automatable end-to-end and must be budgeted.

### 18.4 Efficiency battery (run alongside)

On a fixed query set split into **trivial-lookup** and **structural** classes, measure token deltas: expect ~parity on trivial (graph-ordinary vs graph-structural), large drop on structural; record false-positive rate structured vs free-text, and the zero-fetch rate from the answers tier. Compare all against the rows-model baseline on the same battery.

### 18.5 Decision gates from the numbers
- If **bundles explode** (after steps 1–2): cap depth/top-N or descope Pillar B before building Pillars A/C further.
- If **grading downgrades ≈ nothing** (after step 3): the target repo was already well-documented; Pillars C/grading are low-value *there* — keep them opt-in, don't force.
- If **grading downgrades many**: that count *is* the accuracy problem this redesign fixes, made visible — proceed.
- If **structural-query token drop** doesn't materialize: revisit bundle design before deeper investment.

**Measure, then commit.** No step past the prototype is justified without its numbers.

---

## 19. Open questions for the implementation PR

- Q1. Card granularity: one `<fact>` = one card is clean, but very fine-grained facts could explode card count. Cap per page? Merge adjacent same-`src` facts?
- Q2. Edges: authored (via `<fact>`/`asserts`) vs inferred from scan ground-truth only? Inferring risks invariant-2-style coupling; authoring raises burden. (Note: blast-radius now defaults to `origin:source` edges only, §11.1, so the *impact* path leans on scan ground-truth regardless.)
- ~~Q3. Two-source independence~~ → **RESOLVED (§20):** independence is "different **file**" and the two signals must concern the **same** asserted token. `test-covers`/`call-site`/`references-symbol` weighting can still be tuned on §18 data.
- Q4. `suspect` blocking policy refinement beyond the §14 default (risk-flagged suspect blocks; corroborated-profile `verified==0` blocks).
- Q5. Bundle top-N degree threshold and depth cap D — pick from measured graph sizes (§18.2).
- Q6. Map `answers` tier size N (now pointer-only, so far smaller) vs the ≤~3 KB load-once budget.
- Q7. Are `orientation` cards searchable by default or opt-in (`--include-orientation`), to bias agents toward verified facts?
- ~~Q8. `asserts` mandatory for risk-flagged facts?~~ → **PARTIALLY RESOLVED (§20):** the corroborated-profile gate now blocks `verified==0`, and skeleton seeds `asserts` from the scan inventory; whether to additionally *require* `asserts` on every risk-flagged `<fact>` remains a tunable.
- Q9. Layered-map threshold: at what `counts.cards` does a single `map.json` split into per-topic sub-maps?
- Q10. Keep `wiki-index.json` permanently as a compat shim, or drop it after a deprecation window?
- Q11. (NEW) Relational corroboration: §10's honest bound notes a relation A→B can reach `verified` while only A and B's *existence* is corroborated. Should risk-flagged relational claims require the corroborating site to contain *both* tokens? Tune on §18 ground-truth.

Resolve in the implementation PR with measured data from §18.

---

## 20. Red-team resolutions (changelog)

A pre-implementation design-logic red team (6 adversarial lenses, every finding adversarially verified against this doc + the live source) ran against the prior revision. It surfaced 38 candidate flaws; verification confirmed 27 + 7 minor and rejected 4 (2 misreads, 2 not-a-flaw). This revision applies the confirmed fixes. The rejected items are recorded so they are not "re-fixed" later.

### Applied — critical / high

| # | Finding (theme) | Resolution in this revision |
|---|-----------------|------------------------------|
| R1 | **schema_version trap** silently disables secret/mojibake scanning when the build writes schema 3 (`index_valid in {1,2}` gates all strict sub-checks) | §14 CRITICAL block: widen `index_valid` to `{1,2,3}` + branch by `index_model`, **and decouple content sub-checks from `index_valid`**, as the FIRST migration action (before step 1). |
| R2 | **Freshness uncomputable on hot path** — defined as a `ledger.json` compare while §5 forbids the hot path from loading the ledger | §6.4 denormalizes per-region `file_sha256`+`region_hash` onto each card; §5/§11.2 compute freshness from `cards.json` (re-hash only returned hits' files); ledger demoted to cold audit (§6.7). |
| R3 | **`source_fingerprints`→ledger shape-incompatible** (per-card ledger lacks `exists`/`size`/`mtime_ns`, not path-keyed) | New `fingerprints.json` (§6.7b), per-file, serves `missing_cited_refs` + `old_fingerprint_map`/`current_fingerprint` verbatim. |
| R4 | **§17 step-1 ordering contradiction** — answers tier needs grades (step 3) + freshness (step 4) | §17: step 1 ships map *without* answers tier; new step 4b adds the (pointer-only) answers tier after baselines exist. |
| R5 | **Answers tier = claimed-answer surface** (inlined `statement`+`grade:verified`, zero-fetch, no live freshness) | §6.2/§11.4: answers tier is `{card_id, src}` **pointers only**; consuming one requires a card fetch + freshness check; never actionable text. |
| R6 | **`region-stable` over-trust under line drift** (coincidental hash match at a drifted offset suppresses re-read of a changed file) | §8 two-direction rule + region **relocation** by stored `region_bytes`; new `region-moved` state; §11.2 table updated. |
| R7 | **No `missing`/renamed state** — a renamed file degrades to `stale` pointing at a vanished range | §11.2 adds `missing` (+`region-moved`); rename correlation wired (§16.2). |
| R8 | **Multi-src cards have no freshness representation** (single scalar `region_hash`) | §6.4 `regions[]` list; §11.2 multi-src freshness = worst-state-across-regions. |
| R9 | **Frozen grade shown as live truth** (`map_answers_not_fresh` is a build-time tautology; `suspect` never re-fires on drift) | §11.2 "live trust = grade × freshness" (verified-but-stale); §14 replaces `map_answers_not_fresh` with `map_answers_not_verified` and enforces freshness at consumption (§11.4). |
| R10 | **`risk-keyword` manufactures false `suspect`** (substring `auth` present ⇒ contradicts "no auth") | §10: `risk-keyword` is **support-only**; `contradiction` restricted to *structural* absence vs the scan inventory. |
| R11 | **`asserts` grammar ambiguous** (space-separated, but `route:POST /login` contains a space) | §9: **semicolon-separated** `asserts` + `fact_assert_unparseable` gate check. |
| R12 | **`pages_without_facts` unsatisfiable** for required prose root pages | §9/§14: exempt root_docs pages + `<!-- spwiki:orientation -->` pages. |
| R13 | **scan corroboration substrate unwired + capped** (200-file/allowlist/first-break ⇒ deterministic false `orientation`) | §15: scan emits a **full-tree uncapped** inventory artifact build consumes; coverage is a correctness prerequisite, not a tunable. |
| R14 | **blast-radius reverse edges + cycles unspecified** (entities stores forward edges only; no visited-set) | §11.1: build materializes reverse adjacency (+`graph_edge_asymmetry` gate); BFS with visited-set; depth cap is size-only. |
| R15 | **blast-radius sound/complete-looking on best-effort edges** (silent false negatives) | §11.1: explicit **lower-bound**, `origin:source`-only by default, surfaced as "not exhaustive." |
| R16 | **`defines-symbol` cited whole-file `detect_dynamic_entrypoints`** as its model | §10/§15: region-scoped declaration detection, explicitly NEW work; declaration ≠ use (else only `references-symbol`). |
| R17 | **back-compat shim undefined** (gate can't stay green from card-level data) | §15: defined cards→pages projection + gate-parity test. |
| R18 | **gate can't validate a partial graph dir** | §14: stage-aware checks (prerequisite-gated). |
| R19 | **`source_spans` vs `source_fingerprints` conflation** in §8/§17 step 4 | §8/§17: explicitly distinguished — `source_spans` is dead/deletable; `source_fingerprints` is the live detector being migrated. |
| R20 | **grade stored in two files, no equality check** | §6.4 grade is single source of truth; §6.7 ledger mirrors; §14 `ledger_grade_mismatch`. |

### Applied — medium / minor
- **Byte-normalization pinned** (§8): whole-file and region hashes use one `canonical_bytes` routine; `errors='ignore'` forbidden; `hash_routine_disagreement` gate. (Raw vs normalized could desync the two signals.)
- **Same-token corroboration** (§10): the two signals must concern the same asserted token, not two independently-existing tokens (the old rule corroborated existence, not the relationship; honest bound + Q11 added).
- **"opt-in" honesty** (§15/§16.1 intent): Phase-0 rows-scorer fixes ship separately with re-baselined ranking; `DEFAULT_TOPIC_HINTS` keeps built-in fallback so rows behavior is unchanged.
- **`evidence_region_subset` gate** (§14): a support item's `src` must be within the cited region or a declared corroborating site.

### Rejected by verification — deliberately NOT changed
- **"`cards_unentailed_verified` forces the gate to re-run detectors / is circular"** — *misread.* The check audits self-consistency of stored `evidence[]`; the build does entailment, the gate audits. §10/§14 now state this trust boundary explicitly (anti-gaming is against a prose `<fact>`, not a hand-edited `cards.json`; invariant 1 is the final backstop).
- **"Bundle provenance bound to entities.json is wrong (grade-flip bypasses it)"** — *misread.* Bundle *membership* is a pure function of `entities.json`; grade/freshness resolve live from `cards.json` at fetch (§11.3/§11.4), so a stale grade cannot reach the agent via a bundle. Card *deletion* does change `entities.json` → caught.
- **"how-it-works ordering is an editorial claim that violates the firewall"** — *not-a-flaw.* A deterministic, documented ordering of pointer cards (each carrying its own `src`) introduces no fabricated text — like ranked search results. §11.1 pins the order rule; §11.3 notes it carries no claim beyond that rule.
- **"two-source corroborates existence not relationship = false-verify by construction"** — downgraded: this is the *disclosed, accepted* meaning of `verified` (§10 honest bound), not a hidden contradiction. Tightened to same-token corroboration and logged as Q11; not treated as a blocker.
