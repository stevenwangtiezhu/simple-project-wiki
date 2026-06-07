#!/usr/bin/env python3
"""Shared helpers for simple-project-wiki scripts."""

from __future__ import annotations

import hashlib
import json
import locale
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set


SCHEMA_VERSION = 2

DEFAULT_CONFIG = {
    "language": "zh",
    "profile": "deep",
    "auto_update_after_code_change": False,
    "token_strategy": "prefilter_batch",
    "index_schema_version": SCHEMA_VERSION,
    "strict_ready_required": True,
}

# Maps locale prefixes to the wiki language keys this skill recognizes.
SYSTEM_LANGUAGE_MAP = {
    "zh": "zh",
    "en": "en",
    "ko": "kr",
    "kr": "kr",
    "ja": "ja",
    "jp": "ja",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "pt": "pt",
    "ru": "ru",
    "it": "it",
}
FALLBACK_LANGUAGE = "en"


def detect_system_language() -> str:
    """Best-effort detect the OS language as a wiki language key.

    Returns a key such as zh, en, kr, ja. Falls back to en when the locale
    is unknown. The result is only a default; the user can override at init,
    and once .spwiki/config.json records a language all maintenance must use it.
    """
    candidates: List[str] = []
    for env_var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(env_var)
        if value:
            candidates.append(value)
    try:
        loc = locale.getlocale()[0]
    except Exception:
        loc = None
    if loc:
        candidates.append(loc)
    try:
        loc2 = locale.getdefaultlocale()[0]
    except Exception:
        loc2 = None
    if loc2:
        candidates.append(loc2)

    for raw in candidates:
        token = re.split(r"[._@:; ]", raw.strip().lower(), maxsplit=1)[0]
        if not token:
            continue
        prefix = token.split("-")[0]
        if token in SYSTEM_LANGUAGE_MAP:
            return SYSTEM_LANGUAGE_MAP[token]
        if prefix in SYSTEM_LANGUAGE_MAP:
            return SYSTEM_LANGUAGE_MAP[prefix]
        if "chinese" in token:
            return "zh"
        if "korean" in token:
            return "kr"
        if "japanese" in token:
            return "ja"
        if "english" in token:
            return "en"
    return FALLBACK_LANGUAGE

