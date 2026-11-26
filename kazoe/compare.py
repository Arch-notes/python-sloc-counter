"""Comparison layer: staged matching (FUNCTION-IDENTITY.md) and
line-level breakdown (JSON-SCHEMA.md section 9)."""
from __future__ import annotations

import difflib

from .model import Counts


def line_breakdown(before_lines: list[str], after_lines: list[str]):
    """Return (added, deleted, unchanged) over effective-line texts."""
    sm = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    added = deleted = unchanged = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            unchanged += i2 - i1
        elif tag == "delete":
            deleted += i2 - i1
        elif tag == "insert":
            added += j2 - j1
        elif tag == "replace":
            deleted += i2 - i1
            added += j2 - j1
    return added, deleted, unchanged


def _item_view(item, path):
    return {
        "path": path,
        "key": item.key,
        "name": item.name,
        "kind": getattr(item, "kind", ""),
        "container": getattr(item, "container", ""),
        "signature": getattr(item, "signature", ""),
        "counts": item.counts,
        "body_hash": item.body_hash,
        "own_lines": item.own_lines,
    }


def _collect(results, attr):
    out = []
    for fr in results:
        if fr.status != "counted":
            continue
        for item in getattr(fr, attr):
            out.append(_item_view(item, fr.path))
    return out


def _pair(before, after, status, stage, signature_changed=False):
    added, deleted, unchanged = line_breakdown(before["own_lines"], after["own_lines"])
    return {
        "status": status,
        "match_stage": stage,
        "signature_changed": signature_changed,
        "path_before": before["path"], "path_after": after["path"],
        "key_before": before["key"], "key_after": after["key"],
        "name": after["name"], "kind": after["kind"],
        "before_counts": before["counts"], "after_counts": after["counts"],
        "delta": after["counts"] - before["counts"],
        "lines_added": added, "lines_deleted": deleted,
        "lines_unchanged": unchanged,
    }


def _solo(item, status):
    empty = Counts()
    if status == "added":
        return {"status": status, "match_stage": "none", "signature_changed": False,
                "path_before": "", "path_after": item["path"],
                "key_before": "", "key_after": item["key"],
                "name": item["name"], "kind": item["kind"],
                "before_counts": empty, "after_counts": item["counts"],
                "delta": item["counts"],
                "lines_added": 0, "lines_deleted": 0, "lines_unchanged": 0}
    return {"status": status, "match_stage": "none", "signature_changed": False,
            "path_before": item["path"], "path_after": "",
            "key_before": item["key"], "key_after": "",
            "name": item["name"], "kind": item["kind"],
            "before_counts": item["counts"], "after_counts": empty,
            "delta": empty - item["counts"],
            "lines_added": 0, "lines_deleted": 0, "lines_unchanged": 0}


def match_items(before_items, after_items):
    pairs = []
    b_left = list(before_items)
    a_left = list(after_items)

    def take(lst, pred):
        for i, x in enumerate(lst):
            if pred(x):
                return lst.pop(i)
        return None

    # Stage 1: same path + key.
    for b in list(b_left):
        a = take(a_left, lambda x: x["path"] == b["path"] and x["key"] == b["key"])
        if a is not None:
            b_left.remove(b)
            status = "unchanged" if a["body_hash"] == b["body_hash"] else "modified"
            pairs.append(_pair(b, a, status, "exact"))
    # Stage 2: same path + container + name + kind, signature changed.
    for b in list(b_left):
        a = take(a_left, lambda x: x["path"] == b["path"]
                 and x["container"] == b["container"] and x["name"] == b["name"]
                 and x["kind"] == b["kind"])
        if a is not None:
            b_left.remove(b)
            pairs.append(_pair(b, a, "modified", "signature",
                               signature_changed=a["signature"] != b["signature"]))
    # Stage 3: body hash match -> moved (same name) or renamed (different name).
    for b in list(b_left):
        a = take(a_left, lambda x: x["body_hash"] == b["body_hash"])
        if a is not None:
            b_left.remove(b)
            status = "moved" if a["name"] == b["name"] else "renamed"
            pairs.append(_pair(b, a, status, "body_hash"))
    for b in b_left:
        pairs.append(_solo(b, "deleted"))
    for a in a_left:
        pairs.append(_solo(a, "added"))
    pairs.sort(key=lambda p: (p["path_after"] or p["path_before"], p["key_after"] or p["key_before"]))
    return pairs


def compare_results(before_results, after_results):
    bmap = {r.path: r for r in before_results if r.status == "counted"}
    amap = {r.path: r for r in after_results if r.status == "counted"}
    file_pairs = []
    for path in sorted(set(bmap) | set(amap)):
        b, a = bmap.get(path), amap.get(path)
        if b is not None and a is not None:
            added, deleted, unchanged = line_breakdown(b.effective_lines(), a.effective_lines())
            status = "unchanged" if a.counts == b.counts and deleted == 0 and added == 0 else "modified"
            file_pairs.append({
                "path": path, "status": status,
                "before_counts": b.counts, "after_counts": a.counts,
                "delta": a.counts - b.counts,
                "lines_added": added, "lines_deleted": deleted,
                "lines_unchanged": unchanged,
            })
        elif a is not None:
            file_pairs.append({"path": path, "status": "added",
                               "before_counts": Counts(), "after_counts": a.counts,
                               "delta": a.counts, "lines_added": 0,
                               "lines_deleted": 0, "lines_unchanged": 0})
        else:
            file_pairs.append({"path": path, "status": "deleted",
                               "before_counts": b.counts, "after_counts": Counts(),
                               "delta": Counts() - b.counts, "lines_added": 0,
                               "lines_deleted": 0, "lines_unchanged": 0})
    functions = match_items(_collect(before_results, "functions"),
                            _collect(after_results, "functions"))
    units = match_items(_collect(before_results, "units"),
                        _collect(after_results, "units"))
    return {"files": file_pairs, "functions": functions, "units": units}
