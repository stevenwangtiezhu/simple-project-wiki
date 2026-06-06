#!/usr/bin/env python3
"""Prefilter candidate wiki pages for low-token simple-project-wiki-update work."""

from __future__ import annotations

import argparse
import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Set

from wiki_common import load_config, load_json_file, normalize_path, resolve_source_path, sha256_file, topic_hints_for


DEFAULT_TOPIC_HINTS = {
    "api": ["API Documentation", "API接口文档", "API Layer", "API接口层"],
    "controller": ["API Documentation", "API接口文档", "Security and Permissions", "安全与权限"],
    "config": ["Configuration", "配置管理", "Build and Deploy", "构建与部署", "Operations", "部署与运维"],
    "entity": ["Data Models", "数据模型设计", "Database Design", "数据库设计"],
    "mapper": ["Database Design", "数据库设计"],
    "service": ["Core Modules", "核心模块", "Architecture", "架构设计"],
    "store": ["State Management", "状态管理系统"],
    "view": ["Views and Pages", "页面视图组件"],
    "component": ["UI Components", "UI组件库", "Views and Pages", "页面视图组件"],
    "router": ["Views and Pages", "页面视图组件", "Architecture", "架构设计"],
    "security": ["Security and Permissions", "安全与权限"],
    "pay": ["Security and Permissions", "安全与权限", "Core Modules", "核心模块"],
}


def load_json(path: Path) -> Dict[str, object]:
    return load_json_file(path)


def normalize(path: str) -> str:
    return normalize_path(path)


