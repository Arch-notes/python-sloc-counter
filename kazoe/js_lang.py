"""JavaScript / TypeScript function extraction via tree-sitter.

Identity rules (FUNCTION-IDENTITY.md + LANGUAGES-AND-OPEN-ITEMS 1.3):
- declarations and methods are keyed by their name;
- functions that get their name by assignment (variable declarator or
  assignment expression) are keyed by the assignment target — this covers
  React components such as `const Button = () => {...}`;
- anonymous callbacks are not separate units (same rule as Python lambdas).
Lines are partitioned to the innermost function, as in python_lang.
"""
from __future__ import annotations

from tree_sitter import Language, Parser

from .languages import classify_lines, counts_from_kinds
from .model import ClassUnit, Counts, FunctionUnit, body_hash

_FUNC_NODES = {"function_declaration", "generator_function_declaration",
               "function_expression", "generator_function",
               "arrow_function"}
_METHOD_NODE = "method_definition"
_CLASS_NODES = {"class_declaration", "abstract_class_declaration"}


def _parser(language: str, tsx: bool) -> Parser:
    import tree_sitter_javascript as tsjs
    import tree_sitter_typescript as tsts
    if language == "typescript":
        lang = Language(tsts.language_tsx() if tsx else tsts.language_typescript())
    else:
        lang = Language(tsjs.language())
    return Parser(lang)


def _text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _field(node, name):
    return node.child_by_field_name(name)


def extract(lines: list[str], language: str, tsx: bool = False):
    source = "\n".join(lines).encode("utf-8")
    tree = _parser(language, tsx).parse(source)
    kinds = classify_lines(lines, ("//",), (("/*", "*/"),))
    total = counts_from_kinds(kinds)
    warnings: list[str] = []
    if tree.root_node.has_error:
        warnings.append("parse_error: tree-sitter reported ERROR nodes")

    found = []  # (start_row, end_row, name, kind, container, signature)
    class_spans = []  # (qualified, name, start_row, end_row)

    def register(node, name, kind, container, start_node=None):
        params = _field(node, "parameters")
        signature = _text(params, source) if params is not None else ""
        start = (start_node or node).start_point.row
        found.append((start, node.end_point.row, name, kind, container, signature))
        qualified = f"{container}.{name}" if container else name
        walk_children(node, qualified)
        return qualified

    def walk_children(node, container):
        for child in node.children:
            walk(child, container)

    def walk(node, container):
        t = node.type
        if t in _CLASS_NODES:
            name_node = _field(node, "name")
            name = _text(name_node, source) if name_node is not None else "<anonymous>"
            qualified = f"{container}.{name}" if container else name
            class_spans.append((qualified, name, node.start_point.row,
                                node.end_point.row))
            body = _field(node, "body")
            if body is not None:
                walk_children(body, qualified)
            return
        if t in _FUNC_NODES:
            name_node = _field(node, "name")
            if name_node is not None:
                register(node, _text(name_node, source), "function", container)
                return
            # anonymous function not reached via assignment: not a unit,
            # but named functions may hide inside it.
            walk_children(node, container)
            return
        if t == _METHOD_NODE:
            name_node = _field(node, "name")
            name = _text(name_node, source) if name_node is not None else "<anonymous>"
            first = _text(node.children[0], source) if node.children else ""
            kind = {"get": "getter", "set": "setter"}.get(first, "method")
            register(node, name, kind, container)
            return
        if t == "variable_declarator":
            value = _field(node, "value")
            name_node = _field(node, "name")
            if (value is not None and value.type in _FUNC_NODES
                    and name_node is not None and name_node.type == "identifier"):
                register(value, _text(name_node, source), "function", container,
                         start_node=node)
                return
            if value is not None and value.type == "object":
                owner = _text(name_node, source) if name_node is not None else container
                qualified = f"{container}.{owner}" if container else owner
                walk_children(value, qualified)
                return
            walk_children(node, container)
            return
        if t == "assignment_expression":
            right = _field(node, "right")
            left = _field(node, "left")
            if right is not None and right.type in _FUNC_NODES and left is not None:
                register(right, _text(left, source), "function", container,
                         start_node=node)
                return
            walk_children(node, container)
            return
        walk_children(node, container)

    walk(tree.root_node, "")

    # Partition lines to the innermost function (smallest span wins).
    owner: list[int | None] = [None] * len(lines)
    for idx, (s, e, *_rest) in enumerate(found):
        for ln in range(s, e + 1):
            cur = owner[ln]
            if cur is None or (found[cur][1] - found[cur][0]) >= (e - s):
                owner[ln] = idx

    functions: list[FunctionUnit] = []
    name_seen: dict[tuple, int] = {}
    assigned = Counts()
    for idx, (s, e, name, kind, container, signature) in enumerate(found):
        c = Counts()
        own: list[str] = []
        for ln in range(len(lines)):
            if owner[ln] == idx:
                c.add_line(kinds[ln])
                if kinds[ln] == "effective":
                    own.append(lines[ln].rstrip())
        assigned = assigned + c
        group = (container, name, kind)
        ordinal = name_seen.get(group, 0)
        name_seen[group] = ordinal + 1
        qualified = f"{container}.{name}" if container else name
        key = f"{qualified}#{ordinal}" if ordinal else qualified
        functions.append(FunctionUnit(
            key=key, name=name, kind=kind, container=container,
            signature=signature, start_line=s + 1, end_line=e + 1, counts=c,
            body_hash=body_hash(lines[s:e + 1]), own_lines=own))
    non_function = total - assigned
    classes: list[ClassUnit] = []
    for qualified, name, s, e in class_spans:
        nested = [(s2, e2) for (q2, _n, s2, e2) in class_spans
                  if q2 != qualified and s <= s2 and e2 <= e and (s2, e2) != (s, e)]
        c_total = Counts()
        c_non_method = Counts()
        for ln in range(s, e + 1):
            if any(s2 <= ln <= e2 for s2, e2 in nested):
                continue
            c_total.add_line(kinds[ln])
            if owner[ln] is None:
                c_non_method.add_line(kinds[ln])
        classes.append(ClassUnit(key=qualified, name=name, start_line=s + 1,
                                 end_line=e + 1, counts=c_total,
                                 non_method_counts=c_non_method))
    return functions, total, non_function, warnings, kinds, classes
