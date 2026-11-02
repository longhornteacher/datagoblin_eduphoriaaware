"""Explicit, backed-up v1/v2 -> current standards migration for trusted use."""

import json
from pathlib import Path
import sqlite3

from .catalog import CATALOG_SCHEMA, group_table_sql, labels_table_sql, register_standard, standards_table_sql, student_table_sql
from .errors import require
from .standards import normalize_standard
from .storage import STORE_FORMAT, connect, opaque, read_generation, validate_context, writer_lock


def upgrade_v2(connection):
    for field in ("subject", "framework_version", "course_code"):
        connection.execute(f"ALTER TABLE standards_frameworks ADD COLUMN {field} TEXT")
    statements = (standards_table_sql("standards_v3") + student_table_sql("student_standard_results_v3", "standards_v3")
                  + group_table_sql("group_item_results_v3", "standards_v3") + labels_table_sql("standard_source_labels_v3", "standards_v3"))
    for statement in statements.split(";"):
        if statement.strip():
            connection.execute(statement)
    for row in connection.execute("SELECT * FROM standards"):
        standard = normalize_standard(row["standard_code"])
        require(standard.code == row["standard_code"] and
                (standard.grade, standard.knowledge_skill_number, standard.student_expectation, standard.subexpectation) ==
                (row["grade"], row["knowledge_skill_number"], row["student_expectation"], row["subexpectation"]), "legacy_standard_requires_review")
        connection.execute("INSERT INTO standards_v3 VALUES (?,?,?,?,?,?,?,?,?,?,?)", (*tuple(row), standard.level_code, standard.level_kind, standard.course_code))
    for table in ("student_standard_results", "group_item_results", "standard_source_labels"):
        connection.execute(f"INSERT INTO {table}_v3 SELECT * FROM {table}")
        connection.execute(f"DROP TABLE {table}")
    connection.execute("DROP TABLE standards")
    connection.execute("ALTER TABLE standards_v3 RENAME TO standards")
    for table in ("student_standard_results", "group_item_results", "standard_source_labels"):
        connection.execute(f"ALTER TABLE {table}_v3 RENAME TO {table}")


def finish_migration(connection, generation):
    require(not connection.execute("PRAGMA foreign_key_check").fetchall(), "migration_integrity_failed")
    for table in ("metadata", "identities.metadata"):
        connection.execute(f"UPDATE {table} SET value=? WHERE key='format_version'", (STORE_FORMAT,))
        connection.execute(f"UPDATE {table} SET value=? WHERE key='generation'", (str(generation + 1),))


def migrate_store(root: Path) -> bool:
    with writer_lock(root):
        connection = connect(root, allow_legacy=True)
        try:
            _, generation = read_generation(connection, allow_legacy=True)
            version = connection.execute("SELECT value FROM metadata WHERE key='format_version'").fetchone()[0]
            if version == STORE_FORMAT:
                return False
            backups = root / "migrations"
            require(not backups.is_symlink() and backups.resolve().is_relative_to(root), "migration_backup_path_invalid")
            backup = backups / opaque("v" + version)
            backup.mkdir(parents=True, mode=0o700)
            for schema, name in (("main", "data.sqlite3"), ("identities", "identity.sqlite3")):
                destination = sqlite3.connect(backup / name)
                try:
                    connection.backup(destination, name=schema)
                finally:
                    destination.close()
            connection.execute("BEGIN IMMEDIATE")
            try:
                if version == "2":
                    upgrade_v2(connection)
                    finish_migration(connection, generation)
                    connection.execute("COMMIT")
                    return True
                # executescript would implicitly commit; execute constant DDL
                # statements separately so catalog/backfill changes roll back.
                schema = CATALOG_SCHEMA + student_table_sql("student_standard_results_v2") + group_table_sql("group_item_results_v2")
                for statement in schema.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                contexts = {}
                for row in connection.execute("SELECT i.snapshot_key,i.context_json,a.namespace,a.framework_ref FROM imports i JOIN assessments a ON a.assessment_key=i.assessment_key"):
                    context = validate_context(json.loads(row["context_json"]))
                    require(context["source_namespace"] == row["namespace"] and context["framework_ref"] == row["framework_ref"], "legacy_context_conflict")
                    contexts[row["snapshot_key"]] = context
                keys, labels = {}, {}

                def standard_for(row, *, source_label, source_tag, kind, source_key):
                    normalized = normalize_standard(source_label)
                    require(normalized.code == row["standard_code"] and normalized.source_tag == source_tag, "legacy_standard_requires_review")
                    context = contexts[row["snapshot_key"]]
                    catalog_id = (context["source_namespace"], context["framework_ref"], normalized.code)
                    if catalog_id not in keys:
                        keys[catalog_id] = register_standard(connection, context, normalized)
                    key = keys[catalog_id]
                    provenance_id = (row["snapshot_key"], kind, source_key)
                    provenance = (key, source_label, source_tag)
                    if provenance_id in labels:
                        require(labels[provenance_id] == provenance, "legacy_source_label_conflict")
                    else:
                        labels[provenance_id] = provenance
                        connection.execute("INSERT INTO standard_source_labels VALUES (?,?,?,?,?,?)", (*provenance_id, *provenance))
                    return key

                for row in connection.execute("SELECT * FROM student_standard_results"):
                    key = standard_for(row, source_label=row["source_label"], source_tag=row["source_tag"], kind="student_standard", source_key=row["standard_code"])
                    connection.execute("INSERT INTO student_standard_results_v2 VALUES (?,?,?,?,?,?,?)", (row["snapshot_key"], row["student_alias"], row["standard_code"], row["reported_ratio"], row["source_label"], row["source_tag"], key))
                for row in connection.execute("SELECT * FROM group_item_results"):
                    # v1 retained the dotted label verbatim as standard_code.
                    key = standard_for(row, source_label=row["standard_code"], source_tag=None, kind="group_item", source_key=row["question_label"])
                    connection.execute("INSERT INTO group_item_results_v2 VALUES (?,?,?,?,?,?)", (row["snapshot_key"], row["question_label"], row["standard_code"], row["reported_total_students"], row["reported_correct_ratio"], key))
                for table in ("student_standard_results", "group_item_results"):
                    connection.execute(f"DROP TABLE {table}")
                    connection.execute(f"ALTER TABLE {table}_v2 RENAME TO {table}")
                finish_migration(connection, generation)
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            return True
        finally:
            connection.close()