LANGUAGE_PROFILES = {
    "zh": {
        "root_docs": [
            {"key": "overview", "title": "项目概述", "filename": "项目概述.md"},
            {"key": "quick-start", "title": "快速开始", "filename": "快速开始.md"},
            {"key": "troubleshooting", "title": "故障排除指南", "filename": "故障排除指南.md"},
        ],
        "topics": {
            "architecture": "架构设计",
            "core-modules": "核心模块",
            "development-guide": "开发指南",
            "build-deploy": "构建与部署",
            "security": "安全与权限",
            "performance": "性能优化",
            "extension": "扩展开发",
            "api": "API接口文档",
            "api-layer": "API接口层",
            "data-model": "数据模型设计",
            "database": "数据库设计",
            "configuration": "配置管理",
            "operations": "部署与运维",
            "ui-components": "UI组件库",
            "views": "页面视图组件",
            "state": "状态管理系统",
            "utilities": "工具函数库",
            "desktop": "桌面应用集成",
            "mobile": "移动端应用架构",
            "routes": "页面路由系统",
            "native": "原生能力集成",
            "platform": "平台适配",
            "indexes": "索引矩阵",
            "api-reference": "API参考",
            "testing": "测试与调试",
        },
        "children": {
            "architecture": ["整体架构设计", "分层架构设计", "模块划分策略", "数据流设计"],
            "core-modules": ["核心模块", "用户管理模块", "系统管理模块"],
            "development-guide": ["开发指南", "开发流程", "编码规范", "调试与测试"],
            "build-deploy": ["构建与部署", "开发环境配置", "生产构建流程"],
            "security": ["安全与权限", "认证与授权", "安全配置"],
            "performance": ["性能优化", "性能监控与分析"],
            "extension": ["扩展开发", "API扩展开发", "第三方服务集成"],
            "api": ["API接口文档", "API路由矩阵", "用户管理API", "系统管理API"],
            "api-layer": ["API接口层", "API基础配置", "前后端接口对应"],
            "data-model": ["数据模型设计", "实体模型映射", "数据访问层设计"],
            "database": ["数据库设计", "数据库表结构设计", "数据访问层设计"],
            "configuration": ["配置管理", "配置项索引", "环境配置管理"],
            "operations": ["部署与运维", "环境准备与配置", "性能监控与告警"],
            "ui-components": ["UI组件库", "布局组件", "交互组件"],
            "views": ["页面视图组件", "认证页面系统", "主页布局设计"],
            "state": ["状态管理系统", "全局状态管理"],
            "utilities": ["工具函数库", "通用工具函数", "存储工具"],
            "desktop": ["桌面应用集成", "Electron主进程配置", "IPC进程间通信", "窗口管理系统"],
            "mobile": ["移动端应用架构", "应用入口与生命周期"],
            "routes": ["页面路由系统", "页面配置与导航"],
            "native": ["原生能力集成", "插件与平台能力"],
            "platform": ["平台适配", "条件编译策略"],
            "indexes": ["API路由矩阵", "权限认证矩阵", "配置项索引", "数据模型矩阵", "风险文件清单", "子项目依赖关系", "第三方服务索引"],
            "api-reference": ["API参考", "公共接口", "示例用法"],
            "testing": ["测试与调试", "验证入口", "测试缺口"],
        },
    },
    "en": {
        "root_docs": [
            {"key": "overview", "title": "Project Overview", "filename": "Project Overview.md"},
            {"key": "quick-start", "title": "Quick Start", "filename": "Quick Start.md"},
            {"key": "troubleshooting", "title": "Troubleshooting Guide", "filename": "Troubleshooting Guide.md"},
        ],
        "topics": {
            "architecture": "Architecture",
            "core-modules": "Core Modules",
            "development-guide": "Development Guide",
            "build-deploy": "Build and Deploy",
            "security": "Security and Permissions",
            "performance": "Performance",
            "extension": "Extension Development",
            "api": "API Documentation",
            "api-layer": "API Layer",
            "data-model": "Data Models",
            "database": "Database Design",
            "configuration": "Configuration",
            "operations": "Operations",
            "ui-components": "UI Components",
            "views": "Views and Pages",
            "state": "State Management",
            "utilities": "Utilities",
            "desktop": "Desktop Integration",
            "mobile": "Mobile Architecture",
            "routes": "Routing",
            "native": "Native Integrations",
            "platform": "Platform Adaptation",
            "indexes": "Index Matrices",
            "api-reference": "API Reference",
            "testing": "Testing and Debugging",
        },
        "children": {
            "architecture": ["Overall Architecture", "Layered Architecture", "Module Boundaries", "Data Flow"],
            "core-modules": ["Core Modules", "User Module", "System Module"],
            "development-guide": ["Development Guide", "Development Workflow", "Coding Conventions", "Debugging and Testing"],
            "build-deploy": ["Build and Deploy", "Development Environment", "Production Build"],
            "security": ["Security and Permissions", "Authentication and Authorization", "Security Configuration"],
            "performance": ["Performance", "Performance Monitoring"],
            "extension": ["Extension Development", "API Extension", "Third Party Integrations"],
            "api": ["API Documentation", "API Route Matrix", "User APIs", "System APIs"],
            "api-layer": ["API Layer", "API Base Configuration", "Frontend Backend API Mapping"],
            "data-model": ["Data Models", "Entity Model Mapping", "Data Access Design"],
            "database": ["Database Design", "Database Tables", "Data Access Design"],
            "configuration": ["Configuration", "Configuration Key Index", "Environment Configuration"],
            "operations": ["Operations", "Environment Setup", "Monitoring and Alerts"],
            "ui-components": ["UI Components", "Layout Components", "Interaction Components"],
            "views": ["Views and Pages", "Authentication Pages", "Home Layout"],
            "state": ["State Management", "Global State"],
            "utilities": ["Utilities", "Common Utilities", "Storage Utilities"],
            "desktop": ["Desktop Integration", "Electron Main Process", "IPC", "Window Management"],
            "mobile": ["Mobile Architecture", "App Entry and Lifecycle"],
            "routes": ["Routing", "Page Configuration and Navigation"],
            "native": ["Native Integrations", "Plugins and Platform Capabilities"],
            "platform": ["Platform Adaptation", "Conditional Compilation"],
            "indexes": ["API Route Matrix", "Auth Matrix", "Configuration Key Index", "Data Model Matrix", "Risk File List", "Subproject Dependencies", "Third Party Services"],
            "api-reference": ["API Reference", "Public Interfaces", "Examples"],
            "testing": ["Testing and Debugging", "Validation Entrypoints", "Test Gaps"],
        },
    },
}

