"""Private local SQLite storage; identity map is a separate attached database."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3

from . import __version__
from .adapters import MAX_FILE_BYTES, contract_for, parse_xlsx
from .catalog import CATALOG_SCHEMA, group_table_sql, register_report_standards, student_table_sql
from .errors import PipelineError, require

STORE_FORMAT = "3"

SCHEMA = """
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE assessments(
 assessment_key TEXT PRIMARY KEY, namespace TEXT NOT NULL, reference TEXT NOT NULL,
 framework_ref TEXT NOT NULL, UNIQUE(namespace,reference));
CREATE TABLE populations(
 population_key TEXT PRIMARY KEY, namespace TEXT NOT NULL, reference TEXT NOT NULL,
 UNIQUE(namespace,reference));
CREATE TABLE imports(
 snapshot_key TEXT PRIMARY KEY, source_hash TEXT NOT NULL UNIQUE, method TEXT NOT NULL,
 contract_version TEXT NOT NULL, parser_version TEXT NOT NULL, context_digest TEXT NOT NULL,
 context_json TEXT NOT NULL, assessment_key TEXT NOT NULL REFERENCES assessments,
 population_key TEXT NOT NULL REFERENCES populations, provenance_ref TEXT NOT NULL UNIQUE);
CREATE TABLE attempt_summaries(
 snapshot_key TEXT NOT NULL REFERENCES imports, student_alias TEXT NOT NULL,
 raw_score REAL, scale_score REAL, percent_ratio REAL CHECK(percent_ratio BETWEEN 0 AND 1),
 raw_flags_json TEXT NOT NULL, PRIMARY KEY(snapshot_key,student_alias));
CREATE TABLE source_cells(
 snapshot_key TEXT NOT NULL REFERENCES imports, record_key TEXT NOT NULL, field TEXT NOT NULL,
 worksheet_ordinal INTEGER NOT NULL DEFAULT 0, source_cell TEXT NOT NULL,
 PRIMARY KEY(snapshot_key,record_key,field));
CREATE TABLE identities.metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE identities.students(
 namespace TEXT NOT NULL, local_id TEXT NOT NULL, student_alias TEXT NOT NULL UNIQUE,
 display_name TEXT, PRIMARY KEY(namespace,local_id));
