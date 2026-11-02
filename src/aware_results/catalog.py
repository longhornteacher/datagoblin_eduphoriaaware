"""Framework-scoped shared standards and private original-label provenance."""

from .errors import require
from .standards import Standard, normalize_standard


CATALOG_SCHEMA = """
CREATE TABLE standards_frameworks(
 framework_key TEXT PRIMARY KEY, source_namespace TEXT NOT NULL, framework_ref TEXT NOT NULL,
 subject TEXT, framework_version TEXT, course_code TEXT,
 UNIQUE(source_namespace,framework_ref));
"""


def standards_table_sql(name="standards"):
    return f"""CREATE TABLE {name}(
 standard_key TEXT PRIMARY KEY, framework_key TEXT NOT NULL REFERENCES standards_frameworks,
 standard_code TEXT NOT NULL, grade INTEGER, knowledge_skill_number INTEGER NOT NULL,
 student_expectation TEXT NOT NULL, subexpectation TEXT, description TEXT,
 level_code TEXT NOT NULL, level_kind TEXT NOT NULL, course_code TEXT,
 CHECK((level_kind='grade' AND grade IS NOT NULL AND grade BETWEEN 0 AND 12 AND level_code=CAST(grade AS TEXT) AND course_code IS NULL)
    OR (level_kind='kindergarten' AND grade IS NULL AND level_code='K' AND course_code IS NULL)
    OR (level_kind='course' AND grade IS NULL AND course_code IS NOT NULL AND course_code=level_code)),
 CHECK(substr(standard_code,1,length(level_code)+1)=level_code||'.'),
 UNIQUE(framework_key,standard_code), UNIQUE(standard_key,standard_code));"""


def labels_table_sql(name="standard_source_labels", catalog="standards"):
    return f"""CREATE TABLE {name}(
 snapshot_key TEXT NOT NULL REFERENCES imports, source_kind TEXT NOT NULL,
 source_key TEXT NOT NULL, standard_key TEXT NOT NULL REFERENCES {catalog},
 source_label TEXT NOT NULL, source_tag TEXT,
 PRIMARY KEY(snapshot_key,source_kind,source_key));"""


CATALOG_SCHEMA += standards_table_sql() + labels_table_sql()


def student_table_sql(name="student_standard_results", catalog="standards"):
    return f"""CREATE TABLE {name}(
 snapshot_key TEXT NOT NULL REFERENCES imports, student_alias TEXT NOT NULL,
 standard_code TEXT NOT NULL, reported_ratio REAL CHECK(reported_ratio BETWEEN 0 AND 1),
 source_label TEXT NOT NULL, source_tag TEXT, standard_key TEXT NOT NULL,
 PRIMARY KEY(snapshot_key,student_alias,standard_code),
 FOREIGN KEY(snapshot_key,student_alias) REFERENCES attempt_summaries,
 FOREIGN KEY(standard_key,standard_code) REFERENCES {catalog}(standard_key,standard_code));"""


def group_table_sql(name="group_item_results", catalog="standards"):
    return f"""CREATE TABLE {name}(
 snapshot_key TEXT NOT NULL REFERENCES imports, question_label TEXT NOT NULL,
 standard_code TEXT NOT NULL, reported_total_students INTEGER NOT NULL CHECK(reported_total_students>=0),
 reported_correct_ratio REAL CHECK(reported_correct_ratio BETWEEN 0 AND 1), standard_key TEXT NOT NULL,
 PRIMARY KEY(snapshot_key,question_label),
 FOREIGN KEY(standard_key,standard_code) REFERENCES {catalog}(standard_key,standard_code));"""


def register_standard(connection, context: dict, standard: Standard) -> str:
    from .storage import opaque

    framework = connection.execute("SELECT * FROM standards_frameworks WHERE source_namespace=? AND framework_ref=?", (context["source_namespace"], context["framework_ref"])).fetchone()
    framework_key = framework[0] if framework else opaque("f")
    if not framework:
        connection.execute("INSERT INTO standards_frameworks VALUES (?,?,?,?,?,?)", (framework_key, context["source_namespace"], context["framework_ref"], context.get("subject"), context.get("framework_version"), context.get("course_code")))
    else:
        for field in ("subject", "framework_version", "course_code"):
            if field in context:
                require(framework[field] is None or framework[field] == context[field], "framework_details_conflict")
                if framework[field] is None:
                    if field == "course_code":
                        conflict = connection.execute("SELECT 1 FROM standards WHERE framework_key=? AND (course_code IS NULL OR course_code!=?) LIMIT 1", (framework_key, context[field])).fetchone()
                        require(conflict is None, "framework_course_conflict")
                    connection.execute(f"UPDATE standards_frameworks SET {field}=? WHERE framework_key=?", (context[field], framework_key))
    details = connection.execute("SELECT subject,framework_version,course_code FROM standards_frameworks WHERE framework_key=?", (framework_key,)).fetchone()
    if standard.course_code is not None:
        require(details["course_code"] == standard.course_code and bool(details["subject"]) and bool(details["framework_version"]), "course_scope_required_or_conflicting")
    else:
        require(details["course_code"] is None, "course_scope_required_or_conflicting")
    existing = connection.execute("SELECT standard_key FROM standards WHERE framework_key=? AND standard_code=?", (framework_key, standard.code)).fetchone()
    if existing:
        return existing[0]
    key = opaque("t")
    connection.execute("INSERT INTO standards VALUES (?,?,?,?,?,?,?,NULL,?,?,?)", (key, framework_key, standard.code, standard.grade, standard.knowledge_skill_number, standard.student_expectation, standard.subexpectation, standard.level_code, standard.level_kind, standard.course_code))
    return key


def register_report_standards(connection, snapshot: str, report, context: dict) -> dict[str, str]:
    keys = {}
    for source in report.standards:
        label = source.get("label", source["code"])
        normalized = normalize_standard(label)
        require(normalized.code == source["code"], "standard_catalog_mismatch")
        keys[normalized.code] = register_standard(connection, context, normalized)
    if report.method == "student_learning_standards":
        for source in report.standards:
            connection.execute("INSERT INTO standard_source_labels VALUES (?,?,?,?,?,?)", (snapshot, "student_standard", source["code"], keys[source["code"]], source["label"], source["tag"]))
    else:
        for row in report.rows:
            connection.execute("INSERT INTO standard_source_labels VALUES (?,?,?,?,?,?)", (snapshot, "group_item", row["question"], keys[row["standard"]], row["standard_label"], row["standard_tag"]))
    return keys
