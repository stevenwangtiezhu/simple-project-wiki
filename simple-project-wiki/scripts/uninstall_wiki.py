#!/usr/bin/env python3
"""Find and optionally delete generated .spwiki knowledge-base folders.

Default behavior lists every .spwiki directory under the given root without
deleting anything. Pass --delete to remove them. Only directories literally
named ".spwiki" are ever touched; source files are never removed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import List


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


def find_spwiki_dirs(root: Path) -> List[Path]:
    root = root.resolve()
    found: List[Path] = []
    for current, dirnames, _ in os.walk(root):
        current_path = Path(current)
        if current_path.name == ".spwiki":
            found.append(current_path)
            dirnames[:] = []
            continue
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(description="List or delete generated .spwiki folders.")
    parser.add_argument("project_root", help="Project or repository root to search.")
    parser.add_argument("--delete", action="store_true", help="Delete the .spwiki folders. Without this flag the script only lists them.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    root = Path(args.project_root)
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Project root does not exist or is not a directory: {root}")

    targets = find_spwiki_dirs(root)
    deleted: List[str] = []
    errors: List[str] = []

    if args.delete:
        for path in targets:
            try:
                shutil.rmtree(path)
                deleted.append(str(path))
            except Exception as exc:  # pragma: no cover - filesystem dependent
                errors.append(f"{path}: {exc}")

    if args.json:
        print(json.dumps({
            "project_root": str(root.resolve()),
            "found": [str(path) for path in targets],
            "found_count": len(targets),
            "deleted": deleted,
            "deleted_count": len(deleted),
            "errors": errors,
            "mode": "delete" if args.delete else "list",
        }, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    if not targets:
        print(f"No .spwiki folders found under {root.resolve()}")
        return 0

    if args.delete:
        print(f"Deleted {len(deleted)} .spwiki folder(s):")
        for path in deleted:
            print(f"- {path}")
        for err in errors:
            print(f"! {err}")
        return 1 if errors else 0

    print(f"Found {len(targets)} .spwiki folder(s) (nothing deleted; re-run with --delete to remove):")
    for path in targets:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
