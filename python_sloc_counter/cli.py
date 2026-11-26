"""python_sloc_counter CLI: count / compare / git-compare.
Exit codes: 0 ok, 1 fatal, 2 partial (some files could not be decoded
or counted), per DECODE-POLICY.md."""
from __future__ import annotations

import argparse
import os
import sys

from .compare import compare_results
from .counter import AbortError, count_tree
from .gitcompare import GitError, git_compare
from .output import (compare_document, count_document, render_csv,
                     render_json, render_markdown)


def _emit(doc, fmt: str, out_path: str | None) -> None:
    if fmt == "json":
        text, bom = render_json(doc), False
    elif fmt == "csv":
        text, bom = render_csv(doc), True  # UTF-8 BOM for Excel (JSON-SCHEMA.md s8)
    else:
        text, bom = render_markdown(doc), False
    if out_path:
        data = text.encode("utf-8-sig" if bom else "utf-8")
        with open(out_path, "wb") as fh:
            fh.write(data)
    else:
        if bom:
            sys.stdout.write("﻿")
        sys.stdout.write(text)


def _exit_code(results) -> int:
    return 2 if any(r.status == "error" for r in results) else 0


def _common(p):
    p.add_argument("--format", choices=["json", "csv", "md"], default="json")
    p.add_argument("-o", "--output")
    p.add_argument("--encoding", help="force an encoding for all files")
    p.add_argument("--on-error", choices=["strict", "abort", "replace"],
                   default="strict",
                   help="how to handle undecodable files (default: strict)")
    p.add_argument("--strict-detection", action="store_true",
                   help="treat ambiguous encoding detection as an error")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python-sloc-counter")
    sub = parser.add_subparsers(dest="command", required=True)

    p_count = sub.add_parser("count", help="count steps in a file or folder")
    p_count.add_argument("path")
    _common(p_count)

    p_cmp = sub.add_parser("compare", help="compare two snapshots (folders or files)")
    p_cmp.add_argument("before")
    p_cmp.add_argument("after")
    _common(p_cmp)

    p_git = sub.add_parser("git-compare", help="compare two refs of a git repository")
    p_git.add_argument("repo")
    p_git.add_argument("before")
    p_git.add_argument("after")
    _common(p_git)

    args = parser.parse_args(argv)
    try:
        if args.command == "count":
            if not os.path.exists(args.path):
                print(f"python-sloc-counter: no such path: {args.path}", file=sys.stderr)
                return 1
            results = count_tree(args.path, args.encoding, args.on_error,
                                 args.strict_detection)
            _emit(count_document(results, args.path), args.format, args.output)
            return _exit_code(results)

        if args.command == "compare":
            for p in (args.before, args.after):
                if not os.path.exists(p):
                    print(f"python-sloc-counter: no such path: {p}", file=sys.stderr)
                    return 1
            before = count_tree(args.before, args.encoding, args.on_error,
                                args.strict_detection)
            after = count_tree(args.after, args.encoding, args.on_error,
                               args.strict_detection)
            comp = compare_results(before, after)
            _emit(compare_document(comp, args.before, args.after),
                  args.format, args.output)
            return 2 if _exit_code(before) or _exit_code(after) else 0

        # git-compare
        if not os.path.isdir(args.repo):
            print(f"python-sloc-counter: no such directory: {args.repo}", file=sys.stderr)
            return 1
        comp, meta = git_compare(args.repo, args.before, args.after,
                                 args.encoding, args.on_error,
                                 args.strict_detection)
        resolved = {"before_commit": meta["before_commit"],
                    "after_commit": meta["after_commit"]}
        _emit(compare_document(comp, args.before, args.after, resolved),
              args.format, args.output)
        return 2 if _exit_code(meta["before_results"]) or \
            _exit_code(meta["after_results"]) else 0
    except AbortError as exc:
        print(f"python-sloc-counter: aborted: {exc}", file=sys.stderr)
        return 1
    except GitError as exc:
        print(f"python-sloc-counter: git error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