def current_fingerprint(project_root: Path, ref: str, old: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    normalized = normalize(ref)
    path = resolve_source_path(project_root, normalized)
    record: Dict[str, object] = {
        "path": normalized,
        "exists": False,
        "sha256": None,
        "mtime_ns": None,
        "size": None,
    }
    if path is None or not path.exists() or not path.is_file():
        return record
    stat = path.stat()
    record.update({
        "exists": True,
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
    })
    if (
        old is not None
        and old.get("sha256")
        and old.get("size") == stat.st_size
        and old.get("mtime_ns") == stat.st_mtime_ns
    ):
        record["sha256"] = old.get("sha256")
    else:
        record["sha256"] = sha256_file(path)
    return record


def old_fingerprint_map(page: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    result: Dict[str, Dict[str, object]] = {}
    fingerprints = page.get("source_fingerprints", [])
    if isinstance(fingerprints, list):
        for item in fingerprints:
            if isinstance(item, dict) and item.get("path"):
                result[normalize(str(item["path"]))] = item
    return result


def fingerprint_status(project_root: Path, page: Dict[str, object]) -> List[Dict[str, object]]:
    refs = [normalize(str(ref)) for ref in page.get("source_refs", [])]
    old_map = old_fingerprint_map(page)
    statuses: List[Dict[str, object]] = []
    for ref in refs:
        old = old_map.get(ref)
        current = current_fingerprint(project_root, ref, old)
        if old is None:
            status = "new-ref"
        elif not current["exists"]:
            status = "missing"
        elif old.get("sha256") == current.get("sha256"):
            status = "unchanged"
        else:
            status = "changed"
        statuses.append({
            "path": ref,
            "status": status,
            "old_sha256": old.get("sha256") if old else None,
            "current_sha256": current.get("sha256"),
            "old_mtime_ns": old.get("mtime_ns") if old else None,
            "current_mtime_ns": current.get("mtime_ns"),
            "exists": current.get("exists"),
        })
    return statuses


def default_topic_hints_for(changed_files: List[str]) -> Set[str]:
    hints: Set[str] = set()
    for file_path in changed_files:
        lowered = normalize(file_path).lower()
        for key, topics in DEFAULT_TOPIC_HINTS.items():
            if key in lowered:
                hints.update(topics)
    return hints


def page_search_blob(page: Dict[str, object]) -> str:
    parts = [
        str(page.get("path", "")),
        str(page.get("title", "")),
        str(page.get("topic", "")),
        str(page.get("summary", "")),
    ]
    for key in ("aliases", "tags", "config_keys", "risk_flags", "source_refs"):
        value = page.get(key, [])
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
    for key in ("headings", "routes", "api_endpoints", "symbols"):
        value = page.get(key, [])
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    parts.extend(str(v) for v in item.values())
                else:
                    parts.append(str(item))
    return "\n".join(parts).lower()


def related_glob_hit(page: Dict[str, object], changed_file: str) -> bool:
    globs = page.get("related_globs", [])
    if not isinstance(globs, list):
        return False
    changed = normalize(changed_file)
    return any(fnmatch(changed, normalize(str(pattern))) for pattern in globs)


def score_page(page: Dict[str, object], changed_files: List[str], hints: Set[str], statuses: List[Dict[str, object]]) -> int:
    score = 0
    page_path = str(page.get("path", ""))
    topic = str(page.get("topic", ""))
    refs = [normalize(str(ref)) for ref in page.get("source_refs", [])]
    blob = page_search_blob(page)

    for changed in changed_files:
        changed_norm = normalize(changed)
        if changed_norm in refs:
            score += 100
        if related_glob_hit(page, changed_norm):
            score += 90
        if changed_norm and changed_norm in page_path:
            score += 40
        stem = Path(changed_norm).stem.lower()
        if stem and stem in page_path.lower():
            score += 15
        if stem and stem in blob:
            score += 25
        parent = Path(changed_norm).parent.name.lower()
        if parent and parent in blob:
            score += 10

    if any(item["status"] == "changed" for item in statuses):
        score += 120
    if any(item["status"] in {"missing", "new-ref"} for item in statuses):
        score += 80
    if topic in hints:
        score += 20
    if topic == "root":
        score += 5
    return score


def plan(project_root: Path, changed_files: List[str], limit: int) -> Dict[str, object]:
    project_root = project_root.resolve()
    wiki_root = project_root / ".spwiki"
    config = load_config(project_root)
    index = load_json(wiki_root / "wiki-index.json")
    pages = index.get("pages", []) if isinstance(index.get("pages"), list) else []
    hints = default_topic_hints_for(changed_files) | topic_hints_for(project_root, changed_files)

    candidates = []
    skipped = []
    referenced_changed_files: Set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            continue
        statuses = fingerprint_status(project_root, page)
        has_source_change = any(item["status"] in {"changed", "missing", "new-ref"} for item in statuses)
        has_source_refs = bool(statuses)
        score = score_page(page, changed_files, hints, statuses)
        refs = {normalize(str(ref)) for ref in page.get("source_refs", [])}
        referenced_changed_files.update({normalize(changed) for changed in changed_files if normalize(changed) in refs})
        record = {
            "path": page.get("path"),
            "title": page.get("title"),
            "topic": page.get("topic"),
            "score": score,
            "source_refs": page.get("source_refs", []),
            "source_status": statuses,
            "summary": page.get("summary", ""),
            "risk_flags": page.get("risk_flags", []),
            "tags": page.get("tags", []),
        }
        if has_source_change or score > 0:
            candidates.append(record)
        else:
            reason = "source sha256 unchanged" if has_source_refs else "no source refs to compare"
            skipped.append({
                "path": page.get("path"),
                "title": page.get("title"),
                "reason": reason,
            })

    candidates.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
    if limit > 0:
        candidates = candidates[:limit]

    unlinked_changed_files = [
        changed
        for changed in changed_files
        if normalize(changed) not in referenced_changed_files
    ]
    new_page_candidates = [
        {
            "changed_file": changed,
            "suggested_topics": sorted(default_topic_hints_for([changed]) | topic_hints_for(project_root, [changed])),
            "reason": "changed file is not cited by any indexed wiki page",
        }
        for changed in unlinked_changed_files
    ]

    return {
        "project_root": str(project_root),
        "auto_update_after_code_change": bool(config.get("auto_update_after_code_change", False)),
        "token_strategy": config.get("token_strategy", "prefilter_batch"),
        "changed_files": changed_files,
        "topic_hints": sorted(hints),
        "candidate_count": len(candidates),
        "skipped_count": len(skipped),
        "unlinked_changed_files": unlinked_changed_files,
        "new_page_candidates": new_page_candidates,
        "candidates": candidates,
        "skipped": skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan low-token candidate wiki pages for simple-project-wiki-update.")
    parser.add_argument("project_root", help="Project root containing .spwiki.")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed source file path. Repeat as needed.")
    parser.add_argument("--limit", type=int, default=30, help="Maximum candidate pages to emit. Use 0 for no limit.")
    args = parser.parse_args()

    changed_files = [normalize(path) for path in args.changed_file]
    result = plan(Path(args.project_root), changed_files, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
