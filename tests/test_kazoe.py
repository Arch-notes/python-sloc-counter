import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kazoe.compare import compare_results
from kazoe.counter import count_file, count_tree
from kazoe.output import count_document, compare_document, render_csv, render_json

PY_SAMPLE = '''"""モジュールの説明"""
import os

# コメント行
def greet(name):
    """挨拶を返す"""
    msg = "こんにちは" + name
    return msg


class Calc:
    def add(self, a, b):
        return a + b
'''

ENCODINGS = ["utf-8", "cp932", "euc_jp", "iso2022_jp", "utf-16"]
NEWLINES = ["\n", "\r\n", "\r"]


def write(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


class MatrixTest(unittest.TestCase):
    def test_encoding_newline_invariance(self):
        baseline = None
        with tempfile.TemporaryDirectory() as td:
            for enc in ENCODINGS:
                for nl in NEWLINES:
                    text = PY_SAMPLE.replace("\n", nl)
                    p = os.path.join(td, "sample.py")
                    write(p, text.encode(enc))
                    r = count_file(p, "sample.py")
                    self.assertEqual(r.status, "counted", (enc, nl, r.error))
                    got = (r.counts.total, r.counts.effective,
                           r.counts.comment, r.counts.blank,
                           [(f.key, f.counts.effective) for f in r.functions])
                    if baseline is None:
                        baseline = got
                    self.assertEqual(got, baseline, (enc, nl))

    def test_cross_encoding_compare_is_zero(self):
        with tempfile.TemporaryDirectory() as td:
            b = os.path.join(td, "before")
            a = os.path.join(td, "after")
            write(os.path.join(b, "sample.py"), PY_SAMPLE.encode("cp932"))
            write(os.path.join(a, "sample.py"),
                  PY_SAMPLE.replace("\n", "\r\n").encode("euc_jp"))
            comp = compare_results(count_tree(b), count_tree(a))
            fp = comp["files"][0]
            self.assertEqual(fp["status"], "unchanged")
            self.assertEqual(fp["delta"].effective, 0)
            for pair in comp["functions"]:
                self.assertEqual(pair["status"], "unchanged")


class PythonCountTest(unittest.TestCase):
    def test_checksum_and_keys(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "sample.py")
            write(p, PY_SAMPLE.encode("utf-8"))
            r = count_file(p, "sample.py")
            self.assertEqual(r.status, "counted")
            funcs = {f.key: f for f in r.functions}
            self.assertIn("greet", funcs)
            self.assertIn("Calc.add", funcs)
            total = r.non_function_counts
            for f in r.functions:
                total = total + f.counts
            self.assertEqual(total.total, r.counts.total)
            self.assertEqual(total.effective, r.counts.effective)
            # docstring lines are comments
            self.assertGreaterEqual(r.counts.comment, 3)


class CompareBreakdownTest(unittest.TestCase):
    def test_modified_function_breakdown(self):
        before = "def f():\n    a = 1\n    b = 2\n    return a + b\n"
        after = "def f():\n    a = 1\n    b = 3\n    c = 4\n    return a + b + c\n"
        with tempfile.TemporaryDirectory() as td:
            b = os.path.join(td, "before")
            a = os.path.join(td, "after")
            write(os.path.join(b, "m.py"), before.encode())
            write(os.path.join(a, "m.py"), after.encode())
            comp = compare_results(count_tree(b), count_tree(a))
            pair = [p for p in comp["functions"] if p["name"] == "f"][0]
            self.assertEqual(pair["status"], "modified")
            self.assertEqual(pair["lines_added"], 3)      # b = 3, c = 4, return ...
            self.assertEqual(pair["lines_deleted"], 2)    # b = 2, return ...
            self.assertEqual(pair["before_counts"].effective,
                             pair["lines_unchanged"] + pair["lines_deleted"])
            self.assertEqual(pair["after_counts"].effective,
                             pair["lines_unchanged"] + pair["lines_added"])


class IacTest(unittest.TestCase):
    def test_terraform_units(self):
        tf = '''resource "aws_instance" "web" {
  ami           = "abc"
  instance_type = "t3.micro"
}

variable "image_id" {
  type = string
}
'''
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "main.tf")
            write(p, tf.encode())
            r = count_file(p, "main.tf")
            self.assertEqual(r.category, "iac")
            keys = [u.key for u in r.units]
            self.assertIn("resource.aws_instance.web", keys)
            self.assertIn("variable.image_id", keys)
            total = r.non_unit_counts
            for u in r.units:
                total = total + u.counts
            self.assertEqual(total.total, r.counts.total)

    def test_kubernetes_units(self):
        yml = '''apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 2
---
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  type: ClusterIP
'''
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "k8s.yaml")
            write(p, yml.encode())
            r = count_file(p, "k8s.yaml")
            self.assertEqual(r.category, "iac")
            self.assertEqual(r.language, "kubernetes")
            self.assertEqual(len(r.units), 2)
            self.assertEqual(r.units[0].key, "apps/v1/Deployment/web")


class OutputTest(unittest.TestCase):
    def test_csv_and_json(self):
        with tempfile.TemporaryDirectory() as td:
            write(os.path.join(td, "m.py"), PY_SAMPLE.encode())
            write(os.path.join(td, "c.yaml"), b"a: 1\n# comment\nb: 2\n")
            doc = count_document(count_tree(td), td)
            text = render_json(doc)
            self.assertIn('"kind": "count"', text)
            csv_text = render_csv(doc)
            self.assertIn("total_lines", csv_text.splitlines()[0])
            self.assertIn("m.py", csv_text)
            self.assertIn("function", csv_text)


if __name__ == "__main__":
    unittest.main()