COMMON_TOPIC_KEYS = ["architecture", "core-modules", "development-guide", "build-deploy", "security", "performance", "extension"]
BACKEND_TOPIC_KEYS = ["api", "database", "data-model", "configuration", "operations"]
FRONTEND_TOPIC_KEYS = ["api-layer", "ui-components", "views", "state", "utilities", "configuration"]
MOBILE_TOPIC_KEYS = ["mobile", "routes", "native", "platform"]
DESKTOP_TOPIC_KEYS = ["desktop"]
LIBRARY_TOPIC_KEYS = ["api-reference", "core-modules", "data-model", "extension", "testing"]
MATRIX_TOPIC_KEYS = ["indexes"]
LIGHT_TOPIC_KEYS = ["architecture", "core-modules", "development-guide", "build-deploy", "security"]

DEFAULT_RISK_KEYWORDS = {
    "auth": ["auth", "token", "login", "认证", "授权", "密码", "permission"],
    "payment": ["pay", "payment", "wallet", "refund", "提现", "红包", "支付", "钱包"],
    "file-io": ["upload", "download", "path traversal", "上传", "下载", "file"],
    "sql": ["sql", "mapper", "allowmultiqueries", "${", "数据库", "query"],
    "deserialization": ["fastjson", "autotype", "deserialize", "反序列化"],
    "secrets": ["secret", "password", "appid", "appsecret", "api_key", "private key", "密钥"],
    "admin": ["admin", "shiro", "rbac", "审核", "后台"],
}

DEFAULT_SEARCH_HINTS = {
    "synonyms": {},
    "topic_hints": {},
    "config_key_prefixes": [
        "app",
        "auth",
        "aws",
        "azure",
        "babel",
        "build",
        "compiler",
        "database",
        "datasource",
        "db",
        "django",
        "electron",
        "eslint",
        "fastapi",
        "flask",
        "gcp",
        "jwt",
        "logging",
        "management",
        "mybatis",
        "package",
        "redis",
        "server",
        "shiro",
        "spring",
        "tsconfig",
        "uni",
        "vite",
        "vue",
        "webpack",
    ],
}

PLACEHOLDER_RE = re.compile(
    r"\bTODO\b|TODO:|补充本文引用|基于真实代码说明|列出相关目录|说明关键类|用文字或 Mermaid 图说明|"
    r"replace this|fill this|placeholder|based on real code|describe the key",
    re.IGNORECASE,
)

SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|appsecret|client[_-]?secret)"
    r"\b\s*[:=]\s*['\"]?([A-Za-z0-9_./+=@!#$%^&*:-]{8,})"
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

# Runs of three or more literal '?' or the Unicode replacement char signal that
# non-ASCII text (CJK/Korean/etc.) was written through a non-UTF-8 stream and lost.
MOJIBAKE_RE = re.compile(r"\?{3,}|�")


