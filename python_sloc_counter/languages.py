"""Language detection (extension / filename / path / content) and
line classification (effective / comment / blank)."""
from __future__ import annotations

import os

# extension -> (category, language, line_comment_prefixes, block_comment_pairs)
EXT_TABLE = {
    ".py": ("code", "python", ("#",), ()),
    ".js": ("code", "javascript", ("//",), (("/*", "*/"),)),
    ".jsx": ("code", "javascript", ("//",), (("/*", "*/"),)),
    ".mjs": ("code", "javascript", ("//",), (("/*", "*/"),)),
    ".cjs": ("code", "javascript", ("//",), (("/*", "*/"),)),
    ".ts": ("code", "typescript", ("//",), (("/*", "*/"),)),
    ".tsx": ("code", "typescript", ("//",), (("/*", "*/"),)),
    ".sql": ("code", "sql", ("--",), (("/*", "*/"),)),
    ".tf": ("iac", "terraform", ("#", "//"), (("/*", "*/"),)),
    ".tfvars": ("iac", "terraform-vars", ("#", "//"), (("/*", "*/"),)),
    ".bicep": ("iac", "bicep", ("//",), (("/*", "*/"),)),
    ".yaml": ("config", "yaml", ("#",), ()),
    ".yml": ("config", "yaml", ("#",), ()),
    ".json": ("config", "json", (), ()),
    ".toml": ("config", "toml", ("#",), ()),
    ".xml": ("config", "xml", (), (("<!--", "-->"),)),
    ".ini": ("config", "ini", (";", "#"), ()),
    ".cfg": ("config", "ini", (";", "#"), ()),
    ".conf": ("config", "conf", ("#",), ()),
    ".properties": ("config", "properties", ("#", "!"), ()),
    ".env": ("config", "env", ("#",), ()),
    ".md": ("docs", "markdown", (), (("<!--", "-->"),)),
    ".html": ("config", "html", (), (("<!--", "-->"),)),
    ".htm": ("config", "html", (), (("<!--", "-->"),)),
}

FILENAMES = {
    "dockerfile": ("iac", "dockerfile", ("#",), ()),
}


def detect(relpath: str):
    """Return (category, language, source, prefixes, blocks) or None."""
    base = os.path.basename(relpath).lower()
    if base in FILENAMES or base.endswith(".dockerfile"):
        cat, lang, pre, blk = FILENAMES["dockerfile"]
        return cat, lang, "filename", pre, blk
    if "/.github/workflows/" in "/" + relpath.replace(os.sep, "/"):
        return "iac", "github-actions", "path", ("#",), ()
    _, ext = os.path.splitext(base)
    row = EXT_TABLE.get(ext)
    if row is None:
        return None
    cat, lang, pre, blk = row
    return cat, lang, "extension", pre, blk


def classify_lines(lines, prefixes, blocks, comment_ranges=()):
    """Classify each line as effective / comment / blank.

    comment_ranges: set of 0-based line indexes forced to comment
    (e.g. Python docstrings). Block comments are tracked with a simple
    state machine; string literals are not parsed (documented limit for
    line counting, same as classic counters).
    """
    forced = set(comment_ranges)
    kinds: list[str] = []
    in_block: tuple[str, str] | None = None
    for i, raw in enumerate(lines):
        line = raw.strip()
        if i in forced:
            kinds.append("comment" if line else "blank")
            continue
        if not line and in_block is None:
            kinds.append("blank")
            continue
        if in_block is not None:
            kinds.append("comment")
            if in_block[1] in raw:
                in_block = None
            continue
        started_block = None
        for start, end in blocks:
            if line.startswith(start):
                started_block = (start, end)
                break
        if started_block is not None:
            kinds.append("comment")
            if started_block[1] not in line[len(started_block[0]):]:
                in_block = started_block
            continue
        if any(line.startswith(p) for p in prefixes):
            kinds.append("comment")
            continue
        kinds.append("effective" if line else "blank")
    return kinds


def counts_from_kinds(kinds):
    from .model import Counts
    c = Counts()
    for k in kinds:
        c.add_line(k)
    return c
