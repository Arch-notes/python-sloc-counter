"""Git adapter: compare two refs of a repository.

The folder comparison stays the core; this adapter resolves refs to
commits, materializes each tree with `git archive`, and feeds the
folder machinery. Resolved commit hashes are reported so results can
be reproduced exactly (JSON-SCHEMA.md: resolved commits are required).
"""
from __future__ import annotations

import io
import os
import subprocess
import tarfile
import tempfile

from .compare import compare_results
from .counter import count_tree


class GitError(Exception):
    pass


def _git(repo: str, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", repo, *args],
                          capture_output=True)
    if proc.returncode != 0:
        raise GitError(proc.stderr.decode("utf-8", "replace").strip())
    return proc.stdout


def resolve_ref(repo: str, ref: str) -> str:
    return _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()


def _extract_tree(repo: str, commit: str, dest: str) -> None:
    tar_bytes = _git(repo, "archive", "--format=tar", commit)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tf:
        for member in tf.getmembers():
            target = os.path.normpath(os.path.join(dest, member.name))
            if not target.startswith(os.path.abspath(dest)):
                raise GitError(f"unsafe path in archive: {member.name}")
            if member.isfile():
                os.makedirs(os.path.dirname(target), exist_ok=True)
                src = tf.extractfile(member)
                if src is not None:
                    with open(target, "wb") as fh:
                        fh.write(src.read())


def git_compare(repo: str, ref_before: str, ref_after: str,
                explicit_encoding: str | None = None,
                on_error: str = "strict", strict_detection: bool = False):
    """Return (comparison, meta) where meta carries the resolved commits."""
    if not os.path.isdir(os.path.join(repo, ".git")) and \
            _git(repo, "rev-parse", "--git-dir") is None:
        raise GitError(f"not a git repository: {repo}")
    commit_before = resolve_ref(repo, ref_before)
    commit_after = resolve_ref(repo, ref_after)
    with tempfile.TemporaryDirectory(prefix="sloc-git-") as td:
        dir_b = os.path.join(td, "before")
        dir_a = os.path.join(td, "after")
        os.makedirs(dir_b)
        os.makedirs(dir_a)
        _extract_tree(repo, commit_before, dir_b)
        _extract_tree(repo, commit_after, dir_a)
        before = count_tree(dir_b, explicit_encoding, on_error, strict_detection)
        after = count_tree(dir_a, explicit_encoding, on_error, strict_detection)
    comp = compare_results(before, after)
    meta = {
        "repo": repo,
        "before_ref": ref_before, "after_ref": ref_after,
        "before_commit": commit_before, "after_commit": commit_after,
        "before_results": before, "after_results": after,
    }
    return comp, meta
