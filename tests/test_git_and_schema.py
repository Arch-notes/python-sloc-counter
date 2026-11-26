import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kazoe.counter import count_tree
from kazoe.gitcompare import git_compare
from kazoe.output import compare_document, count_document

ROOT = os.path.join(os.path.dirname(__file__), "..")


def git(repo, *args):
    subprocess.run(["git", "-C", repo, "-c", "user.email=t@example.com",
                    "-c", "user.name=t", *args], check=True,
                   capture_output=True)


def write(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


class GitCompareTest(unittest.TestCase):
    def test_refs_compare(self):
        with tempfile.TemporaryDirectory() as td:
            repo = os.path.join(td, "repo")
            os.makedirs(repo)
            git(repo, "init", "-q")
            write(os.path.join(repo, "m.py"),
                  b"def f():\n    return 1\n")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "v1")
            write(os.path.join(repo, "m.py"),
                  b"def f():\n    return 2\n\ndef g():\n    return 3\n")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "v2")
            comp, meta = git_compare(repo, "HEAD~1", "HEAD")
            self.assertEqual(len(meta["before_commit"]), 40)
            self.assertNotEqual(meta["before_commit"], meta["after_commit"])
            by_name = {p["name"]: p for p in comp["functions"]}
            self.assertEqual(by_name["f"]["status"], "modified")
            self.assertEqual(by_name["g"]["status"], "added")
            doc = compare_document(comp, "HEAD~1", "HEAD",
                                    {"before_commit": meta["before_commit"],
                                     "after_commit": meta["after_commit"]})
            self.assertEqual(doc["resolved"]["before_commit"],
                             meta["before_commit"])


class SchemaTest(unittest.TestCase):
    def _validate(self, schema_name, doc):
        import jsonschema
        with open(os.path.join(ROOT, "schemas", schema_name)) as fh:
            schema = json.load(fh)
        jsonschema.validate(doc, schema)

    def test_count_schema(self):
        with tempfile.TemporaryDirectory() as td:
            write(os.path.join(td, "m.py"), b"def f():\n    return 1\n")
            write(os.path.join(td, "a.ts"),
                  b"export const x = () => {\n  return 1;\n};\n")
            write(os.path.join(td, "main.tf"),
                  b'resource "aws_s3_bucket" "b" {\n  bucket = "x"\n}\n')
            write(os.path.join(td, "q.sql"),
                  b"CREATE TABLE t (\n  id INTEGER\n);\n")
            doc = count_document(count_tree(td), td)
            self._validate("kazoe-count.schema.json", doc)

    def test_compare_schema(self):
        with tempfile.TemporaryDirectory() as td:
            repo = os.path.join(td, "repo")
            os.makedirs(repo)
            git(repo, "init", "-q")
            write(os.path.join(repo, "m.py"), b"def f():\n    return 1\n")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "v1")
            write(os.path.join(repo, "m.py"), b"def f():\n    return 2\n")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "v2")
            comp, meta = git_compare(repo, "HEAD~1", "HEAD")
            doc = compare_document(comp, "HEAD~1", "HEAD",
                                    {"before_commit": meta["before_commit"],
                                     "after_commit": meta["after_commit"]})
            self._validate("kazoe-compare.schema.json", doc)


class OptionsTest(unittest.TestCase):
    def test_on_error_replace_and_strict_detection(self):
        # Bytes valid in cp932 but invalid in utf-8/euc_jp strict paths can
        # still decode; use truly undecodable bytes instead.
        bad = b"\xff\xff\xff\xfe\x00abc"
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "bad.py")
            write(p, bad)
            strict = count_tree(td)
            self.assertEqual(strict[0].status, "skipped_binary")  # NUL -> binary

            p2 = os.path.join(td, "bad2.py")
            write(p2, "あ".encode("cp932")[:1] + b"\n")  # truncated multibyte
            res = count_tree(td, on_error="replace")
            by_path = {r.path: r for r in res}
            self.assertIn("decode_replaced",
                          " ".join(by_path["bad2.py"].warnings))


if __name__ == "__main__":
    unittest.main()