def mojibake_hits(text: str) -> List[Dict[str, str]]:
    hits: List[Dict[str, str]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        match = MOJIBAKE_RE.search(line)
        if match:
            kind = "replacement-char" if "�" in match.group(0) else "question-run"
            hits.append({"line": str(index), "kind": kind})
    return hits


def read_text_utf8(path: Path) -> str:
    """Read a wiki file as UTF-8, tolerating a BOM. Wiki files are always UTF-8."""
    return path.read_text(encoding="utf-8-sig")


def write_text_utf8(path: Path, text: str) -> None:
    """Write a wiki file as UTF-8 regardless of the host console codepage.

    Writing through Path.write_text with an explicit encoding avoids the
    Windows default codepage (cp936/cp1252) that turns CJK/Korean into '?'.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json_file(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write_json_file(path: Path, data: Dict[str, object], force: bool, created: List[str], skipped: List[str]) -> None:
    if path.exists() and not force:
        skipped.append(str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    created.append(str(path))


def load_config(project_root: Path) -> Dict[str, object]:
    config = dict(DEFAULT_CONFIG)
    config.update(load_json_file(project_root / ".spwiki" / "config.json"))
    language = str(config.get("language") or "zh")
    config["language"] = language
    config.setdefault("content_root", f"{language}/content")
    return config


def content_root_rel(config: Dict[str, object]) -> str:
    language = str(config.get("language") or "zh")
    value = str(config.get("content_root") or f"{language}/content")
    return value.replace("\\", "/").strip("/")


def content_root_path(project_root: Path, config: Optional[Dict[str, object]] = None) -> Path:
    config = config or load_config(project_root)
    return project_root / ".spwiki" / content_root_rel(config)


def language_profile(language: str) -> Dict[str, object]:
    return LANGUAGE_PROFILES.get(language, LANGUAGE_PROFILES["en"])


def localized_topic_title(topic_key: str, language: str) -> str:
    profile = language_profile(language)
    topics = profile.get("topics", {})
    if isinstance(topics, dict):
        return str(topics.get(topic_key, topic_key.replace("-", " ").title()))
    return topic_key.replace("-", " ").title()


def root_docs(language: str) -> List[Dict[str, str]]:
    profile = language_profile(language)
    docs = profile.get("root_docs", [])
    return [dict(item) for item in docs if isinstance(item, dict)]


def default_topic_keys(project: Dict[str, object], profile: str) -> List[str]:
    stack = set(project.get("stack") or [])
    if profile == "light":
        return LIGHT_TOPIC_KEYS[:]

    keys: List[str] = []
    keys.extend(COMMON_TOPIC_KEYS)

    if stack.intersection({"java-maven", "java-gradle", "spring-boot", "mybatis", "shiro", "kotlin", "python", "go", "rust", "php", "ruby"}):
        keys.extend(BACKEND_TOPIC_KEYS)
    if stack.intersection({"node", "vue", "react", "vite", "webpack"}):
        keys.extend(FRONTEND_TOPIC_KEYS)
    if "electron" in stack:
        keys.extend(DESKTOP_TOPIC_KEYS)
    if "uni-app" in stack or "app-manifest" in stack:
        keys.extend(MOBILE_TOPIC_KEYS)
    if not stack or stack.intersection({"rust", "go", "python", "node", "php", "ruby"}):
        keys.extend(LIBRARY_TOPIC_KEYS)
    if profile == "deep":
        keys.extend(MATRIX_TOPIC_KEYS)

    return unique_list(keys)


def default_children(topic_key: str, profile: str, language: str) -> List[str]:
    if profile == "light":
        return [localized_topic_title(topic_key, language)]
    children = language_profile(language).get("children", {})
    values = children.get(topic_key, [localized_topic_title(topic_key, language)]) if isinstance(children, dict) else []
    values = [str(item) for item in values]
    if profile == "balanced":
        return values[:2] or [localized_topic_title(topic_key, language)]
    return values or [localized_topic_title(topic_key, language)]


def load_topic_overrides(project_root: Path) -> Dict[str, object]:
    return load_json_file(project_root / ".spwiki" / "topic-overrides.json")


def topic_records(project: Dict[str, object], output_project_root: Path, profile: str, language: str) -> List[Dict[str, object]]:
    records = [
        {
            "key": key,
            "title": localized_topic_title(key, language),
            "children": default_children(key, profile, language),
        }
        for key in default_topic_keys(project, profile)
    ]
    overrides = load_topic_overrides(output_project_root)
    if isinstance(overrides.get("topics"), list) and overrides["topics"]:
        records = normalize_topic_records(overrides["topics"], language)
    if isinstance(overrides.get("append_topics"), list) and overrides["append_topics"]:
        records.extend(normalize_topic_records(overrides["append_topics"], language))
    return dedupe_topic_records(records)


def normalize_topic_records(items: Sequence[object], language: str) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    for item in items:
        if isinstance(item, str):
            records.append({"key": item, "title": localized_topic_title(item, language), "children": [localized_topic_title(item, language)]})
        elif isinstance(item, dict):
            key = str(item.get("key") or item.get("title") or "custom")
            title = str(item.get("title") or localized_topic_title(key, language))
            raw_children = item.get("children") or item.get("pages") or [title]
            children = [str(child.get("title", "")) if isinstance(child, dict) else str(child) for child in raw_children if child]
            records.append({"key": key, "title": title, "children": children or [title]})
    return records


def dedupe_topic_records(records: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    seen: Set[str] = set()
    result: List[Dict[str, object]] = []
    for record in records:
        title = str(record.get("title") or record.get("key") or "")
        if not title or title in seen:
            continue
        seen.add(title)
        result.append(record)
    return result


def filename_for_title(title: str) -> str:
    title = title.strip().replace("/", "-").replace("\\", "-")
    return f"{title}.md"


def default_project_sidecar_files() -> Dict[str, object]:
    return {
        "topic-overrides.json": {
            "topics": [],
            "append_topics": [],
            "_comment": "Optional project-specific topic structure. Leave empty to use stack-based defaults.",
        },
        "project-aliases.json": {
            "aliases": {},
            "_comment": "Map project terms to synonyms, modules, pages, symbols, or routes.",
        },
        "search-hints.json": dict(DEFAULT_SEARCH_HINTS),
        "risk-profile.json": {
            "risk_flags": dict(DEFAULT_RISK_KEYWORDS),
            "_comment": "Override or extend project-specific risk flags and matching keywords.",
        },
    }


def load_search_hints(project_root: Path) -> Dict[str, object]:
    hints = dict(DEFAULT_SEARCH_HINTS)
    raw = load_json_file(project_root / ".spwiki" / "search-hints.json")
    for key, value in raw.items():
        if key == "config_key_prefixes" and isinstance(value, list):
            hints[key] = [str(item) for item in value]
        elif isinstance(value, dict):
            merged = dict(hints.get(key, {})) if isinstance(hints.get(key), dict) else {}
            merged.update(value)
            hints[key] = merged
        else:
            hints[key] = value
    return hints


def load_project_aliases(project_root: Path) -> Dict[str, List[str]]:
    raw = load_json_file(project_root / ".spwiki" / "project-aliases.json")
    aliases = raw.get("aliases", raw)
    result: Dict[str, List[str]] = {}
    if not isinstance(aliases, dict):
        return result
    for key, value in aliases.items():
        terms = flatten_strings(value)
        terms.append(str(key))
        result[str(key)] = unique_list(terms)
    return result


def flatten_strings(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: List[str] = []
        for item in value.values():
            values.extend(flatten_strings(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(flatten_strings(item))
        return values
    return [str(value)]


def expand_query_terms(project_root: Path, query: str) -> List[str]:
    terms = tokenize(query)
    lowered = query.lower()
    aliases = load_project_aliases(project_root)
    hints = load_search_hints(project_root)
    synonyms = hints.get("synonyms", {})
    if isinstance(synonyms, dict):
        for key, values in synonyms.items():
            alias_terms = flatten_strings(values) + [str(key)]
            if str(key).lower() in lowered or any(term.lower() in lowered for term in alias_terms):
                terms.extend(alias_terms)
    for key, values in aliases.items():
        if key.lower() in lowered or any(value.lower() in lowered for value in values):
            terms.extend(values)
    return unique_list(tokenize(" ".join(terms)))


def load_risk_keywords(project_root: Path) -> Dict[str, List[str]]:
    raw = load_json_file(project_root / ".spwiki" / "risk-profile.json")
    source = raw.get("risk_flags", raw.get("risks", raw))
    result = {key: list(values) for key, values in DEFAULT_RISK_KEYWORDS.items()}
    if isinstance(source, dict):
        for key, value in source.items():
            terms = flatten_strings(value)
            if terms:
                result[str(key)] = unique_list(result.get(str(key), []) + terms)
    elif isinstance(source, list):
        for item in source:
            if isinstance(item, dict) and item.get("name"):
                result[str(item["name"])] = unique_list(flatten_strings(item.get("keywords", [])))
    return result


def topic_hints_for(project_root: Path, changed_files: List[str]) -> Set[str]:
    hints = load_search_hints(project_root).get("topic_hints", {})
    result: Set[str] = set()
    if not isinstance(hints, dict):
        return result
    for file_path in changed_files:
        lowered = normalize_path(file_path).lower()
        for needle, topics in hints.items():
            if str(needle).lower() in lowered:
                result.update(flatten_strings(topics))
    return result


def normalize_path(path: str) -> str:
    value = path.strip().strip("<>").replace("\\", "/")
    if "#" in value:
        value = value.split("#", 1)[0]
    return value.strip("/")


def normalize_ref(ref: str) -> str:
    return normalize_path(ref)


def resolve_source_path(project_root: Path, ref: str) -> Optional[Path]:
    normalized = normalize_ref(ref)
    if not normalized:
        return None
    if re.match(r"^[a-zA-Z]+://", normalized):
        return None
    path = Path(normalized)
    if path.is_absolute():
        return path
    return project_root / normalized


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_list(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")


def cjk_bigrams(text: str) -> List[str]:
    grams: List[str] = []
    for run in CJK_RUN_RE.findall(text):
        grams.extend(run[index : index + 2] for index in range(len(run) - 1))
    return grams


def tokenize(query: str) -> List[str]:
    query = query.lower()
    tokens = [token for token in re.split(r"[^0-9a-zA-Z_\-\u4e00-\u9fff/.]+", query) if token]
    tokens.extend(cjk_bigrams(query))
    return sorted(set(tokens), key=len, reverse=True)


def secret_hits(text: str) -> List[Dict[str, str]]:
    hits: List[Dict[str, str]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if PRIVATE_KEY_RE.search(line):
            hits.append({"line": str(index), "kind": "private-key"})
        match = SECRET_RE.search(line)
        if match:
            hits.append({"line": str(index), "kind": match.group(1)})
    return hits


def strip_markdown_noise(text: str) -> str:
    text = re.sub(r"<cite>.*?</cite>", "", text, flags=re.DOTALL | re.IGNORECASE)
    lines: List[str] = []
    skip_toc = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in {"## 目录", "## Table of Contents"}:
            skip_toc = True
            continue
        if skip_toc and stripped.startswith("## "):
            skip_toc = False
        if skip_toc:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("```"):
            continue
        if not stripped:
            continue
        if "file://" in stripped:
            continue
        lines.append(stripped)
    return "\n".join(lines)
