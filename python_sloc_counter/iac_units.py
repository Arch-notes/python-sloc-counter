"""Declarative unit extraction for IaC formats (see IAC.md).

- Terraform / Bicep: top-level blocks found by regex + brace matching.
- YAML family (Kubernetes / CloudFormation / GitHub Actions): PyYAML node
  marks give document and key ranges without a full custom parser.
Units partition lines the same way Python functions do, so
file = sum(units) + non_unit always holds.
"""
from __future__ import annotations

import re

from .languages import counts_from_kinds
from .model import Counts, Unit, body_hash

_TF_BLOCK = re.compile(
    r'^\s*(resource|data|module|variable|output|provider|terraform|locals)\b'
    r'((?:\s+"[^"]*")*)\s*\{')
_BICEP_BLOCK = re.compile(
    r"^\s*(resource|module)\s+([A-Za-z_][A-Za-z0-9_]*)\s+'([^']+)'\s*(?:=\s*\{|=\s*\[)?")


def _brace_end(lines, start_idx):
    """Return 0-based index of the line where the block opened at start_idx
    closes, ignoring braces in strings and line comments (approximation)."""
    depth = 0
    opened = False
    for i in range(start_idx, len(lines)):
        line = lines[i]
        j = 0
        in_str = False
        while j < len(line):
            ch = line[j]
            if in_str:
                if ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "#" or (ch == "/" and j + 1 < len(line) and line[j + 1] == "/"):
                break
            elif ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
                if opened and depth == 0:
                    return i
            j += 1
    return len(lines) - 1


def _partition(lines, kinds, spans):
    """spans: list of (key, name, kind, start0, end0, attributes).
    Returns (units, non_unit_counts). Lines go to the smallest span."""
    owner: list[int | None] = [None] * len(lines)
    for idx, (_, _, _, s, e, _) in enumerate(spans):
        for ln in range(s, e + 1):
            cur = owner[ln]
            if cur is None or (spans[cur][4] - spans[cur][3]) >= (e - s):
                owner[ln] = idx
    units: list[Unit] = []
    assigned = Counts()
    for idx, (key, name, kind, s, e, attrs) in enumerate(spans):
        c = Counts()
        own: list[str] = []
        for ln in range(len(lines)):
            if owner[ln] == idx:
                c.add_line(kinds[ln])
                if kinds[ln] == "effective":
                    own.append(lines[ln].rstrip())
        assigned = assigned + c
        units.append(Unit(key=key, name=name, kind=kind, start_line=s + 1,
                          end_line=e + 1, counts=c,
                          body_hash=body_hash(lines[s:e + 1]),
                          attributes=attrs, own_lines=own))
    total = counts_from_kinds(kinds)
    return units, total - assigned


def extract_brace_blocks(lines, kinds, language):
    spans = []
    i = 0
    while i < len(lines):
        m = None
        if language == "terraform":
            m = _TF_BLOCK.match(lines[i])
            if m:
                labels = re.findall(r'"([^"]*)"', m.group(2))
                name = ".".join(labels) if labels else m.group(1)
                kind = m.group(1)
                key = f"{kind}.{name}" if labels else kind
                end = _brace_end(lines, i)
                spans.append((key, name, kind, i, end, {"labels": labels}))
                i = end + 1
                continue
        elif language == "bicep":
            m = _BICEP_BLOCK.match(lines[i])
            if m:
                kind, name, type_str = m.group(1), m.group(2), m.group(3)
                end = _brace_end(lines, i)
                spans.append((name, name, kind, i, end, {"type": type_str}))
                i = end + 1
                continue
        i += 1
    return _partition(lines, kinds, spans)


def _yaml_docs(text):
    import yaml
    try:
        return [d for d in yaml.compose_all(text)]
    except yaml.YAMLError:
        return None


def _scalar(node):
    return node.value if node is not None and hasattr(node, "value") else None


def _map_items(node):
    if node is None or not hasattr(node, "value") or not isinstance(node.value, list):
        return []
    out = []
    for k, v in node.value:
        out.append((_scalar(k), v))
    return out


def _find(node, key):
    for k, v in _map_items(node):
        if k == key:
            return v
    return None


def refine_yaml(relpath, text, lines, kinds):
    """Decide the YAML flavor and extract units when it is IaC.
    Returns (category, language, source, units, non_unit_counts) or None
    to keep the plain config/yaml treatment."""
    docs = _yaml_docs(text)
    if not docs:
        return None
    first = docs[0]

    # GitHub Actions: jobs are units. Detection is by location, per IAC.md.
    jobs = _find(first, "jobs")
    if jobs is not None and "/.github/workflows/" in "/" + relpath.replace("\\", "/"):
        spans = []
        for job_id, job_node in _map_items(jobs):
            if job_id is None:
                continue
            s = job_node.start_mark.line
            e = job_node.end_mark.line
            if e > s and lines[e - 1].strip() == "":
                e -= 1
            spans.append((f"job.{job_id}", job_id, "job", s, max(s, e - 1), {}))
        if spans:
            units, non_unit = _partition(lines, kinds, spans)
            return "iac", "github-actions", "content", units, non_unit
        return None

    # CloudFormation / SAM: Resources logical IDs are units.
    resources = _find(first, "Resources")
    if resources is not None:
        is_cfn = _find(first, "AWSTemplateFormatVersion") is not None
        if not is_cfn:
            for _, res_node in _map_items(resources):
                t = _scalar(_find(res_node, "Type")) or ""
                if t.startswith(("AWS::", "Custom::")) or _find(first, "Transform") is not None:
                    is_cfn = True
                    break
        if is_cfn:
            spans = []
            for logical_id, res_node in _map_items(resources):
                if logical_id is None:
                    continue
                s = res_node.start_mark.line
                e = res_node.end_mark.line
                spans.append((logical_id, logical_id, "resource", s, max(s, e - 1),
                              {"type": _scalar(_find(res_node, "Type")) or ""}))
            if spans:
                units, non_unit = _partition(lines, kinds, spans)
                return "iac", "cloudformation", "content", units, non_unit
            return None

    # Kubernetes: every document with apiVersion + kind is a unit.
    spans = []
    for doc in docs:
        if doc is None:
            continue
        api = _scalar(_find(doc, "apiVersion"))
        kind = _scalar(_find(doc, "kind"))
        meta = _find(doc, "metadata")
        name = _scalar(_find(meta, "name")) if meta is not None else None
        if not (api and kind and name):
            continue
        ns = _scalar(_find(meta, "namespace")) if meta is not None else None
        key = f"{api}/{kind}/{ns + '/' if ns else ''}{name}"
        s = doc.start_mark.line
        e = doc.end_mark.line
        spans.append((key, name, kind, s, max(s, e - 1),
                      {"apiVersion": api, "namespace": ns or ""}))
    if spans:
        units, non_unit = _partition(lines, kinds, spans)
        return "iac", "kubernetes", "content", units, non_unit
    return None
