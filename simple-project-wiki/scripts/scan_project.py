#!/usr/bin/env python3
"""Scan a repository and emit a project/subproject inventory as JSON."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional


MANIFESTS = {
    "pom.xml": "java-maven",
    "build.gradle": "java-gradle",
    "build.gradle.kts": "java-gradle",
    "settings.gradle": "java-gradle-root",
    "package.json": "node",
    "pnpm-workspace.yaml": "node-workspace",
    "yarn.lock": "node",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "composer.json": "php",
    "Gemfile": "ruby",
    "pages.json": "uni-app",
    "manifest.json": "app-manifest",
}

ENTRY_CANDIDATES = [
    "src/main.js",
    "src/main.ts",
    "src/main/java",
    "src/App.vue",
    "App.vue",
    "main.js",
    "main.ts",
    "index.js",
    "index.ts",
    "server.js",
    "app.js",
    "background.js",
    "src/background.js",
    "src/main/resources/application.yml",
    "src/main/resources/application.yaml",
    "src/main/resources/application.properties",
    "manage.py",
    "main.py",
    "app.py",
    "src/main.py",
    "cmd/main.go",
    "main.go",
    "src/main.rs",
    "bin/console",
]

CONFIG_CANDIDATES = [
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "package.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "vue.config.js",
    "vite.config.js",
    "vite.config.ts",
    "webpack.config.js",
    "tsconfig.json",
    "babel.config.js",
    "pages.json",
    "manifest.json",
    "application.yml",
    "application.yaml",
    "application.properties",
]

SKIP_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".spwiki",
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

SOURCE_DIR_NAMES = {
    "src",
    "app",
    "api",
    "components",
    "pages",
    "views",
    "store",
    "modules",
    "server",
    "client",
    "cmd",
    "internal",
    "pkg",
}

BINARY_DIR_NAMES = {
    "lib",
    "libs",
    "vendor",
}

WORKSPACE_CONTAINER_NAMES = {
    "apps",
    "packages",
    "services",
    "modules",
    "libs",
    "libraries",
    "crates",
    "examples",
}

NESTED_PROJECT_SKIP_PARTS = {
    "src",
    "dist",
    "dist_electron",
    "build",
    "target",
    "node_modules",
    "vendor",
}


def rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _gitignore_pattern_to_regex(pattern: str) -> str:
    """Translate one gitignore glob body into a regex matched against a posix relative path."""
    i = 0
    n = len(pattern)
    out = ""
    while i < n:
        ch = pattern[i]
        if ch == "*":
            if pattern[i : i + 2] == "**":
                # '**/' matches zero or more leading dirs; bare '**' matches anything.
                if pattern[i : i + 3] == "**/":
                    out += "(?:.*/)?"
                    i += 3
                    continue
                out += ".*"
                i += 2
                continue
            out += "[^/]*"
        elif ch == "?":
            out += "[^/]"
        else:
            out += re.escape(ch)
        i += 1
    return out


class GitignoreMatcher:
    """Pragmatic .gitignore evaluator.

    Loads .gitignore files lazily per directory (git semantics: a file applies
    to its own directory and descendants). Supports comments, blank lines,
    negation (!), directory-only (trailing /), anchoring (leading /), and the
    *, ?, ** globs. Last matching rule wins. Not a full git implementation, but
    covers the common cases used to keep generated artifacts out of scans.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._rules_by_dir: Dict[Path, List[tuple]] = {}

    def _load_dir(self, directory: Path) -> List[tuple]:
        directory = directory.resolve()
        if directory in self._rules_by_dir:
            return self._rules_by_dir[directory]
        rules: List[tuple] = []
        gitignore = directory / ".gitignore"
        if gitignore.is_file():
            try:
                lines = gitignore.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
            except Exception:
                lines = []
            for raw in lines:
                line = raw.rstrip("\r\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                line = line.rstrip()
                negated = line.startswith("!")
                if negated:
                    line = line[1:]
                if line.startswith("\\#") or line.startswith("\\!"):
                    line = line[1:]
                dir_only = line.endswith("/")
                if dir_only:
                    line = line[:-1]
                anchored = "/" in line and not line.startswith("/") or line.startswith("/")
                body = line[1:] if line.startswith("/") else line
                if not body:
                    continue
                regex_body = _gitignore_pattern_to_regex(body)
                if anchored:
                    regex = re.compile(r"^" + regex_body + r"(?:/.*)?$")
                else:
                    regex = re.compile(r"(?:^|.*/)" + regex_body + r"(?:/.*)?$")
                rules.append((regex, negated, dir_only))
        self._rules_by_dir[directory] = rules
        return rules

    def is_ignored(self, path: Path, is_dir: bool) -> bool:
        path = path.resolve()
        try:
            path.relative_to(self.root)
        except ValueError:
            return False
        ignored = False
        # Walk from root down to the path's parent; each directory's .gitignore
        # is evaluated against the path expressed relative to that directory.
        chain: List[Path] = []
        cursor = path.parent
        while True:
            chain.append(cursor)
            if cursor == self.root:
                break
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
        for base in reversed(chain):
            rules = self._load_dir(base)
            if not rules:
                continue
            try:
                rel_to_base = path.relative_to(base).as_posix()
            except ValueError:
                continue
            for regex, negated, dir_only in rules:
                if dir_only and not is_dir:
                    continue
                if regex.match(rel_to_base):
                    ignored = not negated
        return ignored


def should_skip_dir(path: Path, include_hidden: bool) -> bool:
    name = path.name
    if name in SKIP_DIRS:
        return True
    if not include_hidden and name.startswith("."):
        return True
    return False


def iter_dirs(root: Path, max_depth: int, include_hidden: bool, gitignore: Optional["GitignoreMatcher"]) -> Iterable[Path]:
    root = root.resolve()
    for current, dirnames, _ in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        dirnames[:] = [
            name
            for name in dirnames
            if not should_skip_dir(current_path / name, include_hidden)
            and not (gitignore and gitignore.is_ignored(current_path / name, is_dir=True))
        ]
        if depth > max_depth:
            dirnames[:] = []
            continue
        yield current_path


def find_files(project_path: Path, names: Iterable[str]) -> List[str]:
    found: List[str] = []
    for name in names:
        candidate = project_path / name
        if candidate.exists():
            found.append(candidate.relative_to(project_path).as_posix())
    return found


def detect_manifests(project_path: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for name, kind in MANIFESTS.items():
        if (project_path / name).exists():
            result[name] = kind
    return result


def detect_stack(project_path: Path, manifests: Dict[str, str]) -> List[str]:
    stack = set(manifests.values())

    package_json = project_path / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8-sig"))
            deps = {}
            for key in ("dependencies", "devDependencies"):
                value = data.get(key)
                if isinstance(value, dict):
                    deps.update(value)
            dep_names = " ".join(deps.keys()).lower()
            if "vue" in deps:
                stack.add("vue")
            if "react" in deps:
                stack.add("react")
            if "electron" in deps or "electron-builder" in deps or "vue-cli-plugin-electron-builder" in deps:
                stack.add("electron")
            if "uni-app" in dep_names or "@dcloudio" in dep_names:
                stack.add("uni-app")
            if "vite" in deps:
                stack.add("vite")
            if "webpack" in deps:
                stack.add("webpack")
        except Exception:
            stack.add("package-json-unreadable")

    pom_xml = project_path / "pom.xml"
    if pom_xml.exists():
        try:
            text = pom_xml.read_text(encoding="utf-8", errors="ignore").lower()
            if "spring-boot" in text:
                stack.add("spring-boot")
            if "mybatis" in text:
                stack.add("mybatis")
            if "shiro" in text:
                stack.add("shiro")
        except Exception:
            stack.add("pom-unreadable")

    gradle_files = [project_path / "build.gradle", project_path / "build.gradle.kts"]
    for gradle_file in gradle_files:
        if gradle_file.exists():
            try:
                text = gradle_file.read_text(encoding="utf-8", errors="ignore").lower()
                if "spring-boot" in text:
                    stack.add("spring-boot")
                if "kotlin" in text:
                    stack.add("kotlin")
            except Exception:
                stack.add("gradle-unreadable")

    pyproject = project_path / "pyproject.toml"
    requirements = project_path / "requirements.txt"
    python_text = ""
    for python_file in (pyproject, requirements):
        if python_file.exists():
            try:
                python_text += "\n" + python_file.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                stack.add("python-manifest-unreadable")
    if python_text:
        if "django" in python_text:
            stack.add("django")
        if "fastapi" in python_text:
            stack.add("fastapi")
        if "flask" in python_text:
            stack.add("flask")
        if "sqlalchemy" in python_text:
            stack.add("sqlalchemy")

    go_mod = project_path / "go.mod"
    if go_mod.exists():
        try:
            text = go_mod.read_text(encoding="utf-8", errors="ignore").lower()
            if "gin-gonic/gin" in text:
                stack.add("gin")
            if "labstack/echo" in text:
                stack.add("echo")
            if "gorm.io/gorm" in text:
                stack.add("gorm")
        except Exception:
            stack.add("go-mod-unreadable")

    cargo_toml = project_path / "Cargo.toml"
    if cargo_toml.exists():
        try:
            text = cargo_toml.read_text(encoding="utf-8", errors="ignore").lower()
            if "actix-web" in text:
                stack.add("actix-web")
            if "axum" in text:
                stack.add("axum")
            if "tokio" in text:
                stack.add("tokio")
        except Exception:
            stack.add("cargo-unreadable")

    composer = project_path / "composer.json"
    if composer.exists():
        try:
            text = composer.read_text(encoding="utf-8", errors="ignore").lower()
            if "laravel" in text:
                stack.add("laravel")
            if "symfony" in text:
                stack.add("symfony")
        except Exception:
            stack.add("composer-unreadable")

    gemfile = project_path / "Gemfile"
    if gemfile.exists():
        try:
            text = gemfile.read_text(encoding="utf-8", errors="ignore").lower()
            if "rails" in text:
                stack.add("rails")
            if "sinatra" in text:
                stack.add("sinatra")
        except Exception:
            stack.add("gemfile-unreadable")

    if (project_path / "pages.json").exists() or (project_path / "manifest.json").exists():
        if (project_path / "App.vue").exists() or (project_path / "main.js").exists():
            stack.add("uni-app")

    return sorted(stack)


def iter_source_files(
    project_path: Path,
    patterns: Iterable[str],
    max_files: int = 200,
    gitignore: Optional["GitignoreMatcher"] = None,
) -> Iterable[Path]:
    yielded = 0
    roots = [
        child
        for child in project_path.iterdir()
        if child.is_dir() and child.name in SOURCE_DIR_NAMES
    ]
    src_main = project_path / "src" / "main"
    if src_main.exists():
        roots.append(src_main)
    if not roots:
        return
    for root in roots:
        for pattern in patterns:
            for path in root.rglob(pattern):
                if yielded >= max_files:
                    return
                if any(part in SKIP_DIRS for part in path.parts):
                    continue
                if gitignore and gitignore.is_ignored(path, is_dir=False):
                    continue
                if path.is_file():
                    yielded += 1
                    yield path
                    continue
            if yielded >= max_files:
                return


def detect_dynamic_entrypoints(project_path: Path, gitignore: Optional["GitignoreMatcher"] = None) -> List[str]:
    entries: List[str] = []
    probes = [
        ("*.java", re.compile(r"@SpringBootApplication|public\s+static\s+void\s+main\s*\(")),
        ("*.py", re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]|FastAPI\s*\(|Flask\s*\(")),
        ("*.go", re.compile(r"\bfunc\s+main\s*\(")),
        ("*.rs", re.compile(r"\bfn\s+main\s*\(")),
        ("*.php", re.compile(r"Laravel|Symfony|require\s+__DIR__")),
        ("*.rb", re.compile(r"Rails\.application|Sinatra::Base|run\s+")),
    ]
    for pattern, regex in probes:
        for path in iter_source_files(project_path, [pattern], gitignore=gitignore):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if regex.search(text):
                entries.append(path.relative_to(project_path).as_posix())
                break

    package_json = project_path / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8-sig"))
            scripts = data.get("scripts", {})
            if isinstance(scripts, dict):
                for name in ("dev", "serve", "start", "build"):
                    if name in scripts:
                        entries.append(f"package.json#scripts.{name}")
        except Exception:
            pass
    return sorted(set(entries))


def find_source_dirs(project_path: Path) -> List[str]:
    found: List[str] = []
    for child in project_path.iterdir():
        if child.is_dir() and child.name in SOURCE_DIR_NAMES:
            found.append(child.name)
    java_src = project_path / "src" / "main" / "java"
    resources = project_path / "src" / "main" / "resources"
    if java_src.exists():
        found.append("src/main/java")
    if resources.exists():
        found.append("src/main/resources")
    return sorted(set(found))


def find_binary_dirs(project_path: Path) -> List[str]:
    found: List[str] = []
    for child in project_path.iterdir():
        if child.is_dir() and child.name in BINARY_DIR_NAMES:
            found.append(child.name)
    return sorted(set(found))


def existing_wikis(project_path: Path) -> Dict[str, bool]:
    return {
        ".spwiki": (project_path / ".spwiki").exists(),
    }


def project_info(path: Path, root: Path, gitignore: Optional["GitignoreMatcher"] = None) -> Dict[str, object]:
    manifests = detect_manifests(path)
    entrypoints = sorted(set(find_files(path, ENTRY_CANDIDATES) + detect_dynamic_entrypoints(path, gitignore)))
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "relative_path": "." if path.resolve() == root.resolve() else rel(path, root),
        "manifests": manifests,
        "stack": detect_stack(path, manifests),
        "entrypoints": entrypoints,
        "config_files": find_files(path, CONFIG_CANDIDATES),
        "source_dirs": find_source_dirs(path),
        "binary_dirs": find_binary_dirs(path),
        "existing_wikis": existing_wikis(path),
    }


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def is_workspace_child(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return len(parts) >= 2 and parts[-2] in WORKSPACE_CONTAINER_NAMES


def has_nested_skip_part(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return any(part in NESTED_PROJECT_SKIP_PARTS for part in parts[:-1])


def filter_project_paths(project_paths: Iterable[Path], root: Path, include_nested_projects: bool) -> List[Path]:
    paths = sorted({path.resolve() for path in project_paths})
    if include_nested_projects:
        return paths

    accepted: List[Path] = []
    for path in paths:
        if path == root:
            accepted.append(path)
            continue
        if has_nested_skip_part(path, root):
            continue

        parent_project = next(
            (
                existing
                for existing in accepted
                if existing != root and is_relative_to(path, existing)
            ),
            None,
        )
        if parent_project is None or is_workspace_child(path, root):
            accepted.append(path)

    return accepted


def scan(root: Path, max_depth: int, include_hidden: bool, include_nested_projects: bool, respect_gitignore: bool = True) -> Dict[str, object]:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Project root does not exist or is not a directory: {root}")

    gitignore = GitignoreMatcher(root) if respect_gitignore else None

    project_paths = {root}
    for directory in iter_dirs(root, max_depth=max_depth, include_hidden=include_hidden, gitignore=gitignore):
        if directory == root:
            continue
        manifests = detect_manifests(directory)
        if manifests:
            project_paths.add(directory)

    filtered_paths = filter_project_paths(project_paths, root, include_nested_projects)
    projects = [project_info(path, root, gitignore) for path in filtered_paths]
    return {
        "schema_version": 1,
        "root": str(root),
        "generated_by": "simple-project-wiki/scripts/scan_project.py",
        "respect_gitignore": respect_gitignore,
        "projects": projects,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a project or monorepo for wiki generation.")
    parser.add_argument("project_root", help="Project or repository root to scan.")
    parser.add_argument("--output", "-o", help="Write JSON to this file instead of stdout.")
    parser.add_argument("--max-depth", type=int, default=3, help="Maximum directory depth for subproject detection.")
    parser.add_argument("--include-hidden", action="store_true", help="Scan hidden directories except known skip folders.")
    parser.add_argument("--include-nested-projects", action="store_true", help="Include manifest-bearing projects nested inside already detected projects.")
    parser.add_argument("--no-gitignore", action="store_true", help="Do not honor .gitignore rules while scanning. By default, .gitignore rules in the root and subprojects are respected.")
    args = parser.parse_args()

    data = scan(
        Path(args.project_root),
        args.max_depth,
        args.include_hidden,
        args.include_nested_projects,
        respect_gitignore=not args.no_gitignore,
    )
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
