"""Explicit numeric/opaque-key projections into compact agent-readable tables."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import tempfile

from .errors import require
from .standards import canonical_code, standard_sort_key
from .storage import connect, writer_lock


GUIDE = """# Reading this DataGoblin packet

Read `data.json`. Tables have `columns` once and positional `rows`; zip each row
with its columns. No original spreadsheet is needed. The packet describes one
explicit export snapshot, not automatically the latest assessment or a matched cohort.

- All ratios are underlying fractions in [0,1], with source precision retained.
- A numeric zero is a reported zero. `null` means source_blank, with no inferred
  reason. Non-null numeric cells are reported values, except the derived means.
- `std:CODE` columns contain student-standard reported ratios. They are aggregates,
  not individual item answers. Grade/suffixes remain part of the standard code.
- Standard keys use dotted LEVEL_OR_COURSE.NUMBER.EXPECTATION[.subexpectation]
  notation, e.g. K.2.B, 5.2.B.v or A.5.C. Compare codes across packets only with
  the same standards_scope_key; it scopes subject/version/course within the source
  namespace. A course prefix does not establish the student's enrolled grade.
- Raw score, scale score and percent score are distinct reported measures with
  unverified scoring denominators. Do not reconstruct points or pooled rates.
- `standard_summary` means are unweighted arithmetic means across available
  student ratios. `n_observed` and `n_missing` count that table's student rows.
- `group_items` ratios are reported group correctness measures; numerator,
  denominator and partial-credit semantics remain unverified. The original
  repeated Total Students counts are deliberately excluded.
- Student aliases persist within a private source namespace. Assessment,
  population, snapshot and provenance keys are opaque. Cite the provenance_ref,
  snapshot_key, student alias/question label and standard column to trace a fact
  through the trusted local process. Raw cell addresses are private.
- Achievement flags, identities, demographics, names, titles, filenames, group
  labels and unreviewed text are excluded. Standard codes disclose curriculum/grade.
- Do not infer a common cohort, equivalent standards, item correspondence or
  score growth across assessments. Keep student-standard and group-item grains distinct.

