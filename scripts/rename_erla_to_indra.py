"""Replace remaining legacy ERLA branding with Indra.

Run from the repository root:

    python scripts/rename_erla_to_indra.py

The script intentionally skips binary files and dependency/cache directories.
"""

from __future__ import annotations

from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".next",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}

REPLACEMENTS = (
    ("ERLA", "Indra"),
    ("Erla", "Indra"),
    ("erla", "indra"),
)

TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".env",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def is_text_path(path: Path) -> bool:
    return path.name in {"Dockerfile", "Makefile"} or path.suffix in TEXT_SUFFIXES


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def rewrite_file(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False

    updated = text
    for old, new in REPLACEMENTS:
        updated = updated.replace(old, new)
    if updated == text:
        return False

    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    root = Path.cwd()
    changed: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or should_skip(path) or not is_text_path(path):
            continue
        if rewrite_file(path):
            changed.append(path)

    legacy_name = root / "ERLA_PHASE_1_CANONICAL_CONTRACTS_CODEX_PLAN.md"
    indra_name = root / "INDRA_PHASE_1_CANONICAL_CONTRACTS_CODEX_PLAN.md"
    if legacy_name.exists() and not indra_name.exists():
        legacy_name.rename(indra_name)
        changed.append(indra_name)

    if changed:
        print("Updated legacy branding in:")
        for path in changed:
            print(f"- {path.relative_to(root)}")
    else:
        print("No legacy branding references found.")


if __name__ == "__main__":
    main()
