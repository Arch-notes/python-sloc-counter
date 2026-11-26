"""Output layer: JSON is canonical; CSV and Markdown are derived
from the same document model (JSON-SCHEMA.md)."""
from __future__ import annotations

import csv
import io
import json

from . import __version__
from .model import Counts

SCHEMA_VERSION = "1.0"


def _totals(results):
    total = Counts()
    for r in results:
        if r.status == "counted":
            total = total + r.counts
    return total


def count_document(results, root_label: str = "") -> dict:
    by_category: dict[str, dict] = {}
    by_language: dict[str, dict] = {}
    for r in results:
        if r.status != "counted":
            continue
        for bucket, key in ((by_category, r.category), (by_language, r.language)):
            cur = bucket.setdefault(key, {"files": 0, "counts": Counts()})
            cur["files"] += 1
            cur["counts"] = cur["counts"] + r.counts
    files = []
    for r in results:
        entry = {
            "path": r.path, "category": r.category, "language": r.language,
            "language_source": r.language_source, "status": r.status,
            "encoding": r.encoding, "encoding_source": r.encoding_source,
            "warnings": r.warnings, "counts": r.counts.to_dict(),
            "non_function_counts": r.non_function_counts.to_dict(),
            "non_unit_counts": r.non_unit_counts.to_dict(),
            "functions": [{
                "key": f.key, "name": f.name, "kind": f.kind,
                "container": f.container, "signature": f.signature,
                "start_line": f.start_line, "end_line": f.end_line,
                "counts": f.counts.to_dict(), "body_hash": f.body_hash,
            } for f in r.functions],
            "classes": [{
                "key": c.key, "name": c.name,
                "start_line": c.start_line, "end_line": c.end_line,
                "counts": c.counts.to_dict(),
                "non_method_counts": c.non_method_counts.to_dict(),
            } for c in r.classes],
            "units": [{
                "key": u.key, "name": u.name, "kind": u.kind,
                "start_line": u.start_line, "end_line": u.end_line,
                "counts": u.counts.to_dict(), "body_hash": u.body_hash,
                "attributes": u.attributes,
            } for u in r.units],
        }
        if r.error:
            entry["error"] = r.error
        files.append(entry)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "count",
        "tool": {"name": "kazoe", "version": __version__},
        "root": root_label,
        "summary": {
            "files": len(results),
            "counted": sum(1 for r in results if r.status == "counted"),
            "skipped_binary": sum(1 for r in results if r.status == "skipped_binary"),
            "errors": sum(1 for r in results if r.status == "error"),
            "counts": _totals(results).to_dict(),
            "by_category": {k: {"files": v["files"], "counts": v["counts"].to_dict()}
                            for k, v in sorted(by_category.items())},
            "by_language": {k: {"files": v["files"], "counts": v["counts"].to_dict()}
                            for k, v in sorted(by_language.items())},
        },
        "files": files,
    }


def compare_document(comp: dict, before_label: str, after_label: str,
                     resolved: dict | None = None) -> dict:
    def pair_out(p, with_items=True):
        out = {
            "path": p.get("path", ""), "status": p["status"],
            "before_counts": p["before_counts"].to_dict(),
            "after_counts": p["after_counts"].to_dict(),
            "delta": p["delta"].to_dict(),
            "lines_added": p["lines_added"], "lines_deleted": p["lines_deleted"],
            "lines_unchanged": p["lines_unchanged"],
        }
        if with_items:
            out.update({
                "path_before": p["path_before"], "path_after": p["path_after"],
                "key_before": p["key_before"], "key_after": p["key_after"],
                "name": p["name"], "kind": p["kind"],
                "match_stage": p["match_stage"],
                "signature_changed": p["signature_changed"],
            })
            out.pop("path")
        return out

    doc = {
        "schema_version": SCHEMA_VERSION,
        "kind": "compare",
        "tool": {"name": "kazoe", "version": __version__},
        "before": before_label, "after": after_label,
        "files": [pair_out(p, with_items=False) for p in comp["files"]],
        "functions": [pair_out(p) for p in comp["functions"]],
        "units": [pair_out(p) for p in comp["units"]],
    }
    if resolved:
        doc["resolved"] = resolved
    return doc


