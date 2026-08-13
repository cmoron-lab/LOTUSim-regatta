#!/usr/bin/env python3
"""Merge the scenario conditions into the vessel model as ONE yaml for xdyn.

xdyn concatenates its input files as raw text and parses the result as a single
document, so a section present in both files becomes a duplicated top-level key
and the winner is whatever the yaml library of the day picks: the bundled CMake
xdyn keeps the LAST occurrence, lxdyn 26.8.1 (yaml-cpp 0.9) keeps the FIRST.
Measured 2026-08-13: same boat, same states, the stacked pair sails a wind 90
degrees off under 26.8.1. Replacing the section ourselves removes the ambiguity
for both binaries.

Usage: merge_conditions.py MODEL CONDITIONS OUT
"""

import re
import sys


def top_block(text, key, path):
    """The top-level `key:` block: from the key line to the next top-level key."""
    m = re.search(rf"(?ms)^{re.escape(key)}:\n.*?(?=^\S|\Z)", text)
    if not m:
        sys.exit(f"merge_conditions: no top-level '{key}:' in {path}")
    return m.group(0)


def main():
    model, conditions, out = sys.argv[1:4]
    src = open(model).read()
    cond = open(conditions).read()
    key = "environment models"
    merged = src.replace(top_block(src, key, model), top_block(cond, key, conditions))
    open(out, "w").write(merged)


if __name__ == "__main__":
    main()
