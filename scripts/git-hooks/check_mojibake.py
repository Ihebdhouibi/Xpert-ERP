#!/usr/bin/env python3
"""Pre-commit guard against mojibake and Unicode replacement characters.

pre-commit passes the staged text files as argv. We read each as UTF-8 and
fail when we find:

  * U+FFFD, the replacement char (a sure sign of a botched decode), or
  * a high-confidence "UTF-8 decoded as Latin-1/CP1252" sequence -- the classic
    way French accents get corrupted (e.g. an accented letter turning into two
    garbage chars).

The pattern is assembled from explicit code points (chr(0x..)) so this source
file stays pure ASCII and never trips its own check.

Pattern legend:
  U+FFFD                          replacement char
  (U+00C3 | U+00C2) + U+00A0..BF  UTF-8 latin/punct read as CP1252
  U+00E2 U+20AC                   UTF-8 smart quotes / dashes read as CP1252
"""
from __future__ import annotations

import re
import sys

_REPLACEMENT = chr(0xFFFD)
_LATIN_LEAD = "[" + chr(0xC3) + chr(0xC2) + "][" + chr(0xA0) + "-" + chr(0xBF) + "]"
_SMART_PUNCT = chr(0xE2) + chr(0x20AC)
MOJIBAKE = re.compile("|".join((_REPLACEMENT, _LATIN_LEAD, _SMART_PUNCT)))


def check(path):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:  # pragma: no cover - defensive
        return [f"{path}: cannot read ({exc})"]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}: not valid UTF-8 ({exc})"]

    problems = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if MOJIBAKE.search(line):
            snippet = line.strip()
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            problems.append(f"{path}:{lineno}: mojibake/replacement char -> {snippet}")
    return problems


def main(argv):
    problems = []
    for path in argv[1:]:
        problems.extend(check(path))

    if problems:
        sys.stderr.write("Mojibake / encoding corruption detected:\n")
        for p in problems:
            sys.stderr.write(f"  {p}\n")
        sys.stderr.write(
            "\nFix the encoding (re-save as clean UTF-8 without BOM) before committing.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
