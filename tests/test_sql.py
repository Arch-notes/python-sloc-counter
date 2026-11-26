import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from python_sloc_counter.counter import count_file

SQL_SAMPLE = '''-- migration 001
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE VIEW user_names AS
SELECT id, name FROM users;

CREATE PROCEDURE add_user(p_name TEXT)
BEGIN
  INSERT INTO users (name) VALUES (p_name);
  UPDATE counters SET n = n + 1;
END;

INSERT INTO users (name) VALUES ('seed');
'''


def write(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


class SqlTest(unittest.TestCase):
    def test_sql_units_and_functions(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "001.sql")
            write(p, SQL_SAMPLE.encode())
            r = count_file(p, "001.sql")
            self.assertEqual(r.status, "counted", r.error)
            unit_keys = [u.key for u in r.units]
            self.assertIn("table.users", unit_keys)
            self.assertIn("view.user_names", unit_keys)
            funcs = {f.key: f for f in r.functions}
            self.assertIn("add_user", funcs)
            # procedure body (with inner semicolons) is one function:
            # CREATE..END; spans 5 lines
            self.assertEqual(funcs["add_user"].counts.total, 5)
            total = r.non_function_counts
            for f in r.functions:
                total = total + f.counts
            for u in r.units:
                total = total + u.counts
            self.assertEqual(total.total, r.counts.total)


if __name__ == "__main__":
    unittest.main()
