#!/usr/bin/env python3
"""Create .wiki content skeletons from a scan JSON file."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from wiki_common import (
    DEFAULT_CONFIG,
    content_root_path,
    default_project_sidecar_files,
    filename_for_title,
    load_config,
    root_docs,
    topic_records,
    write_json_file,
)


def placeholder(title: str, project: Dict[str, object], language: str) -> str:
    cite_files = project.get("config_files") or project.get("entrypoints") or []
    cite_lines = "\n".join(f"- [TODO: {path}](file://{path})" for path in cite_files[:8])
    if not cite_lines:
        cite_lines = "- TODO: add real source or configuration files cited by this page"

    if language == "zh":
        return f"""# {title}

<cite>
**本文引用的文件**
{cite_lines}
</cite>

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细组件分析](#详细组件分析)
6. [依赖关系分析](#依赖关系分析)
7. [性能考虑](#性能考虑)
8. [故障排查指南](#故障排查指南)
9. [结论](#结论)
10. [附录](#附录)

## 简介
TODO: 基于真实代码说明 `{project.get("name", "project")}` 中与“{title}”相关的职责、范围和维护价值。

## 项目结构
TODO: 列出相关目录、入口文件、配置文件和源码位置。

## 核心组件
TODO: 说明关键类、组件、函数、服务、模块或配置项。

## 架构总览
TODO: 用文字或 Mermaid 图说明组件关系。

## 详细组件分析
TODO: 分析主要流程、数据结构、接口、状态变化和边界条件。

## 依赖关系分析
TODO: 说明内部依赖、外部库、服务、配置和跨模块关系。

## 性能考虑
TODO: 记录真实代码中可见的性能路径、缓存、异步、批处理或潜在瓶颈。

## 故障排查指南
TODO: 给出基于代码和配置的排查入口。

## 结论
TODO: 总结维护者需要记住的关键事实。

## 附录
TODO: 补充命令、字段、接口清单或引用来源。
"""

    return f"""# {title}

<cite>
**Referenced files**
{cite_lines}
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Analysis](#detailed-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting](#troubleshooting)
9. [Conclusion](#conclusion)
10. [Appendix](#appendix)

## Introduction
TODO: Describe the responsibilities, scope, and maintenance value of `{project.get("name", "project")}` for "{title}" based on real code.

## Project Structure
TODO: List the relevant directories, entrypoints, configuration files, and source locations.

## Core Components
TODO: Describe the key classes, components, functions, services, modules, or configuration keys.

## Architecture Overview
TODO: Explain component relationships with prose or Mermaid.

## Detailed Analysis
TODO: Analyze the main flows, data structures, APIs, state changes, and boundaries.

## Dependency Analysis
TODO: Explain internal dependencies, external libraries, services, configuration, and cross-module contracts.

## Performance Considerations
TODO: Record visible performance paths, caching, async work, batching, or bottlenecks.

## Troubleshooting
TODO: Provide code-grounded troubleshooting entrypoints.

## Conclusion
TODO: Summarize the key facts maintainers should remember.

## Appendix
TODO: Add commands, fields, API lists, or sources.
"""


def write_file(path: Path, text: str, force: bool, created: List[str], skipped: List[str]) -> None:
    if path.exists() and not force:
        skipped.append(str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    created.append(str(path))


def output_root_for_project(project: Dict[str, object], base_root: Optional[Path]) -> Path:
    project_path = Path(str(project["path"]))
    return base_root / project.get("relative_path", ".") if base_root else project_path


def write_sidecar_configs(project_root: Path, force: bool, created: List[str], skipped: List[str]) -> None:
    for name, data in default_project_sidecar_files().items():
        write_json_file(project_root / ".wiki" / name, data, force, created, skipped)


def create_for_project(
    project: Dict[str, object],
    base_root: Optional[Path],
    profile: str,
    language: str,
    force: bool,
    write_config: bool,
) -> Tuple[List[str], List[str], List[str]]:
    output_project_root = output_root_for_project(project, base_root)
    created: List[str] = []
    skipped: List[str] = []
    pages_to_fill: List[str] = []

    if write_config:
        config = dict(DEFAULT_CONFIG)
        config["profile"] = profile
        config["language"] = language
        config["content_root"] = f"{language}/content"
        write_json_file(output_project_root / ".wiki" / "config.json", config, force, created, skipped)
        write_sidecar_configs(output_project_root, force, created, skipped)

    config = load_config(output_project_root)
    language = str(config["language"])
    content = content_root_path(output_project_root, config)

    for doc in root_docs(language):
        title = doc["title"]
        path = content / doc["filename"]
        write_file(path, placeholder(title, project, language), force, created, skipped)
        pages_to_fill.append(str(path))

    for topic in topic_records(project, output_project_root, profile, language):
        title = str(topic["title"])
        topic_dir = content / title
        index = topic_dir / filename_for_title(title)
        write_file(index, placeholder(title, project, language), force, created, skipped)
        pages_to_fill.append(str(index))

        for child in topic.get("children", []):
            child_title = str(child)
            child_path = topic_dir / filename_for_title(child_title)
            if child_path == index:
                continue
            write_file(child_path, placeholder(child_title, project, language), force, created, skipped)
            pages_to_fill.append(str(child_path))

    return created, skipped, pages_to_fill


def build_index(project_root: Path) -> Dict[str, object]:
    script = Path(__file__).resolve().parent / "build_wiki_index.py"
    proc = subprocess.run(
        [sys.executable, str(script), str(project_root)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(proc.stdout.decode("utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create .wiki content skeletons from scan_project.py JSON.")
    parser.add_argument("scan_json", help="JSON file generated by scan_project.py.")
    parser.add_argument("--output-dir", help="Optional alternate root for generated skeletons.")
    parser.add_argument("--profile", choices=["light", "balanced", "deep"], default="deep")
    parser.add_argument("--language", default="zh", help="Wiki language key, such as zh or en. Default: zh.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--write-config", action="store_true", help="Write .wiki/config.json and project sidecar config files.")
    parser.add_argument("--build-index", action="store_true", help="Build .wiki/wiki-index.json after creating skeletons.")
    args = parser.parse_args()

    data = json.loads(Path(args.scan_json).read_text(encoding="utf-8"))
    base_root = Path(args.output_dir).resolve() if args.output_dir else None

    all_created: List[str] = []
    all_skipped: List[str] = []
    all_pages_to_fill: List[str] = []
    indexes: List[Dict[str, object]] = []
    for project in data.get("projects", []):
        created, skipped, pages_to_fill = create_for_project(
            project,
            base_root,
            args.profile,
            args.language,
            args.force,
            args.write_config,
        )
        all_created.extend(created)
        all_skipped.extend(skipped)
        all_pages_to_fill.extend(pages_to_fill)
        if args.build_index:
            indexes.append(build_index(output_root_for_project(project, base_root)))

    print(json.dumps({
        "created_count": len(all_created),
        "skipped_count": len(all_skipped),
        "index_count": len(indexes),
        "pages_to_fill_count": len(all_pages_to_fill),
        "created": all_created,
        "skipped": all_skipped,
        "pages_to_fill": all_pages_to_fill,
        "indexes": indexes,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
