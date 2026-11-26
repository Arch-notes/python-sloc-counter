import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kazoe.counter import count_tree
from kazoe.output import count_document

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


class GoldenTest(unittest.TestCase):
    def test_count_output_matches_golden(self):
        doc = count_document(count_tree(os.path.join(GOLDEN_DIR, "input")), "")
        doc.pop("tool")
        doc.pop("root")
        with open(os.path.join(GOLDEN_DIR, "expected_count.json")) as fh:
            expected = json.load(fh)
        # UPDATE_GOLDEN=1 regenerates the golden file instead of comparing.
        if os.environ.get("UPDATE_GOLDEN"):
            with open(os.path.join(GOLDEN_DIR, "expected_count.json"), "w") as fh:
                json.dump(doc, fh, ensure_ascii=False, indent=2, sort_keys=True)
            self.skipTest("golden regenerated")
        self.assertEqual(doc, expected)

    def test_class_aggregation(self):
        results = {r.path: r for r in count_tree(os.path.join(GOLDEN_DIR, "input"))}
        calc = results["calc.py"].classes[0]
        self.assertEqual(calc.key, "Calc")
        self.assertEqual(calc.counts.total, 10)
        self.assertEqual(calc.non_method_counts.total, 6)
        greeter = results["app.ts"].classes[0]
        self.assertEqual(greeter.key, "Greeter")
        self.assertEqual(greeter.non_method_counts.total, 4)


if __name__ == "__main__":
    unittest.main()
