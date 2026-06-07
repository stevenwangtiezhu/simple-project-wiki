#!/usr/bin/env python3
"""Search .spwiki/wiki-index.json files before reading full wiki pages."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from wiki_common import expand_query_terms, tokenize


SKIP_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "target",
    "dist",
    "dist_electron",
    "build",
    "out",
    ".next",
    ".nuxt",
    ".cache",
    "__pycache__",
    "vendor",
}


def load_json(path: Path) -> Dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {"_load_error": "JSON root is not an object"}
    except Exception as exc:
        return {"_load_error": str(exc)}


def iter_wiki_indexes(project_root: Path, root_only: bool = False) -> Iterable[Path]:
    yielded = set()
    root_index = project_root / ".spwiki" / "wiki-index.json"
    if root_index.exists():
        yielded.add(root_index.resolve())
        yield root_index
    if root_only:
        return

    for current, dirnames, filenames in os.walk(project_root):
        current_path = Path(current)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        if current_path == project_root:
            continue
        if current_path.name == ".spwiki" and "wiki-index.json" in filenames:
            index_path = current_path / "wiki-index.json"
            resolved = index_path.resolve()
            if resolved not in yielded:
                yielded.add(resolved)
                yield index_path
            dirnames[:] = []


def list_values(page: Dict[str, object], key: str) -> List[object]:
    value = page.get(key, [])
    return value if isinstance(value, list) else []


def flatten_page(page: Dict[str, object]) -> Dict[str, str]:
    buckets = {
        "title": [str(page.get("title", ""))],
        "topic": [str(page.get("topic", ""))],
        "summary": [str(page.get("summary", ""))],
        "path": [str(page.get("path", ""))],
        "source_refs": [str(item) for item in list_values(page, "source_refs")],
        "tags": [str(item) for item in list_values(page, "tags")],
        "aliases": [str(item) for item in list_values(page, "aliases")],
        "config_keys": [str(item) for item in list_values(page, "config_keys")],
        "risk_flags": [str(item) for item in list_values(page, "risk_flags")],
        "headings": [],
        "routes": [],
        "symbols": [],
    }

    for heading in list_values(page, "headings"):
        if isinstance(heading, dict):
            buckets["headings"].append(str(heading.get("title", "")))
            buckets["headings"].append(str(heading.get("anchor", "")))
    routes = list_values(page, "routes") or list_values(page, "api_endpoints")
    for route in routes:
        if isinstance(route, dict):
            buckets["routes"].append(f"{route.get('method', '')} {route.get('path', '')}")
    for symbol in list_values(page, "symbols"):
        if isinstance(symbol, dict):
            buckets["symbols"].append(str(symbol.get("name", "")))

    return {key: "\n".join(values).lower() for key, values in buckets.items()}


def token_in_text(token: str, text: str) -> bool:
    if len(token) < 3 and re.fullmatch(r"[0-9a-z_]+", token, re.IGNORECASE):
        return re.search(rf"(?<![0-9a-z_]){re.escape(token)}(?![0-9a-z_])", text, re.IGNORECASE) is not None
    return token in text


def exact_query_in_text(query: str, text: str) -> bool:
    if re.fullmatch(r"[0-9a-z_]{1,2}", query, re.IGNORECASE):
        return token_in_text(query, text)
    return query in text


def score_page(page: Dict[str, object], query: str, tokens: List[str]) -> Tuple[int, List[str]]:
    fields = flatten_page(page)
    query_l = query.lower()
    score = 0
    reasons: List[str] = []

    weights = {
        "title": 80,
        "aliases": 55,
        "routes": 70,
        "symbols": 65,
        "source_refs": 60,
        "config_keys": 55,
        "risk_flags": 55,
        "tags": 35,
        "topic": 30,
        "headings": 45,
        "path": 25,
        "summary": 20,
    }

    for field, text in fields.items():
        if not text:
            continue
        if query_l and exact_query_in_text(query_l, text):
            score += weights.get(field, 10) * 2
            reasons.append(f"exact:{field}")
        for token in tokens:
            if token_in_text(token, text):
                score += weights.get(field, 10)
                reasons.append(f"{token}:{field}")

    return score, sorted(set(reasons))


def heading_hits(page: Dict[str, object], tokens: List[str], limit: int = 5) -> List[Dict[str, object]]:
    hits: List[Dict[str, object]] = []
    for heading in list_values(page, "headings"):
        if not isinstance(heading, dict):
            continue
        text = " ".join(str(heading.get(key, "")) for key in ("title", "anchor")).lower()
        reasons = [token for token in tokens if token_in_text(token, text)]
        if reasons:
            hits.append({
                "title": heading.get("title"),
                "anchor": heading.get("anchor"),
                "line_start": heading.get("line_start"),
                "line_end": heading.get("line_end"),
                "reasons": reasons,
            })
    return hits[:limit]


def page_hit(index_path: Path, page: Dict[str, object], score: int, reasons: List[str], tokens: List[str]) -> Dict[str, object]:
    wiki_root = index_path.parent
    project_root = wiki_root.parent
    page_path = str(page.get("path", ""))
    return {
        "score": score,
        "reasons": reasons[:12],
        "project": project_root.name,
        "project_root": str(project_root),
        "index_path": str(index_path),
        "page_path": page_path,
        "page_abs_path": str(wiki_root / page_path) if page_path else None,
        "title": page.get("title"),
        "topic": page.get("topic"),
        "summary": page.get("summary"),
        "heading_hits": heading_hits(page, tokens),
        "tags": page.get("tags", []),
        "risk_flags": page.get("risk_flags", []),
        "routes": page.get("routes", page.get("api_endpoints", [])),
        "symbols": list_values(page, "symbols")[:20],
        "source_refs": page.get("source_refs", []),
    }


def search(project_root: Path, query: str, limit: int, root_only: bool) -> Dict[str, object]:
    project_root = project_root.resolve()
    base_tokens = tokenize(query)
    hits: List[Dict[str, object]] = []
    indexes: List[str] = []
    errors: List[Dict[str, str]] = []
    seen_tokens: set = set()

    for index_path in iter_wiki_indexes(project_root, root_only=root_only):
        indexes.append(str(index_path))
        wiki_project_root = index_path.parent.parent
        tokens = expand_query_terms(wiki_project_root, query) or base_tokens
        seen_tokens.update(tokens)
        index = load_json(index_path)
        if "_load_error" in index:
            errors.append({"index_path": str(index_path), "error": str(index["_load_error"])})
            continue
        pages = index.get("pages", [])
        if not isinstance(pages, list):
            continue
        for page in pages:
            if not isinstance(page, dict):
                continue
            score, reasons = score_page(page, query, tokens)
            if score > 0 or not query:
                hits.append(page_hit(index_path, page, score, reasons, tokens))

    hits.sort(key=lambda item: (-int(item["score"]), str(item["project"]), str(item["page_path"])))
    if limit > 0:
        hits = hits[:limit]

    all_tokens = sorted(seen_tokens)
    return {
        "project_root": str(project_root),
        "query": query,
        "tokens": all_tokens or base_tokens,
        "index_count": len(indexes),
        "indexes": indexes,
        "error_count": len(errors),
        "errors": errors,
        "hit_count": len(hits),
        "hits": hits,
    }


def print_text(result: Dict[str, object]) -> None:
    print(f"query: {result['query']}")
    print(f"tokens: {', '.join(result.get('tokens', []))}")
    print(f"indexes: {result['index_count']} hits: {result['hit_count']}")
    for hit in result.get("hits", []):
        print()
        print(f"[{hit['score']}] {hit['project']} :: {hit['title']}")
        print(f"page: {hit['page_path']}")
        if hit.get("heading_hits"):
            print("heading_hits:")
            for heading in hit["heading_hits"][:3]:
                print(f"- {heading.get('title')} L{heading.get('line_start')}-L{heading.get('line_end')}")
        if hit.get("summary"):
            print(f"summary: {hit['summary']}")
        if hit.get("source_refs"):
            print("source_refs:")
            for ref in hit["source_refs"][:8]:
                print(f"- {ref}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Search .spwiki/wiki-index.json files.")
    parser.add_argument("project_root", help="Project root to search.")
    parser.add_argument("query", nargs="*", help="Search text, route, path, symbol, config key, or risk topic.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum hits to emit. Use 0 for no limit.")
    parser.add_argument("--root-only", action="store_true", help="Only search the root .spwiki index.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    result = search(Path(args.project_root), query, args.limit, args.root_only)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
