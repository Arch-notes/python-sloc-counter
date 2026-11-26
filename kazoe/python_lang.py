"""Python function extraction via the standard-library ast module.

Counting rule: lines are partitioned to the innermost function that
contains them, so file = sum(functions) + non_function always holds.
A function's body_hash is taken over its full source range (including
nested definitions) and is used for move/rename matching in compare.
Lambdas are not counted separately (their lines belong to the enclosing
function), per FUNCTION-IDENTITY.md.
"""
from __future__ import annotations

import ast

from .languages import classify_lines, counts_from_kinds
from .model import ClassUnit, Counts, FunctionUnit, body_hash


def _docstring_ranges(tree) -> set[int]:
    ranges: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                doc = node.body[0]
                for ln in range(doc.lineno, (doc.end_lineno or doc.lineno) + 1):
                    ranges.add(ln - 1)
    return ranges


def _kind_of(node, in_class: bool) -> str:
    for dec in node.decorator_list:
        text = ast.unparse(dec)
        if text == "property":
            return "property"
        if text.endswith(".setter"):
            return "property-setter"
        if text.endswith(".deleter"):
            return "property-deleter"
        if text in ("staticmethod", "classmethod"):
            return text
    return "method" if in_class else "function"


def extract(lines: list[str]):
    """Return (functions, file_counts, non_function_counts, warnings)."""
    source = "\n".join(lines)
    warnings: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        warnings.append(f"parse_error: {exc.msg} (line {exc.lineno})")
        kinds = classify_lines(lines, ("#",), ())
        total = counts_from_kinds(kinds)
        return [], total, total, warnings, kinds, []

    kinds = classify_lines(lines, ("#",), (), _docstring_ranges(tree))
    total = counts_from_kinds(kinds)

    found: list[tuple[ast.AST, str, bool]] = []  # node, container, in_class
    class_spans: list[tuple[str, str, int, int]] = []  # qualified, name, start, end

    def visit(node, container: str, in_class: bool):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((child, container, in_class))
                name = f"{container}.{child.name}" if container else child.name
                visit(child, name, False)
            elif isinstance(child, ast.ClassDef):
                name = f"{container}.{child.name}" if container else child.name
                start = min([d.lineno for d in child.decorator_list]
                            + [child.lineno])
                class_spans.append((name, child.name, start,
                                    child.end_lineno or child.lineno))
                visit(child, name, True)
            else:
                visit(child, container, in_class)

    visit(tree, "", False)

    # Partition lines to the innermost containing function.
    spans = []
    for node, container, in_class in found:
        start = min([d.lineno for d in node.decorator_list] + [node.lineno])
        spans.append((node, container, in_class, start, node.end_lineno or node.lineno))
    owner: list[int | None] = [None] * len(lines)
    for idx, (_, _, _, start, end) in enumerate(spans):
        for ln in range(start - 1, end):
            if owner[ln] is None or True:
                # innermost = smallest span wins; later smaller spans overwrite
                cur = owner[ln]
                if cur is None or (spans[cur][4] - spans[cur][3]) >= (end - start):
                    owner[ln] = idx

    functions: list[FunctionUnit] = []
    per_func: dict[int, Counts] = {}
    per_func_lines: dict[int, list[str]] = {}
    name_seen: dict[tuple, int] = {}
    for idx, (node, container, in_class, start, end) in enumerate(spans):
        c = Counts()
        own: list[str] = []
        for ln in range(len(lines)):
            if owner[ln] == idx:
                c.add_line(kinds[ln])
                if kinds[ln] == "effective":
                    own.append(lines[ln].rstrip())
        per_func[idx] = c
        per_func_lines[idx] = own
        group = (container, node.name, _kind_of(node, in_class))
        ordinal = name_seen.get(group, 0)
        name_seen[group] = ordinal + 1
        qualified = f"{container}.{node.name}" if container else node.name
        key = f"{qualified}#{ordinal}" if ordinal else qualified
        try:
            signature = ast.unparse(node.args)
        except Exception:
            signature = ""
        functions.append(FunctionUnit(
            key=key, name=node.name, kind=_kind_of(node, in_class),
            container=container, signature=signature,
            start_line=start, end_line=end, counts=c,
            body_hash=body_hash(lines[start - 1:end]),
            own_lines=own,
        ))

    assigned = Counts()
    for c in per_func.values():
        assigned = assigned + c
    non_function = total - assigned

    # N1: per-class totals and non-method counts. Lines of a nested class
    # belong to the nested class, not to the outer one.
    classes: list[ClassUnit] = []
    for qualified, name, start, end in class_spans:
        nested = [(s2, e2) for (q2, _n, s2, e2) in class_spans
                  if q2 != qualified and start <= s2 and e2 <= end
                  and (s2, e2) != (start, end)]
        c_total = Counts()
        c_non_method = Counts()
        for ln in range(start - 1, end):
            if any(s2 - 1 <= ln <= e2 - 1 for s2, e2 in nested):
                continue
            c_total.add_line(kinds[ln])
            if owner[ln] is None:
                c_non_method.add_line(kinds[ln])
        classes.append(ClassUnit(key=qualified, name=name, start_line=start,
                                 end_line=end, counts=c_total,
                                 non_method_counts=c_non_method))
    return functions, total, non_function, warnings, kinds, classes
