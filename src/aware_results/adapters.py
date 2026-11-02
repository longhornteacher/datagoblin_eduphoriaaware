"""Literal-value adapters for the two documented, single-sheet XLSX families.

No source titles, names, metadata or arbitrary text can become exported labels.
Fixtures, rather than real records, exercise these adapters during development.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
import math
from pathlib import Path
import re
import warnings
from zipfile import ZipFile

from openpyxl import load_workbook

from .errors import PipelineError, require
from .standards import normalize_standard, standard_sort_key


TEMPLATES = Path(__file__).resolve().parents[2] / "templates"
METHODS = ("student_learning_standards", "group_item_analysis")
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_CELLS = 2_000_000
MAX_ROWS = 100_000


@dataclass
class ParsedReport:
    method: str
    contract_version: str
    standards: list[dict]
    rows: list[dict]


def contract_for(method: str) -> dict:
    require(method in METHODS, "unknown_method")
    return json.loads((TEMPLATES / method.replace("_", "-") / "contract.json").read_text(encoding="utf-8"))


def header(value) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) else None


def literal(cell):
    require(cell.data_type not in ("f", "e"), "formula_or_error_cell")
    return cell.value


def text(cell, *, required=False) -> str | None:
    value = literal(cell)
    if value is None and not required:
        return None
    require(isinstance(value, str), "text_value_required")
    if required:
        require(bool(value.strip()) and value == value.strip(), "invalid_identity_or_label")
    return value


def number(cell, *, ratio=False, integer=False, required=False, formats=None):
    value = literal(cell)
    if value is None:
        require(not required, "required_number_missing")
        return None
    require(type(value) in (int, float), "numeric_literal_required")
    require(math.isfinite(value), "nonfinite_number")
    if formats is not None:
        require(cell.number_format in formats, "number_format_unrecognized")
    if ratio:
        require(cell.number_format in ("0%", "0.00%"), "percent_format_unrecognized")
        require(0 <= value <= 1, "ratio_out_of_range")
    else:
        require(cell.number_format == "General", "number_format_unrecognized")
    if integer:
        require(value >= 0 and int(value) == value and value <= 2**53 - 1, "nonnegative_integer_required")
        return int(value)
    return value


def find_headers(sheet, contract: dict) -> tuple[int, dict[str, int]]:
    required = set(contract["detection"]["required_headers"])
    optional = set(contract["detection"]["optional_headers"])
    matches = []
    # A bounded structural search permits blank/preamble rows without scanning
    # arbitrary student names as possible headers throughout the workbook.
    for row in sheet.iter_rows(min_row=1, max_row=min(20, sheet.max_row)):
        labels = [header(cell.value) for cell in row]
        if not required <= set(labels):
            continue
        populated = [label for label in labels if label is not None]
        require(len(populated) == len(set(populated)), "duplicate_header")
        require(set(populated) <= required | optional, "unknown_header")
        require(all(cell.value is None or isinstance(cell.value, str) for cell in row), "unknown_header")
        matches.append((row[0].row, {label: cell.column for cell, label in zip(row, labels) if label is not None}))
    require(len(matches) == 1, "header_not_unique_or_missing")
    return matches[0]


def validate_sheet(sheet):
    require(sheet.sheet_state == "visible", "hidden_sheet_unsupported")
    require(not any(dim.hidden for dim in sheet.row_dimensions.values()), "hidden_rows_unsupported")
    require(not any(dim.hidden for dim in sheet.column_dimensions.values()), "hidden_columns_unsupported")
    require(not sheet.tables and not sheet.auto_filter.ref, "filtered_or_table_layout_unsupported")


def validate_rows(sheet, *, data_start: int, allowed_columns: set[int], allowed_merge=None):
    for merge in sheet.merged_cells.ranges:
        if merge.max_row >= data_start:
            require(allowed_merge is not None and str(merge) == str(allowed_merge), "data_merge_unsupported")
    for row in sheet.iter_rows(min_row=data_start):
        for cell in row:
            if cell.value is not None:
                require(cell.column in allowed_columns, "unknown_populated_column")
                literal(cell)


def parse_students(sheet, contract: dict, row: int, columns: dict) -> ParsedReport:
    container_col = columns["All Learning Standards"]
    groups = [m for m in sheet.merged_cells.ranges if m.min_row == row and m.max_row == row and m.min_col == container_col]
    require(len(groups) == 1, "standards_merge_missing")
    group = groups[0]
    require(not (set(columns.values()) - {container_col}) & set(range(group.min_col, group.max_col + 1)), "header_overlap")
    band_end = row + 1
    for col in set(columns.values()) - {container_col}:
        merges = [m for m in sheet.merged_cells.ranges if (m.min_row, m.max_row, m.min_col, m.max_col) == (row, band_end, col, col)]
        require(len(merges) == 1, "header_merge_unsupported")
    # No other populated child headers outside the standard container.
    require(all(c.value is None or group.min_col <= c.column <= group.max_col for c in sheet[band_end]), "unknown_child_header")
    pattern = re.compile(contract["dynamic_axis"]["standard_label_pattern"])
    standards = []
    for col in range(group.min_col, group.max_col + 1):
        label = text(sheet.cell(band_end, col), required=True)
        match = pattern.fullmatch(label)
        require(match is not None, "standard_label_unrecognized")
        normalized = normalize_standard(label)
        standards.append({"code": normalized.code, "tag": normalized.source_tag, "label": label, "column": col})
    require(len({s["code"] for s in standards}) == len(standards), "duplicate_standard")
    allowed = set(columns.values()) | set(range(group.min_col, group.max_col + 1))
    validate_rows(sheet, data_start=band_end + 1, allowed_columns=allowed)
    rows, ids = [], set()
    score_labels = ("Raw Score", "Scale Score", "Percent Score")
    formats = {field["source"]: field["observed_formats"] for field in contract["fields"]}
    flag_labels = ("Approaches Grade Level (TX)", "Meets Grade Level (TX)", "Masters Grade Level (TX)")
    for r in range(band_end + 1, sheet.max_row + 1):
        if not any(sheet.cell(r, c).value is not None for c in allowed):
            continue
        local_id = text(sheet.cell(r, columns["Local ID"]), required=True)
        require(local_id not in ids, "duplicate_student")
        ids.add(local_id)
        name = text(sheet.cell(r, columns["Student Name"]))
        # Keep private flags literal, with no guessed boolean vocabulary.
        flags = {label: text(sheet.cell(r, columns[label])) for label in flag_labels}
        for label in contract["detection"]["optional_headers"]:
            if label in columns:
                text(sheet.cell(r, columns[label]))
        scores = [number(sheet.cell(r, columns[label]), ratio=(label == "Percent Score"), formats=formats[label]) for label in score_labels]
        values = [number(sheet.cell(r, s["column"]), ratio=True, formats=formats["All Learning Standards"]) for s in standards]
        rows.append({"local_id": local_id, "name": name, "scores": scores, "ratios": values, "raw_flags": flags, "row": r,
                     "score_cells": [sheet.cell(r, columns[label]).coordinate for label in score_labels],
                     "standard_cells": [sheet.cell(r, s["column"]).coordinate for s in standards]})
    require(bool(rows), "no_data_rows")
    return ParsedReport(contract["method_id"], contract["version"], standards, rows)


def parse_items(sheet, contract: dict, row: int, columns: dict) -> ParsedReport:
    first_col = min(columns.values())
    group_col = first_col - 1
    require(group_col >= 1 and sorted(columns.values()) == list(range(first_col, first_col + 4)), "item_header_geometry_unsupported")
    groups = [m for m in sheet.merged_cells.ranges if m.min_col == m.max_col == group_col and m.min_row == row + 1]
    require(len(groups) == 1, "single_group_merge_required")
    group = groups[0]
    text(sheet.cell(group.min_row, group_col), required=True)
    validate_rows(sheet, data_start=row + 1, allowed_columns=set(columns.values()) | {group_col}, allowed_merge=group)
    require(not any(c.value is not None for values in sheet.iter_rows(min_row=group.max_row + 1) for c in values), "data_outside_group")
    pattern = re.compile(contract["dynamic_axis"]["standard_label_pattern"])
    formats = {field["source"]: field["observed_formats"] for field in contract["fields"]}
    rows, questions, totals, codes = [], set(), set(), set()
    for r in range(group.min_row, group.max_row + 1):
        if not any(sheet.cell(r, c).value is not None for c in columns.values()):
            continue
        q = number(sheet.cell(r, columns["Question Number"]), integer=True, required=True)
        require(q > 0 and q not in questions, "duplicate_or_invalid_question")
        questions.add(q)
        label = text(sheet.cell(r, columns["Learning Standard Number"]), required=True)
        require(pattern.fullmatch(label) is not None, "standard_label_unrecognized")
        normalized = normalize_standard(label)
        code = normalized.code
        codes.add(code)
        total = number(sheet.cell(r, columns["Total Students"]), integer=True, required=True)
        value = number(sheet.cell(r, columns["Student Correct"]), ratio=True, formats=formats["Student Correct"])
        require(total != 0 or value is None, "zero_population_with_result")
        totals.add(total)
        rows.append({"question": str(q), "standard": code, "standard_label": label, "standard_tag": normalized.source_tag, "total": total, "ratio": value, "row": r,
                     "source_cell": sheet.cell(r, columns["Student Correct"]).coordinate})
    require(bool(rows), "no_data_rows")
    require(len(totals) == 1, "varying_population_count")
    return ParsedReport(contract["method_id"], contract["version"], [{"code": code} for code in sorted(codes, key=standard_sort_key)], rows)


def parse_xlsx(payload: bytes, method: str) -> ParsedReport:
    contract = contract_for(method)
    require(len(payload) <= MAX_FILE_BYTES, "workbook_size_limit")
    book = None
    try:
        with ZipFile(BytesIO(payload)) as archive:
            entries = archive.infolist()
            require(len(entries) < 10_000 and sum(e.file_size for e in entries) <= MAX_UNCOMPRESSED_BYTES, "workbook_expansion_limit")
            require(not any("vbaProject" in e.filename or e.filename.startswith("xl/externalLinks/") for e in entries), "active_content_unsupported")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            book = load_workbook(BytesIO(payload), data_only=False, keep_links=False)
        require(len(book.sheetnames) == 1, "single_worksheet_required")
        sheet = book.worksheets[0]
        require(sheet.max_row <= MAX_ROWS and sheet.max_row * sheet.max_column <= MAX_CELLS, "worksheet_size_limit")
        validate_sheet(sheet)
        row, columns = find_headers(sheet, contract)
        return parse_students(sheet, contract, row, columns) if method == METHODS[0] else parse_items(sheet, contract, row, columns)
    except PipelineError:
        raise
    except Exception:
        raise PipelineError("workbook_unreadable_or_unsupported") from None
    finally:
        if book is not None:
            book.close()
