#!/usr/bin/env python3
"""Build .spwiki/wiki-index.json from wiki Markdown files."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from wiki_common import (
    SCHEMA_VERSION,
    content_root_path,
    content_root_rel,
    load_config,
    load_risk_keywords,
    load_search_hints,
    normalize_ref,
    resolve_source_path,
    sha256_file,
    strip_markdown_noise,
    unique_list,
)


TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.MULTILINE)
FILE_LINK_RE = re.compile(r"file://(?:<([^>]+)>|([^)\]\s]+))")
CITE_RE = re.compile(r"<cite>(.*?)</cite>", re.DOTALL | re.IGNORECASE)
HTTP_ROUTE_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+(/[A-Za-z0-9_./{}:<>${}-]+)", re.IGNORECASE)
ANNOTATION_ROUTE_RE = re.compile(r"@(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\s*\([^)]*[\"']([^\"']+)[\"']", re.IGNORECASE)
BACKTICK_ROUTE_RE = re.compile(r"`(/[A-Za-z0-9_./{}:<>${}-]+)`")
CONFIG_KEY_RE = re.compile(r"\b[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+){1,}\b")
SYMBOL_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9_]*(?:Controller|Service|Mapper|Entity|Config|Util|Handler|Listener|Application|Store|Module|Component|View|Page|Provider|Repository|Manager|Factory|Client|Adapter|Middleware|Router|Schema|Model)|"
    r"[a-z][A-Za-z0-9_]*(?:Service|Store|Module|Component|Provider|Repository|Manager|Factory|Client|Adapter|Middleware|Router|Schema|Model))\b"
)

TAG_KEYWORDS = {
    "spring": ["spring", "spring boot", "@controller", "@service"],
    "mybatis": ["mybatis", "mapper.xml", "basemapper"],
    "shiro": ["shiro"],
    "vue": ["vue", ".vue"],
    "react": ["react", "jsx", "tsx"],
    "electron": ["electron", "ipcmain", "browserwindow"],
    "uni-app": ["uni-app", "pages.json", "app-plus", "mp-weixin"],
    "websocket": ["websocket", "ws", "j-im", "t-io"],
    "redis": ["redis", "jedis"],
    "mysql": ["mysql", "datasource", "数据库"],
    "python": ["python", "django", "flask", "fastapi"],
    "go": ["go.mod", "func main"],
    "rust": ["cargo.toml", "fn main"],
    "security": ["安全", "auth", "token", "认证", "授权", "password"],
}


def as_posix(path: Path) -> str:
    return path.as_posix()


def title_for(text: str, path: Path) -> str:
    match = TITLE_RE.search(text)
    if match:
        return match.group(1).strip()
    return path.stem


def topic_for(markdown_path: Path, content_root: Path) -> str:
    rel = markdown_path.relative_to(content_root)
    if len(rel.parts) <= 1:
        return "root"
    return rel.parts[0]


def slugify_heading(title: str, used: Dict[str, int]) -> str:
    slug = re.sub(r"[^\w\-\u4e00-\u9fff ]+", "", title.lower()).strip()
    slug = re.sub(r"\s+", "-", slug) or "section"
    count = used.get(slug, 0)
    used[slug] = count + 1
    return slug if count == 0 else f"{slug}-{count}"


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def source_refs_for(text: str) -> List[str]:
    refs = set()
    cite_blocks = CITE_RE.findall(text)
    searchable = "\n".join(cite_blocks) if cite_blocks else text
    for match in FILE_LINK_RE.finditer(searchable):
        ref = normalize_ref(match.group(1) or match.group(2) or "")
        if ref:
            refs.add(ref)
    return sorted(refs)


def parse_line_anchor(anchor: str) -> Dict[str, Optional[int]]:
    start = None
    end = None
    match = re.search(r"L(\d+)(?:-L?(\d+))?", anchor, re.IGNORECASE)
    if match:
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
    return {"line_start": start, "line_end": end}


def source_spans_for(text: str) -> List[Dict[str, object]]:
    spans = []
    cite_blocks = CITE_RE.findall(text)
    searchable = "\n".join(cite_blocks) if cite_blocks else text
    for match in FILE_LINK_RE.finditer(searchable):
        raw = (match.group(1) or match.group(2) or "").strip().strip("<>").replace("\\", "/")
        path = normalize_ref(raw)
        span: Dict[str, object] = {"path": path, "anchor": None, "line_start": None, "line_end": None}
        if "#" in raw:
            anchor = raw.split("#", 1)[1]
            span["anchor"] = anchor
            span.update(parse_line_anchor(anchor))
        if path:
            spans.append(span)
    return spans


def fingerprint_for(project_root: Path, ref: str) -> Dict[str, object]:
    normalized = normalize_ref(ref)
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
        "sha256": sha256_file(path),
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
    })
    return record


def fingerprints_for(project_root: Path, refs: List[str]) -> List[Dict[str, object]]:
    return [fingerprint_for(project_root, ref) for ref in refs]


def headings_for(text: str) -> List[Dict[str, object]]:
    matches = list(HEADING_RE.finditer(text))
    used: Dict[str, int] = {}
    headings: List[Dict[str, object]] = []
    for index, match in enumerate(matches):
        title = match.group(2).strip()
        start_line = line_for_offset(text, match.start())
        if index + 1 < len(matches):
            end_line = max(start_line, line_for_offset(text, matches[index + 1].start()) - 1)
        else:
            end_line = text.count("\n") + 1
        headings.append({
            "level": len(match.group(1)),
            "title": title,
            "anchor": slugify_heading(title, used),
            "line_start": start_line,
            "line_end": end_line,
        })
    return headings


def tags_for(text: str, topic: str, refs: List[str]) -> List[str]:
    haystack = "\n".join([text, topic, " ".join(refs)]).lower()
    tags = [tag for tag, needles in TAG_KEYWORDS.items() if any(needle in haystack for needle in needles)]
    if topic and topic != "root":
        tags.append(topic)
    return unique_list(sorted(tags))


def aliases_for(title: str, topic: str, headings: List[Dict[str, object]], refs: List[str]) -> List[str]:
    values = [title, topic]
    values.extend(str(item.get("title", "")) for item in headings[:12])
    values.extend(Path(ref).stem for ref in refs)
    return unique_list(values)


def related_globs_for(refs: List[str]) -> List[str]:
    globs: List[str] = []
    for ref in refs:
        parent = Path(normalize_ref(ref)).parent.as_posix()
        if parent and parent not in {"", "."}:
            globs.append(f"{parent}/*")
    return unique_list(sorted(globs))


def routes_for(text: str) -> List[Dict[str, str]]:
    routes: List[Dict[str, str]] = []
    for method, path in HTTP_ROUTE_RE.findall(text):
        routes.append({"method": method.upper(), "path": path})
    for annotation, path in ANNOTATION_ROUTE_RE.findall(text):
        method = {
            "GetMapping": "GET",
            "PostMapping": "POST",
            "PutMapping": "PUT",
            "DeleteMapping": "DELETE",
            "PatchMapping": "PATCH",
        }.get(annotation, "ANY")
        routes.append({"method": method, "path": path})
    for path in BACKTICK_ROUTE_RE.findall(text):
        routes.append({"method": "ANY", "path": path})

    seen = set()
    result = []
    for route in routes:
        key = (route["method"], route["path"])
        if key not in seen:
            seen.add(key)
            result.append(route)
    return result


def symbols_for(text: str, refs: List[str]) -> List[Dict[str, str]]:
    symbols = [{"name": Path(ref).stem, "kind": "file"} for ref in refs if Path(ref).stem]
    for symbol in SYMBOL_RE.findall(text):
        symbols.append({"name": symbol, "kind": "text"})

    seen = set()
    result = []
    for symbol in symbols:
        key = (symbol["name"], symbol["kind"])
        if key not in seen:
            seen.add(key)
            result.append(symbol)
    return result[:80]


def config_keys_for(text: str, project_root: Path) -> List[str]:
    keys = CONFIG_KEY_RE.findall(text)
    prefixes = set(str(item).lower() for item in load_search_hints(project_root).get("config_key_prefixes", []))
    result = []
    for key in keys:
        lower = key.lower()
        if lower.startswith("file.") or lower.startswith("http.") or lower.startswith("https."):
            continue
        if re.search(r"\.(md|java|js|ts|vue|py|go|rs|json|xml|yml|yaml)$", lower):
            continue
        first = lower.split(".", 1)[0]
        if prefixes and first not in prefixes:
            continue
        result.append(key)
    return unique_list(sorted(result))[:80]


def risk_flags_for(text: str, refs: List[str], project_root: Path) -> List[str]:
    haystack = "\n".join([text, " ".join(refs)]).lower()
    keywords = load_risk_keywords(project_root)
    return unique_list(sorted([flag for flag, needles in keywords.items() if any(str(needle).lower() in haystack for needle in needles)]))


def summary_for(text: str, max_len: int = 220) -> str:
    cleaned = strip_markdown_noise(text)
    for paragraph in re.split(r"\n{2,}|\n", cleaned):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        paragraph = re.sub(r"\s+", " ", paragraph)
        if len(paragraph) > max_len:
            return paragraph[: max_len - 1].rstrip() + "..."
        return paragraph
    return ""


def page_record(markdown_path: Path, project_root: Path, wiki_root: Path, content_root: Path) -> Dict[str, object]:
    text = markdown_path.read_text(encoding="utf-8-sig", errors="ignore").lstrip("\ufeff")
    source_refs = source_refs_for(text)
    headings = headings_for(text)
    title = title_for(text, markdown_path)
    topic = topic_for(markdown_path, content_root)
    routes = routes_for(text)
    return {
        "path": as_posix(markdown_path.relative_to(wiki_root)),
        "title": title,
        "topic": topic,
        "summary": summary_for(text),
        "aliases": aliases_for(title, topic, headings, source_refs),
        "tags": tags_for(text, topic, source_refs),
        "routes": routes,
        "api_endpoints": routes,
        "symbols": symbols_for(text, source_refs),
        "config_keys": config_keys_for(text, project_root),
        "risk_flags": risk_flags_for(text, source_refs, project_root),
        "source_refs": source_refs,
        "source_spans": source_spans_for(text),
        "source_fingerprints": fingerprints_for(project_root, source_refs),
        "related_globs": related_globs_for(source_refs),
        "headings": headings,
    }


def build_index(project_root: Path, language: Optional[str] = None) -> Dict[str, object]:
    project_root = project_root.resolve()
    config = load_config(project_root)
    if language:
        config["language"] = language
        config["content_root"] = f"{language}/content"
    wiki_root = project_root / ".spwiki"
    content_root = content_root_path(project_root, config)
    if not content_root.exists():
        raise SystemExit(f"Wiki content root not found: {content_root}")

    pages = [
        page_record(path, project_root, wiki_root, content_root)
        for path in sorted(content_root.rglob("*.md"))
        if path.is_file()
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "language": config["language"],
        "content_root": content_root_rel(config),
        "project_root": str(project_root),
        "project_name": project_root.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "simple-project-wiki/scripts/build_wiki_index.py",
        "pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build .spwiki/wiki-index.json from wiki Markdown.")
    parser.add_argument("project_root", help="Project root containing .spwiki.")
    parser.add_argument("--language", help="Override wiki language folder. Defaults to .spwiki/config.json language.")
    parser.add_argument("--output", help="Optional output file. Default: <project-root>/.spwiki/wiki-index.json.")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    index = build_index(project_root, args.language)
    output = Path(args.output) if args.output else project_root.resolve() / ".spwiki" / "wiki-index.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "content_root": index["content_root"],
        "page_count": len(index["pages"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
