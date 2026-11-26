"""SQL extraction (LANGUAGES-AND-OPEN-ITEMS 1.9).

Dialects are not distinguished in v1. CREATE statements are found by
regex and their extent is tracked with BEGIN..END nesting so stored
procedures whose bodies contain semicolons stay in one piece.
- CREATE PROCEDURE / FUNCTION -> functions (procedural code)
- CREATE TABLE / VIEW / INDEX / TRIGGER / SEQUENCE / TYPE -> units
Everything else (DML, bare SELECT, migrations glue) is line-counted only.
"""
from __future__ import annotations

import re

from .languages import classify_lines, counts_from_kinds
from .model import Counts, FunctionUnit, Unit, body_hash

_CREATE = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?"
    r"(TABLE|VIEW|INDEX|TRIGGER|PROCEDURE|FUNCTION|SEQUENCE|TYPE)\b"
    r"(?:\s+IF\s+NOT\s+EXISTS)?\s+([^\s(;]+)",
    re.IGNORECASE)
_BEGIN = re.compile(r"\bBEGIN\b", re.IGNORECASE)
_END = re.compile(r"\bEND\b", re.IGNORECASE)
_QUOTES = str.maketrans("", "", "\"`[]")


def _statement_end(lines, start):
    """Line index where the statement starting at `start` terminates:
    the first ';' at BEGIN..END depth 0 after the start line."""
    depth = 0
    for i in range(start, len(lines)):
        code = lines[i]
        # strip -- comments and single-quoted strings (approximation)
        code = re.sub(r"--.*$", "", code)
        code = re.sub(r"'[^']*'", "''", code)
        depth += len(_BEGIN.findall(code))
        depth -= len(_END.findall(code))
        if ";" in code and depth <= 0:
            return i
    return len(lines) - 1


def extract(lines: list[str]):
    kinds = classify_lines(lines, ("--",), (("/*", "*/"),))
    total = counts_from_kinds(kinds)
    warnings: list[str] = []

    spans = []  # (start, end, kind, name, is_function, signature)
    i = 0
    while i < len(lines):
        m = _CREATE.match(lines[i])
        if m:
            obj_kind = m.group(1).lower()
            name = m.group(2).translate(_QUOTES)
            end = _statement_end(lines, i)
            is_func = obj_kind in ("procedure", "function")
            signature = ""
            if is_func:
                joined = " ".join(lines[i:end + 1])
                pm = re.search(r"\((.*?)\)", joined, re.DOTALL)
                signature = pm.group(1).strip() if pm else ""
            spans.append((i, end, obj_kind, name, is_func, signature))
            i = end + 1
            continue
        i += 1

    owner: list[int | None] = [None] * len(lines)
    for idx, (s, e, *_r) in enumerate(spans):
        for ln in range(s, e + 1):
            owner[ln] = idx

    functions: list[FunctionUnit] = []
    units: list[Unit] = []
    assigned = Counts()
    for idx, (s, e, obj_kind, name, is_func, signature) in enumerate(spans):
        c = Counts()
        own: list[str] = []
        for ln in range(len(lines)):
            if owner[ln] == idx:
                c.add_line(kinds[ln])
                if kinds[ln] == "effective":
                    own.append(lines[ln].rstrip())
        assigned = assigned + c
        if is_func:
            functions.append(FunctionUnit(
                key=name, name=name, kind=obj_kind, container="",
                signature=signature, start_line=s + 1, end_line=e + 1,
                counts=c, body_hash=body_hash(lines[s:e + 1]), own_lines=own))
        else:
            units.append(Unit(
                key=f"{obj_kind}.{name}", name=name, kind=obj_kind,
                start_line=s + 1, end_line=e + 1, counts=c,
                body_hash=body_hash(lines[s:e + 1]),
                attributes={}, own_lines=own))
    remainder = total - assigned
    return functions, units, total, remainder, warnings, kinds
