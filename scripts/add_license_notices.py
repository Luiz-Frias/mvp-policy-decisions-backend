#!/usr/bin/env python3
"""Utility to apply license notices to files based on extension."""
from __future__ import annotations

import argparse
from pathlib import Path

LICENSE_HEADERS = {
    "python": [
        "# PolicyCore - Policy Decision Management System",
        "# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>",
        "# Form F[x] Labs",
        "#",
        "# This software is dual-licensed under AGPL-3.0 and Commercial License.",
        "# For commercial licensing, contact: luizf35@gmail.com",
        "# See LICENSE file for full terms.",
        "",
    ],
    "javascript": [
        "/**",
        " * PolicyCore - Policy Decision Management System",
        " * Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>",
        " * Form F[x] Labs",
        " *",
        " * This software is dual-licensed under AGPL-3.0 and Commercial License.",
        " * For commercial licensing, contact: luizf35@gmail.com",
        " * See LICENSE file for full terms.",
        " */",
        "",
    ],
    "yaml": [
        "# PolicyCore - Policy Decision Management System",
        "# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>",
        "# Form F[x] Labs",
        "#",
        "# This software is dual-licensed under AGPL-3.0 and Commercial License.",
        "# For commercial licensing, contact: luizf35@gmail.com",
        "# See LICENSE file for full terms.",
        "",
    ],
    "sql": [
        "-- PolicyCore - Policy Decision Management System",
        "-- Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>",
        "-- Form F[x] Labs",
        "--",
        "-- This software is dual-licensed under AGPL-3.0 and Commercial License.",
        "-- For commercial licensing, contact: luizf35@gmail.com",
        "-- See LICENSE file for full terms.",
        "",
    ],
    "docker": [
        "# PolicyCore - Policy Decision Management System",
        "# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>",
        "# Form F[x] Labs",
        "#",
        "# This software is dual-licensed under AGPL-3.0 and Commercial License.",
        "# For commercial licensing, contact: luizf35@gmail.com",
        "# See LICENSE file for full terms.",
        "",
    ],
    "shell": [
        "# PolicyCore - Policy Decision Management System",
        "# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>",
        "# Form F[x] Labs",
        "#",
        "# This software is dual-licensed under AGPL-3.0 and Commercial License.",
        "# For commercial licensing, contact: luizf35@gmail.com",
        "# See LICENSE file for full terms.",
        "",
    ],
    "markdown": [
        "<!--",
        "PolicyCore - Policy Decision Management System",
        "Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>",
        "Form F[x] Labs",
        "",
        "This software is dual-licensed under AGPL-3.0 and Commercial License.",
        "For commercial licensing, contact: luizf35@gmail.com",
        "See LICENSE file for full terms.",
        "-->",
        "",
    ],
}

EXTENSION_MAP = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".ts": "javascript",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sql": "sql",
    ".sh": "shell",
    ".md": "markdown",
}


def detect_file_type(path: Path) -> str | None:
    if path.name == "Dockerfile":
        return "docker"
    return EXTENSION_MAP.get(path.suffix.lower())


def has_header(lines: list[str], header: list[str], shebang: bool) -> bool:
    start = 1 if shebang else 0
    sample = lines[start : start + len(header)]
    return sample == header


def apply_header(path: Path, file_type: str) -> None:
    header = LICENSE_HEADERS[file_type]
    text = path.read_text().splitlines()
    shebang = False
    if text and text[0].startswith("#!"):
        shebang = True
    if has_header(text, header, shebang):
        return
    new_lines = []
    if shebang:
        new_lines.append(text[0])
        new_lines.extend(header)
        new_lines.extend(text[1:])
    else:
        new_lines.extend(header)
        new_lines.extend(text)
    path.write_text("\n".join(new_lines) + "\n")


def process_path(path: Path) -> None:
    if path.is_dir():
        for child in path.rglob("*"):
            if child.is_file():
                file_type = detect_file_type(child)
                if file_type:
                    apply_header(child, file_type)
    elif path.is_file():
        file_type = detect_file_type(path)
        if file_type:
            apply_header(path, file_type)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply license notices to files")
    parser.add_argument("paths", nargs="+", type=Path, help="Files or directories to process")
    args = parser.parse_args()
    for p in args.paths:
        process_path(p)


if __name__ == "__main__":
    main()
