"""Shared data model for count / compare results."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Counts:
    total: int = 0
    effective: int = 0
    comment: int = 0
    blank: int = 0

    def add_line(self, kind: str) -> None:
        self.total += 1
        if kind == "effective":
            self.effective += 1
        elif kind == "comment":
            self.comment += 1
        else:
            self.blank += 1

    def __add__(self, other: "Counts") -> "Counts":
        return Counts(self.total + other.total, self.effective + other.effective,
                      self.comment + other.comment, self.blank + other.blank)

    def __sub__(self, other: "Counts") -> "Counts":
        return Counts(self.total - other.total, self.effective - other.effective,
                      self.comment - other.comment, self.blank - other.blank)

    def to_dict(self) -> dict:
        return {"total": self.total, "effective": self.effective,
                "comment": self.comment, "blank": self.blank}


def body_hash(lines: list[str]) -> str:
    """Hash of normalized text: each line right-stripped, joined with LF."""
    joined = "\n".join(line.rstrip() for line in lines)
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass
class FunctionUnit:
    key: str
    name: str
    kind: str  # function | method | property | ...
    container: str
    signature: str
    start_line: int
    end_line: int
    counts: Counts
    body_hash: str
    own_lines: list = field(default_factory=list, repr=False)  # effective lines assigned to this unit


@dataclass
class Unit:
    key: str
    name: str
    kind: str  # resource | block | document | job | object | ...
    start_line: int
    end_line: int
    counts: Counts
    body_hash: str
    attributes: dict = field(default_factory=dict)
    own_lines: list = field(default_factory=list, repr=False)


@dataclass
class ClassUnit:
    key: str
    name: str
    start_line: int
    end_line: int
    counts: Counts          # lines of this class (excluding nested classes)
    non_method_counts: Counts  # of those, lines not belonging to any method


@dataclass
class FileResult:
    path: str
    category: str  # code | iac | config | docs
    language: str
    language_source: str  # extension | filename | path | content
    counts: Counts
    functions: list = field(default_factory=list)
    units: list = field(default_factory=list)
    classes: list = field(default_factory=list)
    non_function_counts: Counts = field(default_factory=Counts)
    non_unit_counts: Counts = field(default_factory=Counts)
    encoding: str = ""
    encoding_source: str = ""
    warnings: list = field(default_factory=list)
    status: str = "counted"  # counted | skipped_binary | error
    error: str = ""
    lines: list = field(default_factory=list, repr=False)  # normalized lines
    line_kinds: list = field(default_factory=list, repr=False)

    def effective_lines(self) -> list[str]:
        return [ln.rstrip() for ln, k in zip(self.lines, self.line_kinds)
                if k == "effective"]