""" + CATALOG_SCHEMA + student_table_sql() + group_table_sql()


def opaque(prefix: str) -> str:
    return prefix + "_" + secrets.token_urlsafe(12)


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def validate_context(context: dict) -> dict:
    required = {"source_namespace", "assessment_ref", "population_ref", "framework_ref"}
    optional = {"subject", "framework_version", "course_code"}
    require(type(context) is dict and required <= set(context) and set(context) <= required | optional, "context_shape_invalid")
    require(all(isinstance(v, str) and bool(v.strip()) and v == v.strip() for v in context.values()), "context_value_invalid")
    require(("subject" in context) == ("framework_version" in context), "framework_details_incomplete")
    if "course_code" in context:
        require("subject" in context and re.fullmatch(r"[A-Z][A-Z0-9_-]{0,31}", context["course_code"]) is not None and context["course_code"] != "K", "course_context_invalid")
    return dict(context)


def validate_work_root(path: Path, *, project_root: Path, sync_root: Path | None = None) -> Path:
    require(path.is_absolute(), "work_directory_must_be_absolute")
    root = path.resolve()
    require(root != Path(root.anchor) and root != Path.home().resolve(), "work_directory_must_be_dedicated")
    for other in (project_root, sync_root):
        if other is not None:
            resolved = other.resolve()
            require(not root.is_relative_to(resolved) and not resolved.is_relative_to(root), "private_directory_overlap")
    require(not root.exists() or root.is_dir(), "work_directory_is_not_directory")
    return root


@contextmanager
def writer_lock(root: Path):
    require(root.is_dir(), "private_store_not_initialized")
    lock = root / ".writer.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise PipelineError("private_store_locked") from None
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def connect(root: Path, *, create=False, allow_legacy=False) -> sqlite3.Connection:
    for name in ("data.sqlite3", "identity.sqlite3", "originals"):
        target = root / name
        require(not target.is_symlink() and target.resolve().is_relative_to(root), "private_store_link_unsupported")
    if not create:
        require((root / "data.sqlite3").is_file() and (root / "identity.sqlite3").is_file(), "private_store_or_identity_missing")
        require((root / "originals").is_dir(), "private_archive_missing")
    connection = sqlite3.connect(root / "data.sqlite3", isolation_level=None)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("ATTACH DATABASE ? AS identities", (str(root / "identity.sqlite3"),))
        for name in ("main", "identities"):
            connection.execute(f"PRAGMA {name}.journal_mode=DELETE")
            connection.execute(f"PRAGMA {name}.synchronous=FULL")
        if not create:
            read_generation(connection, allow_legacy=allow_legacy)
        return connection
    except Exception:
        connection.close()
        raise


def read_generation(connection: sqlite3.Connection, *, allow_legacy=False) -> tuple[str, int]:
    left = dict(connection.execute("SELECT key,value FROM metadata").fetchall())
    right = dict(connection.execute("SELECT key,value FROM identities.metadata").fetchall())
    require(left == right and set(left) == {"store_id", "generation", "format_version"} and left["format_version"] in ("1", "2", STORE_FORMAT), "identity_generation_mismatch")
    require(allow_legacy or left["format_version"] == STORE_FORMAT, "store_migration_required")
    require(re.fullmatch(r"store_[A-Za-z0-9_-]{16}", left["store_id"]) is not None and re.fullmatch(r"[0-9]+", left["generation"]) is not None, "store_metadata_invalid")
    return left["store_id"], int(left["generation"])


def initialize_store(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with writer_lock(root):
        require(not any((root / name).exists() for name in ("data.sqlite3", "identity.sqlite3", "originals")), "private_store_already_exists")
        (root / "originals").mkdir(mode=0o700)
        connection = connect(root, create=True)
        try:
            connection.executescript(SCHEMA)
            entries = [("store_id", opaque("store")), ("generation", "0"), ("format_version", STORE_FORMAT)]
            connection.execute("BEGIN IMMEDIATE")
            for table in ("metadata", "identities.metadata"):
                connection.executemany(f"INSERT INTO {table} VALUES (?,?)", entries)
            connection.execute("COMMIT")
        finally:
            connection.close()


def get_identity(connection, namespace: str, local_id: str, name: str | None) -> str:
    existing = connection.execute("SELECT student_alias,display_name FROM identities.students WHERE namespace=? AND local_id=?", (namespace, local_id)).fetchone()
    if existing:
        require(existing["display_name"] == name, "identity_context_conflict")
        return existing["student_alias"]
    for _ in range(8):
        alias = opaque("s")
        if connection.execute("SELECT 1 FROM identities.students WHERE student_alias=?", (alias,)).fetchone() is None:
            connection.execute("INSERT INTO identities.students VALUES (?,?,?,?)", (namespace, local_id, alias, name))
            return alias
    raise PipelineError("alias_collision_limit")


def registered_keys(connection, context: dict) -> tuple[str, str]:
    namespace = context["source_namespace"]
    assessment = connection.execute("SELECT assessment_key,framework_ref FROM assessments WHERE namespace=? AND reference=?", (namespace, context["assessment_ref"])).fetchone()
    if assessment:
        require(assessment["framework_ref"] == context["framework_ref"], "assessment_framework_conflict")
        assessment_key = assessment["assessment_key"]
    else:
        assessment_key = opaque("a")
        connection.execute("INSERT INTO assessments VALUES (?,?,?,?)", (assessment_key, namespace, context["assessment_ref"], context["framework_ref"]))
    population = connection.execute("SELECT population_key FROM populations WHERE namespace=? AND reference=?", (namespace, context["population_ref"])).fetchone()
    population_key = population[0] if population else opaque("p")
    if not population:
        connection.execute("INSERT INTO populations VALUES (?,?,?)", (population_key, namespace, context["population_ref"]))
    return assessment_key, population_key


def import_report(root: Path, source: Path, method: str, context: dict) -> tuple[str, bool]:
    context = validate_context(context)
    contract_version = contract_for(method)["version"]
    require(source.suffix.lower() == ".xlsx", "xlsx_input_required")
    with writer_lock(root):
        connection = connect(root)
        try:
            before = source.stat()
            require(before.st_size <= MAX_FILE_BYTES, "workbook_size_limit")
            with source.open("rb") as stream:
                payload = stream.read(MAX_FILE_BYTES + 1)
            after = source.stat()
            require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and len(payload) == after.st_size, "source_changed_during_read")
            source_hash = digest(payload)
            context_json = canonical_json(context)
            context_digest = digest(context_json.encode("utf-8"))
            previous = connection.execute("SELECT * FROM imports WHERE source_hash=?", (source_hash,)).fetchone()
            if previous:
                require(previous["context_digest"] == context_digest and previous["method"] == method, "source_context_conflict")
                compatible = (previous["parser_version"], previous["contract_version"]) in {
                    (__version__, contract_version), ("0.1.0", "1.1.0"), ("0.2.0", "1.2.0")
                }
                require(compatible, "reprocessing_requires_review")
                archived = root / "originals" / (source_hash + ".xlsx")
                require(archived.is_file(), "private_archive_missing")
                require(digest(archived.read_bytes()) == source_hash, "private_archive_conflict")
                return previous["snapshot_key"], False
            report = parse_xlsx(payload, method)
            snapshot = opaque("r")
            # Immutable archive bytes survive failure as an unreferenced private
            # artifact; no identity or result is committed until validation ends.
            archive = root / "originals" / (source_hash + ".xlsx")
            if archive.exists():
                require(digest(archive.read_bytes()) == source_hash, "private_archive_conflict")
            else:
                with archive.open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            connection.execute("BEGIN IMMEDIATE")
            try:
                assessment, population = registered_keys(connection, context)
                connection.execute("INSERT INTO imports VALUES (?,?,?,?,?,?,?,?,?,?)", (snapshot, source_hash, method, report.contract_version, __version__, context_digest, context_json, assessment, population, opaque("v")))
                standard_keys = register_report_standards(connection, snapshot, report, context)
                if method == "student_learning_standards":
                    for row in report.rows:
                        alias = get_identity(connection, context["source_namespace"], row["local_id"], row["name"])
                        connection.execute("INSERT INTO attempt_summaries VALUES (?,?,?,?,?,?)", (snapshot, alias, *row["scores"], canonical_json(row["raw_flags"])))
                        for field, cell in zip(("raw_score", "scale_score", "percent_ratio"), row["score_cells"]):
                            connection.execute("INSERT INTO source_cells VALUES (?,?,?,0,?)", (snapshot, alias, field, cell))
                        for standard, value, cell in zip(report.standards, row["ratios"], row["standard_cells"]):
                            connection.execute("INSERT INTO student_standard_results VALUES (?,?,?,?,?,?,?)", (snapshot, alias, standard["code"], value, standard["label"], standard["tag"], standard_keys[standard["code"]]))
                            connection.execute("INSERT INTO source_cells VALUES (?,?,?,0,?)", (snapshot, alias, standard["code"], cell))
                else:
                    for row in report.rows:
                        connection.execute("INSERT INTO group_item_results VALUES (?,?,?,?,?,?)", (snapshot, row["question"], row["standard"], row["total"], row["ratio"], standard_keys[row["standard"]]))
                        connection.execute("INSERT INTO source_cells VALUES (?,?,?,0,?)", (snapshot, row["question"], "reported_correct_ratio", row["source_cell"]))
                _, generation = read_generation(connection)
                for table in ("metadata", "identities.metadata"):
                    connection.execute(f"UPDATE {table} SET value=? WHERE key='generation'", (str(generation + 1),))
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            return snapshot, True
        finally:
            connection.close()
