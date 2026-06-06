#!/usr/bin/env python3
"""Check whether a project .spwiki is structurally and evidence ready."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set

from wiki_common import (
    PLACEHOLDER_RE,
    content_root_path,
    content_root_rel,
    filename_for_title,
    load_config,
    mojibake_hits,
    root_docs,
    secret_hits,
    strip_markdown_noise,
)


CITE_RE = re.compile(r"<cite>(.*?)</cite>", re.DOTALL | re.IGNORECASE)
MIN_STRICT_BODY_CHARS = 160
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
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def required_root_files(project_root: Path, config: Dict[str, object]) -> List[str]:
    content_rel = content_root_rel(config)
    language = str(config["language"])
    files = [
        ".spwiki/config.json",
        ".spwiki/wiki-index.json",
    ]
    files.extend(f".spwiki/{content_rel}/{doc['filename']}" for doc in root_docs(language))
    return files


def same_name_topic_indexes(project_root: Path, config: Dict[str, object]) -> List[str]:
    content_root = content_root_path(project_root, config)
    if not content_root.exists():
        return []
    required = []
    for child in sorted(content_root.iterdir()):
        if child.is_dir():
            required.append(rel(child / filename_for_title(child.name), project_root))
    return required


def markdown_pages(project_root: Path, config: Dict[str, object]) -> List[Path]:
    content_root = content_root_path(project_root, config)
    if not content_root.exists():
        return []
    return [path for path in sorted(content_root.rglob("*.md")) if path.is_file()]


def placeholder_files(project_root: Path, config: Dict[str, object]) -> List[str]:
    result: List[str] = []
    for path in markdown_pages(project_root, config):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if PLACEHOLDER_RE.search(text):
            result.append(rel(path, project_root))
    return result


def pages_without_cite(project_root: Path, config: Dict[str, object]) -> List[str]:
    result = []
    for path in markdown_pages(project_root, config):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if not CITE_RE.search(text):
            result.append(rel(path, project_root))
    return result


def short_content_pages(project_root: Path, config: Dict[str, object]) -> List[str]:
    result = []
    for path in markdown_pages(project_root, config):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if len(strip_markdown_noise(text)) < MIN_STRICT_BODY_CHARS:
            result.append(rel(path, project_root))
    return result


def secret_hit_records(project_root: Path, config: Dict[str, object]) -> List[Dict[str, str]]:
    records = []
    for path in markdown_pages(project_root, config):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        for hit in secret_hits(text):
            records.append({"path": rel(path, project_root), **hit})
    return records


def mojibake_hit_records(project_root: Path, config: Dict[str, object]) -> List[Dict[str, str]]:
    records = []
    for path in markdown_pages(project_root, config):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for hit in mojibake_hits(text):
            records.append({"path": rel(path, project_root), **hit})
    return records


def index_page_map(index: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    pages = index.get("pages", [])
    if not isinstance(pages, list):
        return {}
    result = {}
    for page in pages:
        if isinstance(page, dict) and page.get("path"):
            result[str(page["path"]).replace("\\", "/")] = page
    return result


def missing_cited_refs(page_map: Dict[str, Dict[str, object]]) -> List[Dict[str, str]]:
    missing: List[Dict[str, str]] = []
    for page_path, page in page_map.items():
        fingerprints = page.get("source_fingerprints", [])
        if not isinstance(fingerprints, list):
            continue
        for item in fingerprints:
            if isinstance(item, dict) and item.get("path") and not item.get("exists"):
                missing.append({"page": page_path, "source_ref": str(item["path"])})
    return missing


def pages_missing_source_refs(page_map: Dict[str, Dict[str, object]]) -> List[str]:
    result = []
    for page_path, page in page_map.items():
        refs = page.get("source_refs", [])
        if not isinstance(refs, list) or not refs:
            result.append(page_path)
    return result


def unindexed_markdown_pages(project_root: Path, config: Dict[str, object], page_map: Dict[str, Dict[str, object]]) -> List[str]:
    wiki_root = project_root / ".spwiki"
    indexed = set(page_map.keys())
    result = []
    for path in markdown_pages(project_root, config):
        rel_path = rel(path, wiki_root)
        if rel_path not in indexed:
            result.append(rel(path, project_root))
    return result


def config_valid(config: Dict[str, object]) -> bool:
    return (
        isinstance(config.get("language"), str)
        and bool(str(config.get("language")).strip())
        and config.get("profile") in {"light", "balanced", "deep"}
        and isinstance(config.get("auto_update_after_code_change"), bool)
        and config.get("token_strategy") == "prefilter_batch"
    )


def check(project_root: Path, strict: bool = False) -> Dict[str, object]:
    project_root = project_root.resolve()
    config = load_config(project_root)
    missing: List[str] = []
    present: List[str] = []

    required = required_root_files(project_root, config) + same_name_topic_indexes(project_root, config)
    for item in required:
        path = project_root / item
        if path.exists() and path.is_file():
            present.append(item)
        else:
            missing.append(item)

    index_path = project_root / ".spwiki" / "wiki-index.json"
    index = load_json(index_path)
    expected_content_root = content_root_rel(config)
    page_map = index_page_map(index)
    index_valid = (
        index.get("schema_version") in {1, 2}
        and index.get("content_root") == expected_content_root
        and isinstance(index.get("pages"), list)
    )
    cfg_valid = config_valid(config)

    strict_details = {
        "placeholder_files": placeholder_files(project_root, config) if strict else [],
        "pages_without_cite": pages_without_cite(project_root, config) if strict else [],
        "short_content_pages": short_content_pages(project_root, config) if strict else [],
        "secret_hits": secret_hit_records(project_root, config) if strict else [],
        "mojibake_hits": mojibake_hit_records(project_root, config) if strict else [],
        "unindexed_pages": unindexed_markdown_pages(project_root, config, page_map) if strict and index_valid else [],
        "pages_missing_source_refs": pages_missing_source_refs(page_map) if strict and index_valid else [],
        "missing_cited_refs": missing_cited_refs(page_map) if strict and index_valid else [],
    }
    strict_valid = not any(strict_details.values())
    ready = not missing and index_valid and cfg_valid and (strict_valid if strict else True)
    return {
        "project_root": str(project_root),
        "ready": ready,
        "strict": strict,
        "strict_valid": strict_valid,
        "language": config.get("language"),
        "content_root": expected_content_root,
        "index_valid": index_valid,
        "config_valid": cfg_valid,
        "present": present,
        "missing": missing,
        "placeholder_count": len(strict_details["placeholder_files"]),
        "placeholder_files": strict_details["placeholder_files"],
        "pages_without_cite": strict_details["pages_without_cite"],
        "short_content_pages": strict_details["short_content_pages"],
        "secret_hits": strict_details["secret_hits"],
        "mojibake_hits": strict_details["mojibake_hits"],
        "unindexed_pages": strict_details["unindexed_pages"],
        "pages_missing_source_refs": strict_details["pages_missing_source_refs"],
        "missing_cited_refs": strict_details["missing_cited_refs"],
    }


def iter_wiki_project_roots(project_root: Path) -> Iterable[Path]:
    yielded: Set[Path] = set()
    project_root = project_root.resolve()
    if (project_root / ".spwiki").exists():
        yielded.add(project_root)
        yield project_root
    for current, dirnames, _ in os.walk(project_root):
        current_path = Path(current)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        if current_path.name == ".spwiki":
            root = current_path.parent.resolve()
            if root not in yielded:
                yielded.add(root)
                yield root
            dirnames[:] = []


def check_recursive(project_root: Path, strict: bool = False) -> Dict[str, object]:
    roots = list(iter_wiki_project_roots(project_root))
    if not roots:
        roots = [project_root.resolve()]
    results = [check(root, strict=strict) for root in roots]
    return {
        "project_root": str(project_root.resolve()),
        "recursive": True,
        "ready": all(item["ready"] for item in results),
        "wiki_count": len(results),
        "results": results,
    }


def print_not_ready(result: Dict[str, object]) -> None:
    if result.get("recursive"):
        for item in result.get("results", []):
            print_not_ready(item)
        return
    if result.get("missing"):
        print(f"missing for {result['project_root']}:")
        for item in result["missing"]:
            print(f"- {item}")
    if not result.get("index_valid"):
        print(f"index invalid or missing for {result['project_root']}")
    if not result.get("config_valid"):
        print(f"config invalid or missing for {result['project_root']}")
    for key in ("placeholder_files", "pages_without_cite", "short_content_pages", "unindexed_pages", "pages_missing_source_refs", "missing_cited_refs", "secret_hits", "mojibake_hits"):
        values = result.get(key) or []
        if values:
            print(f"{key} for {result['project_root']}:")
            for item in values:
                print(f"- {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether .spwiki core files, index, and evidence are ready.")
    parser.add_argument("project_root", help="Project root to check.")
    parser.add_argument("--json", action="store_true", help="Emit detailed JSON.")
    parser.add_argument("--strict", action="store_true", help="Fail on missing evidence, placeholders, short content, missing citations, or secret-like values.")
    parser.add_argument("--recursive", action="store_true", help="Check every discovered .spwiki under the project root.")
    args = parser.parse_args()

    result = check_recursive(Path(args.project_root), strict=args.strict) if args.recursive else check(Path(args.project_root), strict=args.strict)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("ready" if result["ready"] else "not ready")
        if not result["ready"]:
            print_not_ready(result)
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
