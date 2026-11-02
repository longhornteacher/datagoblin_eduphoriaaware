-- Frozen 0.2.0 format-2 schema; no student data.

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

CREATE TABLE standards_frameworks(
 framework_key TEXT PRIMARY KEY, source_namespace TEXT NOT NULL, framework_ref TEXT NOT NULL,
 UNIQUE(source_namespace,framework_ref));
CREATE TABLE standards(
 standard_key TEXT PRIMARY KEY, framework_key TEXT NOT NULL REFERENCES standards_frameworks,
 standard_code TEXT NOT NULL, grade INTEGER NOT NULL, knowledge_skill_number INTEGER NOT NULL,
 student_expectation TEXT NOT NULL, subexpectation TEXT, description TEXT,
 UNIQUE(framework_key,standard_code), UNIQUE(standard_key,standard_code));
CREATE TABLE standard_source_labels(
 snapshot_key TEXT NOT NULL REFERENCES imports, source_kind TEXT NOT NULL,
 source_key TEXT NOT NULL, standard_key TEXT NOT NULL REFERENCES standards,
 source_label TEXT NOT NULL, source_tag TEXT,
 PRIMARY KEY(snapshot_key,source_kind,source_key));
CREATE TABLE student_standard_results(
 snapshot_key TEXT NOT NULL REFERENCES imports, student_alias TEXT NOT NULL,
 standard_code TEXT NOT NULL, reported_ratio REAL CHECK(reported_ratio BETWEEN 0 AND 1),
 source_label TEXT NOT NULL, source_tag TEXT NOT NULL, standard_key TEXT NOT NULL,
 PRIMARY KEY(snapshot_key,student_alias,standard_code),
 FOREIGN KEY(snapshot_key,student_alias) REFERENCES attempt_summaries,
 FOREIGN KEY(standard_key,standard_code) REFERENCES standards(standard_key,standard_code));CREATE TABLE group_item_results(
 snapshot_key TEXT NOT NULL REFERENCES imports, question_label TEXT NOT NULL,
 standard_code TEXT NOT NULL, reported_total_students INTEGER NOT NULL CHECK(reported_total_students>=0),
 reported_correct_ratio REAL CHECK(reported_correct_ratio BETWEEN 0 AND 1), standard_key TEXT NOT NULL,
 PRIMARY KEY(snapshot_key,question_label),
 FOREIGN KEY(standard_key,standard_code) REFERENCES standards(standard_key,standard_code));