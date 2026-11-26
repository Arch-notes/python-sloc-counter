import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kazoe.counter import count_file

TSX_SAMPLE = '''import React from "react";

export function greet(name: string): string {
  const msg = "hi " + name;
  return msg;
}

export const Button = ({ label }: { label: string }) => {
  const onClick = () => {
    console.log(label);
  };
  return <button onClick={onClick}>{label}</button>;
};

class Calc {
  add(a: number, b: number): number {
    return a + b;
  }
  get total(): number {
    return 42;
  }
}
'''


def write(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


class JsTest(unittest.TestCase):
    def test_tsx_functions(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "app.tsx")
            write(p, TSX_SAMPLE.encode())
            r = count_file(p, "app.tsx")
            self.assertEqual(r.status, "counted", r.error)
            self.assertEqual(r.language, "typescript")
            funcs = {f.key: f for f in r.functions}
            for key in ("greet", "Button", "Button.onClick", "Calc.add", "Calc.total"):
                self.assertIn(key, funcs)
            self.assertEqual(funcs["Calc.total"].kind, "getter")
            total = r.non_function_counts
            for f in r.functions:
                total = total + f.counts
            self.assertEqual(total.total, r.counts.total)
            self.assertEqual(total.effective, r.counts.effective)

    def test_plain_js(self):
        js = "function a() {\n  return 1;\n}\nconst b = function() {\n  return 2;\n};\n"
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "a.js")
            write(p, js.encode())
            r = count_file(p, "a.js")
            keys = [f.key for f in r.functions]
            self.assertEqual(keys, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
