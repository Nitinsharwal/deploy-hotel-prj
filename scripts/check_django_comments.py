#!/usr/bin/env python3
"""Block multi-line ``{# ... #}`` Django comments in templates.

WHY this exists
---------------
Django's ``{# short comment #}`` syntax only works on a SINGLE LINE.
If the closing ``#}`` is not on the same line as the opening ``{#``,
the comment isn't recognized — Django renders the text as plain
content past the first line. This has caused FIVE separate
production bugs in this codebase where developer comments leaked
into the rendered page.

The safe form for anything spanning multiple lines is::

    {% comment %}
      ...explanation...
    {% endcomment %}

This hook enforces that rule. If you see a failure, change ``{# #}``
to ``{% comment %}{% endcomment %}``.

WHAT it does
------------
Given file paths as argv (pre-commit passes only staged HTML files),
report every multi-line ``{# ... #}`` block and exit non-zero if any
were found.
"""

from __future__ import annotations

import pathlib
import sys


def find_bad_blocks(text: str) -> list[tuple[int, int]]:
    """Return [(open_line, close_line), ...] for every multi-line {# ... #}.

    Walks line by line:
      - ``in_open`` tracks whether we're inside an unfinished ``{#``.
      - For each line: if we're open, look for ``#}`` to close (recording
        the span). Otherwise, scan for ``{#`` and check whether its
        matching ``#}`` is on the same line. If not → open.

    Doesn't try to be a full Django template parser — that would be
    overkill. The heuristic is conservative: we only flag genuine
    multi-line spans, not weird edge cases like ``{# foo #} bar {#``
    on the same line (rare in practice).
    """
    bad: list[tuple[int, int]] = []
    in_open = False
    open_line = 0

    for i, line in enumerate(text.split("\n"), start=1):
        if in_open:
            if "#}" in line:
                bad.append((open_line, i))
                in_open = False
            continue

        # Not currently inside a multi-line comment. Look for {# starts.
        # If the matching #} is also on this line, it's the safe form
        # and we ignore it.
        idx = line.find("{#")
        while idx != -1:
            close = line.find("#}", idx + 2)
            if close == -1:
                in_open = True
                open_line = i
                break  # rest of line is inside the comment
            idx = line.find("{#", close + 2)

    return bad


def main() -> int:
    """Returns 0 if all clean, 1 if any multi-line comment found."""
    bad_found: list[str] = []

    for arg in sys.argv[1:]:
        path = pathlib.Path(arg)
        if not path.suffix == ".html":
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue

        for open_line, close_line in find_bad_blocks(text):
            bad_found.append(f"  {path}:{open_line}-{close_line}")

    if bad_found:
        print(
            "ERROR: Multi-line `{# ... #}` Django comments found.",
            "Django only recognizes single-line `{# #}`; multi-line versions",
            "render as visible text past line 1.",
            "",
            "Fix: replace with `{% comment %}...{% endcomment %}`.",
            "",
            "Offending blocks:",
            *bad_found,
            sep="\n",
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
