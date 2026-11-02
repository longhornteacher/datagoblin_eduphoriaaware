-- Frozen 0.1.0 database schema, for independently populated synthetic migration tests.

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
CREATE TABLE student_standard_results(
 snapshot_key TEXT NOT NULL REFERENCES imports, student_alias TEXT NOT NULL,
 standard_code TEXT NOT NULL, reported_ratio REAL CHECK(reported_ratio BETWEEN 0 AND 1),
 source_label TEXT NOT NULL, source_tag TEXT NOT NULL,
 PRIMARY KEY(snapshot_key,student_alias,standard_code),
 FOREIGN KEY(snapshot_key,student_alias) REFERENCES attempt_summaries);
CREATE TABLE group_item_results(
 snapshot_key TEXT NOT NULL REFERENCES imports, question_label TEXT NOT NULL,
 standard_code TEXT NOT NULL, reported_total_students INTEGER NOT NULL CHECK(reported_total_students>=0),
 reported_correct_ratio REAL CHECK(reported_correct_ratio BETWEEN 0 AND 1),
 PRIMARY KEY(snapshot_key,question_label));
CREATE TABLE source_cells(
 snapshot_key TEXT NOT NULL REFERENCES imports, record_key TEXT NOT NULL, field TEXT NOT NULL,
 worksheet_ordinal INTEGER NOT NULL DEFAULT 0, source_cell TEXT NOT NULL,
 PRIMARY KEY(snapshot_key,record_key,field));
CREATE TABLE identities.metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE identities.students(
 namespace TEXT NOT NULL, local_id TEXT NOT NULL, student_alias TEXT NOT NULL UNIQUE,
 display_name TEXT, PRIMARY KEY(namespace,local_id));
