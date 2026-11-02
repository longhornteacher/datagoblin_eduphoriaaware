"""Audit project contents and reproduce the three approved synthetic packets.

No private setting, original workbook or identity map is read. This is a release
gate for known artifacts, not a general PII detector or access-control boundary.
"""

from pathlib import Path
import json
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from aware_results.export import GUIDE, build_packet, safe_key
from aware_results.storage import connect, import_report, initialize_store
from synthetic_xlsx import items, students

ROOT_FILES = {".gitignore", "AGENTS.md", "PROJECT_HANDOFF.md", "README.md", "LICENSE",
              "requirements.txt", "requirements-dev.txt", "config.example.toml"}
SOURCE_FOLDERS = {"src", "scripts", "tests", "docs", "templates", "examples", ".github"}
SOURCE_EXTENSIONS = {".py", ".md", ".json", ".sql", ".toml", ".txt", ".yml", ".yaml"}
REVIEWED_JSON = {
    "templates/standards.json", "templates/report-contract.schema.json", "templates/observation.schema.json",
    "templates/student-learning-standards/contract.json", "templates/group-item-analysis/contract.json",
    "tests/fixtures/synthetic_layout_cases.json",
    *[f"templates/observations/{method}-{year}-g{grade}.json" for method in ("slsb", "itemperc") for year, grade in ((2025, 5), (2026, 6))],
    *[f"examples/synthetic-{kind}-packet/data.json" for kind in ("student", "group", "course")],
}


class RepositoryPrivacyError(ValueError):
    pass


def inventory(root: Path) -> int:
    count = 0
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = [name for name in folders if name != ".git"]
        for name in [*folders, *files]:
            path = Path(directory) / name
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise RepositoryPrivacyError("workspace_link_requires_review")
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root)
            if "__pycache__" in relative.parts and path.suffix == ".pyc":
                continue
            allowed = (len(relative.parts) == 1 and name in ROOT_FILES) or (
                len(relative.parts) > 1 and relative.parts[0] in SOURCE_FOLDERS and path.suffix in SOURCE_EXTENSIONS
            )
            if not allowed:
                raise RepositoryPrivacyError("unapproved_file_or_private_configuration")
            if path.suffix == ".json" and relative.as_posix() not in REVIEWED_JSON:
                raise RepositoryPrivacyError("unreviewed_json_dataset")
            if path.suffix == ".toml" and relative.as_posix() != "config.example.toml":
                raise RepositoryPrivacyError("unreviewed_configuration")
            payload = path.read_bytes()
            if b"\0" in payload:
                raise RepositoryPrivacyError("unexpected_binary_content")
            payload.decode("utf-8")
            count += 1
    return count


def comparable_tables(packet: dict) -> dict:
    tables = json.loads(json.dumps(packet["tables"]))
    if "students" in tables:
        rows = tables["students"]["rows"]
        aliases = [safe_key(row[0], "s") for row in rows]
        if len(aliases) != len(set(aliases)):
            raise RepositoryPrivacyError("synthetic_packet_alias_conflict")
        tables["students"]["rows"] = sorted((row[1:] for row in rows), key=lambda row: json.dumps(row))
    return tables


def verify_packet(directory: Path, expected: dict) -> None:
    if {p.name for p in directory.iterdir()} != {"data.json", "README.md"}:
        raise RepositoryPrivacyError("unreviewed_example_file")
    actual = json.loads((directory / "data.json").read_text(encoding="utf-8"))
    if set(actual) != set(expected):
        raise RepositoryPrivacyError("unreviewed_packet_fields")
    for key, prefix in (("assessment_key", "a"), ("snapshot_key", "r"), ("provenance_ref", "v"),
                        ("standards_scope_key", "f"), ("population_key", "p")):
        if key in actual:
            safe_key(actual[key], prefix)
    if (actual["format"] != expected["format"] or actual["method"] != expected["method"]
            or comparable_tables(actual) != comparable_tables(expected)
            or (directory / "README.md").read_text(encoding="utf-8") != GUIDE):
        raise RepositoryPrivacyError("example_does_not_match_synthetic_fixture")


def check_repository(root: Path = ROOT) -> tuple[int, int]:
    root = root.resolve()
    count = inventory(root)
    context = {"source_namespace": "SYNTHETIC_PRIVATE_NAMESPACE", "assessment_ref": "SYNTHETIC_PRIVATE_ASSESSMENT",
               "population_ref": "SYNTHETIC_PRIVATE_POPULATION", "framework_ref": "SYNTHETIC_PRIVATE_FRAMEWORK"}
    with tempfile.TemporaryDirectory() as temporary:
        scratch = Path(temporary).resolve()
        work = scratch / "work"
        initialize_store(work)
        course = students(2)
        course.put("F3", "A.5(C)")
        course.put("G3", "A.10(B) [S]")
        cases = [
            ("synthetic-student-packet", students(29), "student_learning_standards", context),
            ("synthetic-group-packet", items(5), "group_item_analysis", context),
            ("synthetic-course-packet", course, "student_learning_standards",
             {**context, "assessment_ref": "SYNTHETIC_PRIVATE_COURSE", "framework_ref": "SYNTHETIC_PRIVATE_COURSE_FRAMEWORK",
              "subject": "mathematics", "framework_version": "synthetic-version", "course_code": "A"}),
        ]
        for name, spec, method, scope in cases:
            source = scratch / (name + ".xlsx")
            spec.save(source)
            snapshot, _ = import_report(work, source, method, scope)
            connection = connect(work)
            try:
                expected = build_packet(connection, snapshot)
            finally:
                connection.close()
            verify_packet(root / "examples" / name, expected)
    return count, len(cases)


def main() -> int:
    try:
        count, examples = check_repository()
    except RepositoryPrivacyError as error:
        print(f"Repository privacy check failed: {error}", file=sys.stderr)
        return 1
    except Exception:
        print("Repository privacy check failed: unreviewed_or_invalid_artifact", file=sys.stderr)
        return 1
    print(f"Repository inventory passed ({count} reviewed project files); {examples} packet datasets match independent synthetic fixtures.")
    print("No private sync files or real student records were opened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
