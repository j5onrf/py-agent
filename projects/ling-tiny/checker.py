#!/usr/bin/env python3
"""CLI markdown checklist parser that counts checked [x] vs unchecked [ ] boxes."""

import argparse
import re


def parse_checklist(filepath: str) -> tuple[int, int]:
    """Parse a markdown checklist file and return (checked_count, unchecked_count)."""
    checked = 0
    unchecked = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            # Skip empty lines and comment lines
            if not stripped or stripped.startswith("#"):
                continue
            # Match list items with [x] or [ ] (handles optional leading - or bullet)
            match = re.fullmatch(r"^\s*[-*]?\s*\[([ xX])\]\s*(.*)", stripped)
            if match:
                if match.group(1) in ("x", "X"):
                    checked += 1
                elif match.group(1) in (" ", " "):
                    unchecked += 1

    return checked, unchecked


def main():
    parser = argparse.ArgumentParser(
        description="Count checked [x] vs unchecked [ ] boxes in a markdown checklist."
    )
    parser.add_argument("filepath", help="Path to the markdown checklist file")
    args = parser.parse_args()

    checked, unchecked = parse_checklist(args.filepath)

    print(f"Checked [x]: {checked}")
    print(f"Unchecked [ ]: {unchecked}")
    print(f"Total: {checked + unchecked}")


if __name__ == "__main__":
    main()