Pseudonymized data remains linkable student data. The trusted local user reviews
this packet before making it accessible to an analysis agent.
"""


def safe_key(value, prefix):
    require(isinstance(value, str) and re.fullmatch(prefix + r"_[A-Za-z0-9_-]{16}", value) is not None, "invalid_export_key")
    return value


def safe_number(value, *, ratio=False):
    require(value is None or (type(value) in (int, float) and math.isfinite(value)), "invalid_export_number")
    if ratio and value is not None:
        require(0 <= value <= 1, "invalid_export_ratio")
    # SQLite REAL returns 0.0/1.0 for integer-valued measurements. The shorter
    # JSON integer has exactly the same numeric value; no source precision is lost.
    if type(value) is float and value.is_integer() and abs(value) <= 2**53 - 1:
        return int(value)
    return value


def safe_code(value):
    require(isinstance(value, str), "invalid_export_standard")
    canonical_code(value)
    return value


def build_packet(connection, snapshot: str) -> dict:
    record = connection.execute("""SELECT i.method,i.assessment_key,i.population_key,i.provenance_ref,f.framework_key
        FROM imports i JOIN assessments a ON a.assessment_key=i.assessment_key
        JOIN standards_frameworks f ON f.source_namespace=a.namespace AND f.framework_ref=a.framework_ref
        WHERE i.snapshot_key=?""", (snapshot,)).fetchone()
    require(record is not None, "snapshot_not_found")
    table = "student_standard_results" if record["method"] == "student_learning_standards" else "group_item_results"
    invalid = connection.execute(f"""SELECT 1 FROM {table} r LEFT JOIN standards s ON s.standard_key=r.standard_key
        LEFT JOIN standards_frameworks f ON f.framework_key=s.framework_key
        WHERE r.snapshot_key=? AND (s.standard_key IS NULL OR s.standard_code!=r.standard_code OR s.framework_key!=?
        OR (s.course_code IS NOT NULL AND (f.course_code IS NULL OR f.course_code!=s.course_code OR f.subject IS NULL OR f.framework_version IS NULL))) LIMIT 1""", (snapshot, record["framework_key"])).fetchone()
    require(invalid is None, "standard_catalog_mismatch")
    packet = {"format": "datagoblin.agent.v1", "method": record["method"],
              "assessment_key": safe_key(record["assessment_key"], "a"),
              "snapshot_key": safe_key(snapshot, "r"), "provenance_ref": safe_key(record["provenance_ref"], "v"),
              "standards_scope_key": safe_key(record["framework_key"], "f")}
    if record["method"] == "student_learning_standards":
        codes = sorted((safe_code(row[0]) for row in connection.execute("SELECT DISTINCT standard_code FROM student_standard_results WHERE snapshot_key=?", (snapshot,))), key=standard_sort_key)
        require(bool(codes), "empty_export")
        rows = []
        aggregates = {code: [] for code in codes}
        # Each projection is explicit. Never serialize database row dictionaries
        # or pass through arbitrary source/header text to the agent artifact.
        for student in connection.execute("SELECT student_alias,raw_score,scale_score,percent_ratio FROM attempt_summaries WHERE snapshot_key=? ORDER BY student_alias", (snapshot,)):
            alias = safe_key(student["student_alias"], "s")
            values = dict(connection.execute("SELECT standard_code,reported_ratio FROM student_standard_results WHERE snapshot_key=? AND student_alias=?", (snapshot, alias)).fetchall())
            require(set(values) == set(codes), "incomplete_standard_grid")
            ratios = [safe_number(values[code], ratio=True) for code in codes]
            for code, value in zip(codes, ratios):
                if value is not None:
                    aggregates[code].append(value)
            rows.append([alias, safe_number(student["raw_score"]), safe_number(student["scale_score"]), safe_number(student["percent_ratio"], ratio=True), *ratios])
        require(bool(rows), "empty_export")
        summary = [[code, safe_number(math.fsum(aggregates[code]) / len(aggregates[code]), ratio=True) if aggregates[code] else None, len(aggregates[code]), len(rows) - len(aggregates[code])] for code in codes]
        packet["tables"] = {
            "students": {"columns": ["student_alias", "reported_raw_score", "reported_scale_score", "reported_percent_ratio", *["std:" + code for code in codes]], "rows": rows},
            "standard_summary": {"columns": ["standard_code", "mean_reported_ratio", "n_observed", "n_missing"], "rows": summary},
        }
    else:
        require(record["method"] == "group_item_analysis", "unknown_export_method")
        packet["population_key"] = safe_key(record["population_key"], "p")
        rows = []
        for item in connection.execute("SELECT question_label,standard_code,reported_correct_ratio FROM group_item_results WHERE snapshot_key=? ORDER BY CAST(question_label AS INTEGER)", (snapshot,)):
            require(re.fullmatch(r"[1-9][0-9]*", item["question_label"]) is not None, "invalid_export_question")
            rows.append([item["question_label"], safe_code(item["standard_code"]), safe_number(item["reported_correct_ratio"], ratio=True)])
        require(bool(rows), "empty_export")
        packet["tables"] = {"group_items": {"columns": ["question_label", "standard_code", "reported_correct_ratio"], "rows": rows}}
    return packet


def packet_bytes(packet: dict) -> bytes:
    return (json.dumps(packet, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def export_packet(root: Path, snapshot: str, output: Path, *, sync_root: Path | None = None) -> None:
    require(output.is_absolute(), "export_directory_must_be_absolute")
    output = output.resolve()
    for private in (root, sync_root):
        if private is not None:
            require(not output.is_relative_to(private.resolve()) and not private.resolve().is_relative_to(output), "export_private_directory_overlap")
    require(not output.exists(), "export_destination_exists")
    with writer_lock(root):
        connection = connect(root)
        try:
            data = packet_bytes(build_packet(connection, snapshot))
        finally:
            connection.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".datagoblin-packet-", dir=output.parent))
    try:
        (stage / "data.json").write_bytes(data)
        (stage / "README.md").write_text(GUIDE, encoding="utf-8")
        require(not output.exists(), "export_destination_exists")
        stage.rename(output)
    finally:
        # Only our two known files; never recursively delete an export target.
        if stage.exists():
            for name in ("data.json", "README.md"):
                (stage / name).unlink(missing_ok=True)
            stage.rmdir()
