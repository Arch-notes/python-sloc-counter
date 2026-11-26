"""Counting layer: build a FileResult for one file or a whole tree."""
from __future__ import annotations

import os

from . import iac_units, js_lang, python_lang, sql_lang
from .languages import classify_lines, counts_from_kinds, detect
from .model import FileResult
from .normalize import (DecodeError, decode_bytes, decode_replace,
                        is_binary, to_lines)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "target", "dist", "build", ".tox", ".mypy_cache"}


class AbortError(Exception):
    """Raised under --on-error abort at the first undecodable file."""


def count_file(abspath: str, relpath: str, explicit_encoding: str | None = None,
               on_error: str = "strict", strict_detection: bool = False) -> FileResult:
    det = detect(relpath)
    if det is None:
        return FileResult(relpath, "", "", "", counts_from_kinds([]),
                          status="error", error="unknown file type")
    category, language, source, prefixes, blocks = det
    with open(abspath, "rb") as fh:
        data = fh.read()
    result = FileResult(relpath, category, language, source, counts_from_kinds([]))
    if is_binary(data):
        result.status = "skipped_binary"
        return result
    replaced = None
    try:
        decoded = decode_bytes(data, explicit_encoding)
    except DecodeError as exc:
        if on_error == "abort":
            raise AbortError(f"{relpath}: {exc}") from exc
        if on_error == "replace":
            text, enc, bad, bad_lines = decode_replace(data)
            replaced = (text, enc, bad, bad_lines)
            decoded = None
        else:
            result.status = "error"
            result.error = str(exc)
            return result
    if replaced is not None:
        text, enc, bad, bad_lines = replaced
        result.encoding = enc
        result.encoding_source = "replace"
        result.warnings.append(
            f"decode_replaced: {bad} replacement character(s) at lines "
            f"{bad_lines}; body_hash is unreliable for this file")
        lines = to_lines(text)
        result.lines = lines
        kinds = classify_lines(lines, prefixes, blocks)
        result.line_kinds = kinds
        result.counts = counts_from_kinds(kinds)
        result.non_function_counts = result.counts
        result.non_unit_counts = result.counts
        return result
    result.encoding = decoded.encoding
    result.encoding_source = decoded.source
    if decoded.ambiguous:
        result.warnings.append(
            f"ambiguous_encoding: {decoded.encoding} score={decoded.score} "
            f"margin={decoded.margin} candidates={decoded.candidates}")
        if strict_detection:
            result.status = "error"
            result.error = ("ambiguous_encoding below threshold "
                            "(--strict-detection)")
            result.counts = counts_from_kinds([])
            return result
    lines = to_lines(decoded.text)
    result.lines = lines

    if language == "python":
        functions, total, non_function, warnings, kinds, classes = \
            python_lang.extract(lines)
        result.functions = functions
        result.classes = classes
        result.counts = total
        result.non_function_counts = non_function
        result.non_unit_counts = non_function
        result.warnings.extend(warnings)
        result.line_kinds = kinds
        return result

    if language in ("javascript", "typescript"):
        tsx = relpath.endswith((".tsx", ".jsx"))
        functions, total, non_function, warnings, kinds, classes = \
            js_lang.extract(lines, language, tsx)
        result.functions = functions
        result.classes = classes
        result.counts = total
        result.non_function_counts = non_function
        result.non_unit_counts = non_function
        result.warnings.extend(warnings)
        result.line_kinds = kinds
        return result

    if language == "sql":
        functions, units, total, remainder, warnings, kinds = sql_lang.extract(lines)
        result.functions = functions
        result.units = units
        result.counts = total
        result.non_function_counts = remainder
        result.non_unit_counts = remainder
        result.warnings.extend(warnings)
        result.line_kinds = kinds
        return result

    kinds = classify_lines(lines, prefixes, blocks)
    result.line_kinds = kinds
    result.counts = counts_from_kinds(kinds)

    if language in ("terraform", "bicep"):
        units, non_unit = iac_units.extract_brace_blocks(lines, kinds, language)
        result.units = units
        result.non_unit_counts = non_unit
        result.non_function_counts = non_unit
        return result

    if language in ("yaml", "github-actions"):
        refined = iac_units.refine_yaml(relpath, decoded.text, lines, kinds)
        if refined is not None:
            cat, lang, src, units, non_unit = refined
            result.category, result.language, result.language_source = cat, lang, src
            result.units = units
            result.non_unit_counts = non_unit
            result.non_function_counts = non_unit
            return result

    result.non_function_counts = result.counts
    result.non_unit_counts = result.counts
    return result


def count_tree(root: str, explicit_encoding: str | None = None,
               on_error: str = "strict", strict_detection: bool = False) -> list[FileResult]:
    root = os.path.abspath(root)
    results: list[FileResult] = []
    if os.path.isfile(root):
        rel = os.path.basename(root)
        if detect(rel) is not None:
            results.append(count_file(root, rel, explicit_encoding,
                                      on_error, strict_detection))
        return results
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            abspath = os.path.join(dirpath, name)
            relpath = os.path.relpath(abspath, root).replace(os.sep, "/")
            if detect(relpath) is None:
                continue
            results.append(count_file(abspath, relpath, explicit_encoding,
                                      on_error, strict_detection))
    results.sort(key=lambda r: r.path)
    return results
