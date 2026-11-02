"""Shared structural TEKS-code normalization; not an authoritative TEKS catalog.

Grade/K/course-prefix forms share one grammar. New forms are tested synthetically;
subject/adoption/course scope requires explicit private framework registration.
"""

from dataclasses import dataclass
import re

from .errors import require


LEVEL = r"(?:[0-9]+|[A-Za-z][A-Za-z0-9_-]{0,31})"
PARTS = r"(?P<level>" + LEVEL + r")\.(?P<number>[0-9]+)"
EXPECTATION = r"(?P<expectation>[A-Za-z])(?P<suffix>(?:\.[A-Za-z0-9]+)*)"
SOURCE_PATTERN = r"^" + PARTS + r"(?:\(" + EXPECTATION + r"\)|\.?(?P<plain>[A-Za-z](?:\.[A-Za-z0-9]+)*))(?: \[(?P<tag>[RSrs])\])?$"
# The single optional plain group avoids duplicate named groups across branches.
SOURCE = re.compile(SOURCE_PATTERN)
CANONICAL_PATTERN = r"^(0|[1-9]|1[0-2]|[A-Z][A-Z0-9_-]{0,31})\.[1-9][0-9]*\.[A-Z](?:\.[a-z0-9]+)*$"


@dataclass(frozen=True)
class Standard:
    code: str
    grade: int | None
    knowledge_skill_number: int
    student_expectation: str
    subexpectation: str | None
    source_label: str
    source_tag: str | None
    level_code: str
    level_kind: str
    course_code: str | None


def normalize_standard(label: str) -> Standard:
    require(isinstance(label, str), "standard_label_unrecognized")
    match = SOURCE.fullmatch(label.strip())
    require(match is not None, "standard_label_unrecognized")
    raw_level = match["level"]
    grade = int(raw_level) if raw_level.isdigit() else None
    require(grade is None or 0 <= grade <= 12, "standard_label_unrecognized")
    level = str(grade) if grade is not None else raw_level.upper()
    kind = "grade" if grade is not None else "kindergarten" if level == "K" else "course"
    course = level if kind == "course" else None
    number = int(match["number"])
    require(number > 0, "standard_label_unrecognized")
    plain = match["plain"]
    expectation = (match["expectation"] or plain[0]).upper()
    suffix = (match["suffix"] if match["expectation"] else plain[1:]).lower()
    tag = match.groupdict().get("tag")
    return Standard(f"{level}.{number}.{expectation}{suffix}", grade, number, expectation,
                    suffix[1:] or None, label, tag, level, kind, course)


def canonical_code(value: str) -> str:
    """Validate stored/exported dotted keys without silently rewriting old data."""
    standard = normalize_standard(value)
    require(standard.code == value, "noncanonical_standard_code")
    return standard.code


def _part_order(part: str):
    if part.isdigit():
        return 0, int(part)
    if part and re.fullmatch(r"m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})", part):
        values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
        total = sum(-values[c] if i + 1 < len(part) and values[c] < values[part[i + 1]] else values[c] for i, c in enumerate(part))
        return 1, total
    return 2, part


def standard_sort_key(code: str):
    standard = normalize_standard(canonical_code(code))
    level_order = (0, 0) if standard.level_kind == "kindergarten" else (1, standard.grade) if standard.grade is not None else (2, standard.level_code)
    return (level_order, standard.knowledge_skill_number, standard.student_expectation,
            tuple(_part_order(p) for p in (standard.subexpectation or "").split(".") if p), standard.code)
