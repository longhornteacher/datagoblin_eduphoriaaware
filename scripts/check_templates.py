"""Validate versioned report specifications. Never opens source workbooks.

This is a documentation consistency checker, not an XLSX parser or privacy scanner.
Errors intentionally omit values, document paths, and validation-library messages.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
sys.path.insert(0, str(ROOT / "src"))
from aware_results.errors import PipelineError
from aware_results.standards import CANONICAL_PATTERN, SOURCE_PATTERN, normalize_standard
PRIVATE_EXPORT_FIELDS = {
    "student_name", "local_id", "name", "id", "email", "birth_date", "dob",
    "special_ed", "emergent_bilingual", "ethnicity", "raw_response", "response",
    "source_path", "source_hash", "source_cell", "filename", "sheet_name",
    "title", "group_label", "reported_total_students",
}


class SpecificationError(ValueError):
    """A code-only specification error safe for public development output."""


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_shape(value: dict, schema: dict) -> None:
    if not Draft202012Validator(schema).is_valid(value):
        raise SpecificationError("schema_shape_invalid")


def canonical_standard(label: str, pattern: str) -> str:
    """Check documented header notation; not an assessment equivalence crosswalk."""
    match = re.fullmatch(pattern, label)
    if match is None:
        raise SpecificationError("standard_label_unrecognized")
    try:
        return normalize_standard(label).code
    except PipelineError:
        raise SpecificationError("standard_label_unrecognized") from None


def cell_position(reference: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", reference)
    if match is None:
        raise SpecificationError("cell_reference_invalid")
    column = 0
    for letter in match.group(1):
        column = column * 26 + ord(letter) - ord("A") + 1
    return int(match.group(2)), column


def validate_contract(contract: dict, schema: dict) -> None:
    validate_shape(contract, schema)
    fields = contract["fields"]
    sources = [field["source"] for field in fields]
    if len(sources) != len(set(sources)):
        raise SpecificationError("duplicate_field_source")
    targets = [field["target"] for field in fields]
    if len(targets) != len(set(targets)):
        raise SpecificationError("duplicate_field_target")
    detection = contract["detection"]
    required = set(detection["required_headers"])
    optional = set(detection["optional_headers"])
    if required & optional:
        raise SpecificationError("overlapping_header_requirements")
    if required != {field["source"] for field in fields if field["required"]}:
        raise SpecificationError("required_header_mapping_mismatch")
    if optional != {field["source"] for field in fields if not field["required"]}:
        raise SpecificationError("optional_header_mapping_mismatch")
    if contract["dynamic_axis"]["container_header"] not in required:
        raise SpecificationError("dynamic_container_not_required")
    try:
        re.compile(contract["dynamic_axis"]["standard_label_pattern"])
    except re.error:
        raise SpecificationError("standard_pattern_invalid") from None
    if contract["dynamic_axis"]["standard_label_pattern"] != SOURCE_PATTERN:
        raise SpecificationError("standard_pattern_policy_mismatch")
    private_targets = {
        field["target"].split(".")[-1]
        for field in fields if field["privacy"] == "private"
    }
    for exported in contract["export_tables"].values():
        if set(exported) & (PRIVATE_EXPORT_FIELDS | private_targets):
            raise SpecificationError("private_field_in_export_allowlist")


def validate_observation(observation: dict, contract: dict, schema: dict) -> None:
    validate_shape(observation, schema)
    level = observation["level_code"]
    grade, course = observation["grade"], observation["course_code"]
    if grade is not None:
        valid_level = level == str(grade) and course is None
    else:
        valid_level = (level == "K" and course is None) or (level != "K" and course == level)
    if not valid_level:
        raise SpecificationError("observation_level_mismatch")
    if observation["method_id"] != contract["method_id"]:
        raise SpecificationError("observation_method_mismatch")
    if observation["header_rows"] != contract["detection"]["observed_header_rows"]:
        raise SpecificationError("header_band_mismatch")
    headers = list(observation["headers"].values())
    if len(headers) != len(set(headers)):
        raise SpecificationError("duplicate_observed_header")
    required = set(contract["detection"]["required_headers"])
    optional = set(contract["detection"]["optional_headers"])
    if not required <= set(headers) or set(headers) - required - optional:
        raise SpecificationError("observed_header_set_mismatch")
    if set(observation["formats_by_field"]) != set(headers):
        raise SpecificationError("observed_format_field_mismatch")
    for field in contract["fields"]:
        if field["source"] in headers:
            if observation["formats_by_field"][field["source"]] not in field["observed_formats"]:
                raise SpecificationError("observed_format_unrecognized")
    pattern = contract["dynamic_axis"]["standard_label_pattern"]
    codes = observation["standard_codes"]
    if contract["dynamic_axis"]["kind"] == "standard_columns":
        container = next(ref for ref, label in observation["headers"].items()
                         if label == contract["dynamic_axis"]["container_header"])
        container_merges = [merge for merge in observation["header_merges"]
                            if merge.split(":")[0] == container]
        if len(container_merges) != 1:
            raise SpecificationError("standard_container_merge_invalid")
        start_ref, end_ref = container_merges[0].split(":")
        start_row, start_column = cell_position(start_ref)
        end_row, end_column = cell_position(end_ref)
        positions = {cell_position(ref) for ref in observation["standard_headers"]}
        expected_positions = {(start_row + 1, col) for col in range(start_column, end_column + 1)}
        if (start_row != end_row or start_row + 1 != observation["header_rows"]
                or not expected_positions or positions != expected_positions):
            raise SpecificationError("standard_header_geometry_mismatch")
        canonical = [canonical_standard(label, pattern)
                     for label in observation["standard_headers"].values()]
        if len(canonical) != len(set(canonical)):
            raise SpecificationError("duplicate_canonical_standard")
        if observation["standard_count"] != len(canonical) or set(canonical) != set(codes):
            raise SpecificationError("standard_coverage_mismatch")
    else:
        for code in codes:
            if canonical_standard(code, pattern) != code:
                raise SpecificationError("noncanonical_observed_standard")
        if observation["question_count"] != len(observation["question_labels"]):
            raise SpecificationError("question_count_mismatch")
        start_ref, end_ref = observation["group_merge"].split(":")
        start_row, start_column = cell_position(start_ref)
        end_row, end_column = cell_position(end_ref)
        if (start_column != end_column or start_row != observation["header_rows"] + 1
                or end_row - start_row + 1 < observation["question_count"]
                or any(cell_position(ref)[1] == start_column for ref in observation["headers"])):
            raise SpecificationError("group_merge_geometry_mismatch")


def validate_comparisons(observations: list[dict]) -> None:
    pairs = {}
    for observation in observations:
        if observation.get("comparison_group") is None:
            continue
        key = (observation["administration_year"], observation["subject"], observation["framework_version"],
               observation["standards_scope_ref"], observation["level_code"], observation["comparison_group"])
        group = pairs.setdefault(key, {})
        codes = set(observation["standard_codes"])
        method = observation["method_id"]
        if method in group and group[method] != codes:
            raise SpecificationError("paired_standard_coverage_mismatch")
        group[method] = codes
    if any(len(group) > 1 and len({frozenset(codes) for codes in group.values()}) != 1 for group in pairs.values()):
        raise SpecificationError("paired_standard_coverage_mismatch")


def check_registry(root: Path = TEMPLATES) -> tuple[int, int]:
    contract_schema = load_json(root / "report-contract.schema.json")
    observation_schema = load_json(root / "observation.schema.json")
    standards_policy = load_json(root / "standards.json")
    if (standards_policy.get("normalizer") != "aware_results.standards.normalize_standard"
            or standards_policy.get("scope_fields") != ["source_namespace", "framework_ref"]
            or standards_policy.get("catalog_database_format") != 3
            or standards_policy.get("canonical_pattern") != CANONICAL_PATTERN
            or standards_policy.get("packet_scope_field") != "standards_scope_key"):
        raise SpecificationError("standards_policy_invalid")
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(observation_schema)
    contracts = [load_json(path) for path in sorted(root.glob("*/contract.json"))]
    observations = [load_json(path) for path in sorted((root / "observations").glob("*.json"))]
    if not contracts or not observations:
        raise SpecificationError("empty_registry")
    methods = [contract["method_id"] for contract in contracts]
    ids = [observation["observation_id"] for observation in observations]
    if len(methods) != len(set(methods)) or len(ids) != len(set(ids)):
        raise SpecificationError("duplicate_registry_key")
    by_id = dict(zip(ids, observations))
    used = set()
    for contract in contracts:
        validate_contract(contract, contract_schema)
        if not (root / contract["method_id"].replace("_", "-") / "README.md").is_file():
            raise SpecificationError("missing_method_documentation")
        for observation_id in contract["observation_ids"]:
            if observation_id not in by_id or observation_id in used:
                raise SpecificationError("observation_reference_invalid")
            validate_observation(by_id[observation_id], contract, observation_schema)
            used.add(observation_id)
    if used != set(ids):
        raise SpecificationError("unreferenced_observation")
    # Compare only deliberately paired evidence within the same subject,
    # framework and report level. A missing counterpart is not fabricated.
    for observation in observations:
        if any(re.fullmatch(standards_policy["canonical_pattern"], code) is None for code in observation["standard_codes"]):
            raise SpecificationError("noncanonical_observed_standard")
    validate_comparisons(observations)
    return len(contracts), len(observations)


def main() -> int:
    try:
        contracts, observations = check_registry()
    except SpecificationError as error:
        print(f"Template check failed: {error}", file=sys.stderr)
        return 1
    except Exception:
        # JSON/schema-library errors can include an entire offending instance.
        print("Template check failed: specification_load_or_schema_error", file=sys.stderr)
        return 1
    print(f"Validated {contracts} report contracts and {observations} structural observations.")
    print("No source workbooks or student records were opened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