def render_json(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


_COUNT_HEADER = ["category", "language", "path", "kind", "key", "name",
                 "total_lines", "effective_lines", "comment_lines", "blank_lines"]
_COMPARE_EXTRA = ["status", "match_stage", "before_total", "before_effective",
                  "after_total", "after_effective", "delta_total", "delta_effective",
                  "lines_added", "lines_deleted", "lines_unchanged"]


def render_csv(doc: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    if doc["kind"] == "count":
        w.writerow(_COUNT_HEADER)
        for f in doc["files"]:
            if f["status"] != "counted":
                continue
            c = f["counts"]
            w.writerow([f["category"], f["language"], f["path"], "file", "",
                        f["path"].rsplit("/", 1)[-1],
                        c["total"], c["effective"], c["comment"], c["blank"]])
            for fn in f["functions"]:
                c = fn["counts"]
                w.writerow([f["category"], f["language"], f["path"], "function",
                            fn["key"], fn["name"],
                            c["total"], c["effective"], c["comment"], c["blank"]])
            for cl in f.get("classes", []):
                c = cl["counts"]
                w.writerow([f["category"], f["language"], f["path"], "class",
                            cl["key"], cl["name"],
                            c["total"], c["effective"], c["comment"], c["blank"]])
                nm = cl["non_method_counts"]
                if nm["total"]:
                    w.writerow([f["category"], f["language"], f["path"],
                                "class_non_method", cl["key"], cl["name"],
                                nm["total"], nm["effective"],
                                nm["comment"], nm["blank"]])
            for u in f["units"]:
                c = u["counts"]
                w.writerow([f["category"], f["language"], f["path"], "unit",
                            u["key"], u["name"],
                            c["total"], c["effective"], c["comment"], c["blank"]])
            nf = f["non_function_counts"]
            if nf["total"]:
                w.writerow([f["category"], f["language"], f["path"], "non_function",
                            "", "", nf["total"], nf["effective"],
                            nf["comment"], nf["blank"]])
    else:
        w.writerow(_COUNT_HEADER + _COMPARE_EXTRA)
        for section, kind in (("files", "file"), ("functions", "function"),
                              ("units", "unit")):
            for p in doc[section]:
                path = p.get("path") or p.get("path_after") or p.get("path_before")
                key = p.get("key_after") or p.get("key_before") or ""
                name = p.get("name") or path.rsplit("/", 1)[-1]
                bc, ac, d = p["before_counts"], p["after_counts"], p["delta"]
                w.writerow(["", "", path, kind, key, name,
                            ac["total"], ac["effective"], ac["comment"], ac["blank"],
                            p["status"], p.get("match_stage", ""),
                            bc["total"], bc["effective"], ac["total"], ac["effective"],
                            d["total"], d["effective"],
                            p["lines_added"], p["lines_deleted"], p["lines_unchanged"]])
    return buf.getvalue()


def render_markdown(doc: dict) -> str:
    lines = []
    if doc["kind"] == "count":
        s = doc["summary"]
        c = s["counts"]
        lines += [f"# kazoe count — {doc['root']}", "",
                  f"Files: {s['counted']} counted, {s['skipped_binary']} binary skipped, "
                  f"{s['errors']} errors",
                  f"Lines: total {c['total']}, effective {c['effective']}, "
                  f"comment {c['comment']}, blank {c['blank']}", ""]
        errors = [f for f in doc["files"] if f["status"] != "counted"]
        if errors:
            lines += ["## Files not counted", ""]
            for f in errors:
                lines.append(f"- {f['path']}: {f['status']} {f.get('error', '')}")
            lines.append("")
        lines += ["| path | category | language | total | effective | comment | blank |",
                  "|---|---|---|---:|---:|---:|---:|"]
        for f in doc["files"]:
            if f["status"] != "counted":
                continue
            c = f["counts"]
            lines.append(f"| {f['path']} | {f['category']} | {f['language']} | "
                         f"{c['total']} | {c['effective']} | {c['comment']} | {c['blank']} |")
        lines.append("")
    else:
        lines += [f"# kazoe compare — {doc['before']} -> {doc['after']}", "",
                  "| path | status | before | after | delta | +lines | -lines | unchanged |",
                  "|---|---|---:|---:|---:|---:|---:|---:|"]
        for p in doc["files"]:
            lines.append(f"| {p['path']} | {p['status']} | {p['before_counts']['effective']} "
                         f"| {p['after_counts']['effective']} | {p['delta']['effective']} "
                         f"| {p['lines_added']} | {p['lines_deleted']} | {p['lines_unchanged']} |")
        lines.append("")
        changed = [p for p in doc["functions"] + doc["units"] if p["status"] != "unchanged"]
        if changed:
            lines += ["## Changed functions / units", "",
                      "| path | name | status | before | after | delta | + | - | = |",
                      "|---|---|---|---:|---:|---:|---:|---:|---:|"]
            for p in changed:
                path = p["path_after"] or p["path_before"]
                lines.append(f"| {path} | {p['name']} | {p['status']} | "
                             f"{p['before_counts']['effective']} | {p['after_counts']['effective']} "
                             f"| {p['delta']['effective']} | {p['lines_added']} "
                             f"| {p['lines_deleted']} | {p['lines_unchanged']} |")
            lines.append("")
    return "\n".join(lines)
