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
    """
    Determine the file type key for a given file path based on its name or extension.
    
    Returns:
        The file type string used for license headers, or None if the file type is not recognized.
    """
    if path.name == "Dockerfile":
        return "docker"
    return EXTENSION_MAP.get(path.suffix.lower())


def has_header(lines: list[str], header: list[str], shebang: bool) -> bool:
    """
    Check if the specified license header is present at the start of the file content.
    
    Parameters:
        lines (list[str]): The lines of the file to check.
        header (list[str]): The license header lines to look for.
        shebang (bool): Whether the file starts with a shebang line, which should be skipped.
    
    Returns:
        bool: True if the header is present at the expected position, False otherwise.
    """
    start = 1 if shebang else 0
    sample = lines[start : start + len(header)]
    return sample == header


def apply_header(path: Path, file_type: str) -> None:
    """
    Inserts the appropriate license header into a file if it is not already present.
    
    If the file begins with a shebang line, the license header is inserted immediately after it; otherwise, the header is added at the top of the file. The function avoids adding duplicate headers.
    """
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
    """
    Recursively applies the appropriate license header to all supported files within the given path.
    
    If the path is a directory, processes all files within it and its subdirectories. If the path is a file, processes it directly. Only files with recognized types will have license headers applied or updated.
    """
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
    """
    Parses command-line arguments and applies license headers to the specified files or directories.
    
    Processes each provided path, recursively handling directories and applying the appropriate license header to supported file types.
    """
    parser = argparse.ArgumentParser(description="Apply license notices to files")
    parser.add_argument("paths", nargs="+", type=Path, help="Files or directories to process")
    args = parser.parse_args()
    for p in args.paths:
        process_path(p)


if __name__ == "__main__":
    main()
