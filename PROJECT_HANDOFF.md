# Eduphoria Aware results pipeline — project handoff

## Objective

Build a local, script-driven workflow to extract, normalize, tabulate, and store student assessment results exported from Eduphoria Aware, then produce pseudonymized datasets for AI-agent analysis. Preserve a private way for the teacher to connect findings back to students.

This file preserves the original planning context. Implementation status is recorded below; adapters have not been verified against real student records.

## Implemented setup update — 2026-11-02

Before the initial development publication, all four real source workbooks and the personal path configuration were moved out of the workspace into the user's private sync folder, with lengths/SHA-256 hashes verified and a private relocation manifest. No student rows were parsed. The sync root now resolves from a persisted per-user environment setting. The repository retains only code/docs, reviewed structural metadata and independently generated synthetic datasets. A release audit and GitHub checks verify repository inventory and synthetic example reproducibility.

Report-method specifications now live in `templates/`. Private durable storage uses a per-user sync directory resolved from `DATAGOBLIN_SYNC_DIR`, including the persisted Windows user setting; Git-ignored `.datagoblin.local.toml` remains a legacy fallback. See [docs/sync-folder.md](docs/sync-folder.md) for setup and storage lifecycle. Configuration and folder creation do not establish an agent access boundary. Real records were relocated as files but have not been ingested by the pipeline.

Adapter 0.1.0 now implements both known report families, stable random aliases, a separate identity database, transactional normalized storage, compact allowlisted JSON matrices and summaries, packet queries, and closed paired snapshots for sync publication. Tests construct synthetic XLSX inputs; no supplied student records were processed. See [docs/pipeline.md](docs/pipeline.md) for commands and current limitations. The sections below remain architecture/research context rather than a declaration that every proposed capability exists.

Adapter 0.2.0 adds consistent TEKS normalization and a framework-scoped shared catalog, private original labels/tags for both report types, natural code ordering and an opaque standards-scope key in packets. Existing database-format-1 stores require an explicit paired-backup migration to format 2. See [docs/standards.md](docs/standards.md); the migration is tested on synthetic legacy stores only and has not been run against private user storage.

Adapter 0.3.0 extends that model across subject scopes, K–12 numeric grade prefixes and explicitly registered named course prefixes, with optional R/S tags. Current database format is 3, and `migrate-store` upgrades formats 1 or 2 with paired backups while preserving aliases/catalog identities. Subject/version metadata and course registrations are private explicit context. Cross-subject/course notation and report-pattern coverage is synthetic only; real supplied evidence is still grade-5/6 ELAR structure.

## User intent and decisions so far

- Work with Aware assessment reports, potentially in several formats.
- Handle variable numbers of questions without assessment-specific hardcoding.
- Prefer predictable scripted transformations and persistent storage.
- Pseudonymize student results before exposing them to agents.
- Research existing projects before choosing a foundation.
- Current recommendation: a small Python project with a local database, borrowing ideas rather than adopting an existing repository wholesale. This is a proposed implementation choice, not a user-mandated stack.

## What research established

Predictable report families can each have a reusable importer. Question columns or repeated question rows can be discovered dynamically; question count should not require a code change.

Aware documentation describes report types, configurable fields, and reusable views. Research did not locate a comprehensive, versioned export schema covering every Aware report. Therefore, do not treat online documentation as sufficient proof of the actual files' layout or semantics.

Quick Views and Saved Views offer a way to standardize exports. Different view settings, roles, assessment types, or product changes can still produce different layouts. Header labels, score meanings, missing-value conventions, and row granularity must be verified from representative files.

Prefer CSV/XLSX when available. PDFs may require separate parsers for repeated headers, page breaks, wrapping, and scanned text. Do not promise one universal parser or infer missing item-level data from an aggregate report.

Official references:

- [Vertical data views](https://support.eduphoria.net/docs/building-vertical-data-views-for-learning-standards-item-analysis-and-depth-of-knowledge): selectable fields include Question Number, Learning Standard Number/Description, Process Learning Standard Number/Description, Learning Standard Percent Correct, Student Correct, and Complexity/DOK. These are documented UI fields, not a verified export header schema.
- [Data Views Bank](https://support.eduphoria.net/docs/basic-data-analysis): Saved Views retain configured reports; Quick Views are reusable templates applied to assessments.
- [Report Types](https://support.eduphoria.net/docs/report-types): student summaries, constructed responses, and incorrect-response reports. Constructed responses support CSV export; printed reports have consolidated and detailed layouts.
- [Student Profiles](https://support.eduphoria.net/docs/navigating-to-student-profiles): profile-table CSV exports reflect selected table settings.
- [Importing Test Scores](https://support.eduphoria.net/docs/importing-test-scores): specifies an INPUT format with student ID followed by responses and no header row. This is not an export schema.

## Existing projects reviewed

Repository metadata and documentation were checked November 2, 2026. No reviewed project supplied the complete requested workflow. Code was inspected where relevant, but these projects were not executed or tested for current compatibility.

| Repository | Purpose and relevance |
|---|---|
| [skeptycal/eduphoria](https://github.com/skeptycal/eduphoria) | Early Python HTTP-request experiment targeting a hardcoded district Aware URL. No complete authentication, parsing, storage, or pseudonymization pipeline found. Last push 2022. |
| [scott-grimes/cheatingScanner](https://github.com/scott-grimes/cheatingScanner) | Parses an older Eduphoria CSV to compare pairs of students' correct/incorrect answers and plot similarities. Potential historical parsing reference. Last push 2017; GPL-3.0. Author cautions that the analysis is not rigorous evidence of cheating. |
| [maricia/Academic-Growth-Template-Campus-Exporter](https://github.com/maricia/Academic-Growth-Template-Campus-Exporter) | VBA exports campus-specific XLSX files from a Lead4ward workbook populated with Eduphoria data. Requires the separate workbook/template. Last push June 2026; MIT. |
| [bowserj/eduphoria-knowledge-graph](https://github.com/bowserj/eduphoria-knowledge-graph) | Searchable index of Eduphoria support documentation using SQLite, Qdrant, embeddings, and a graph. Useful reference grounding for agents; does not ingest student results. Last push August 2026. |
| [scott-grimes/bulkEduphoriaJournaling](https://github.com/scott-grimes/bulkEduphoriaJournaling) | Browser script writes the same journal note to multiple students. Outside the initial read-only results scope. Last push 2018. |
| [Sykezzz/Edu-Role-Importer](https://github.com/Sykezzz/Edu-Role-Importer) | Skyward employee assignment diffs to Eduphoria role-import CSVs. Staff access administration rather than assessment analysis. Last push August 2026; MIT. |
| [nishadtaylor1/qti-sdk](https://github.com/nishadtaylor1/qti-sdk) | PHP QTI authoring/parsing with an Aware target profile. Assessment content interchange rather than result extraction; MIT. |

Do not assume public repositories without an explicit license grant unrestricted code reuse. An independent implementation can use documented behavior without copying repository code.

## Proposed architecture

1. A trusted local ingestion process reads original exports and resolves student identities.
2. Report-specific adapters detect the layout, parse fields, and normalize results.
3. Validation checks completeness, uniqueness, scoring, and source consistency.
4. Private local storage retains original inputs, provenance, identity mappings, and normalized records.
5. An explicit export step emits only allowlisted pseudonymized fields and analysis tables into an agent-accessible directory or database.
6. Agents analyze those exports. Reconnecting findings to real students happens locally in the trusted process.

The identity boundary must be enforced through actual filesystem/tool access. A folder named `private` or an instruction to ignore it does not prevent an agent with unrestricted filesystem access from reading it. Do not ingest real records in an agent session that can access the originals and identity map; establish the local processing and restricted analysis environment first.

## Proposed storage model

Use SQLite initially unless sample files reveal a reason to choose another store. Keep private identity data in a separate database/file from the agent dataset. Proposed entities:

- `assessments`: internal assessment key, source assessment identifier when present, title, subject, administration date, version/form when known.
- `items`: internal item key, assessment key, source question label, item type, maximum points when supplied. Question number is local to an assessment and is not a global item identifier.
- `standards` and `item_standards`: standards metadata and a many-to-many item alignment table.
- `attempts`: student pseudonym, assessment key, attempt identifier, administration context, reported totals when available.
- `item_results`: attempt key, item key, response, earned points, correctness, and result status when available.
- `imports`: source hash, adapter/version, import time, settings/context, validation outcome. Original filenames and source locations stay private if they reveal identities.
- Private identity map: source-system/district namespace plus original student identifier mapped to a persistent random pseudonym.

Preserve distinctions between absent, not tested, omitted, unanswered, unscored, incorrect, and zero points when the source distinguishes them. Do not manufacture distinctions the export does not provide. Preserve identifiers as strings so leading zeros survive.

An item with multiple standards must not accidentally multiply scores during aggregation. Distinguish an observed response, correctness, and earned points; they are not interchangeable. Store reported aggregates separately from computed aggregates when needed for reconciliation.

## Pseudonymization requirements

- Generate persistent random aliases locally; use a private mapping to link successive reports.
- Do not use names, student ID fragments, or unsalted hashes of student IDs as aliases.
- Scope identity matching to the relevant source system/district. Do not auto-merge ambiguous records based on a name alone.
- Export an explicit allowlist of fields. Omit original names, student IDs, emails, birth dates, and unneeded identifying context.
- Free-text responses can contain names and other identities. Initially exclude them from agent exports unless a local redaction/review workflow has been verified.
- Review assessment titles, filenames, sheet names, teacher/class details, metadata, and unusually specific attributes for identifying information.
- Keep real source files, identity maps, secrets, logs containing identities, and generated private databases out of version control.
- Treat pseudonymized data as linkable student data, not guaranteed anonymous data. Export only the context needed for the analysis.
- Logs and parsing errors exposed to agents must not echo raw records.

## First implementation milestone

Start with one report family and complete it end to end before adding more adapters.

1. Identify the exact report name, export format, view configuration, and intended analyses. Determine whether the file contains individual results, aggregate statistics, responses, points, standards, or some subset.
2. Obtain a sanitized representative export or locally create a structurally faithful synthetic fixture. Sanitization must happen before an unrestricted agent can read real input. Keep headers, title rows, merged cells, sheet structure, and question labels intact.
3. Obtain a second fixture from the same family with a different question count. Cover partial credit, missing results, and multiple attempts when relevant to the source.
4. Document the observed schema and field meanings. Mark uncertain meanings explicitly.
5. Implement format detection and a single adapter. Parse by labels/structure rather than fixed absolute columns or fixed question counts.
6. Load normalized records and maintain provenance and a stable identity map through trusted local processing.
7. Produce a pseudonymized dataset and deterministic summary tables.
8. Verify the importer against both fixtures and reconcile with source counts/totals where the source provides comparable values.

A schema-only inspector is a useful first command: report sheet names, candidate header rows, column labels, question labels, and counts without displaying student rows. Run it locally and review its output before sharing, since even headers or sheet names can contain identifying information.

## Validation and acceptance criteria

- Different question counts require no code edits within the supported report family.
- Reordered columns and documented optional fields are handled where supported.
- Unknown layouts, missing required fields, ambiguous identities, and conflicting records cause a clear stop or quarantine outcome rather than guessed data.
- Re-importing the same file does not duplicate results. Changed exports of the same assessment have a defined update/conflict policy.
- Student, attempt, and item-result counts reconcile with the source where possible; expected exclusions are recorded.
- Point totals reconcile within an explicit rounding tolerance when the source provides enough information. Do not assume raw percent correct equals a weighted or scaled score.
- Synthetic fixtures cover leading-zero IDs, quoted multiline text when supported, missing scores, partial credit, and repeated question labels across different assessments.
- Repeated imports preserve aliases; new students receive new aliases; identity mappings never appear in agent exports.
- Tests include unique synthetic identity markers and verify their absence from exported datasets and public logs. This tests known leakage paths without claiming automatic detection of all identifying text.
- Stored provenance makes any reported statistic traceable to its source import through the trusted local process.

## Suggested project layout

```text
README.md
AGENTS.md                   # Development and agent-access rules
pyproject.toml
src/aware_results/
  adapters/
  schema.py
  validate.py
  storage.py
  identity.py
  export.py
  summarize.py
  cli.py
tests/fixtures/             # Synthetic/sanitized only
docs/report-schemas/
docs/privacy-boundary.md
```

Keep private input/storage outside the agent-visible project workspace. An `agent_exports` area can contain approved pseudonymized outputs. Do not add private paths to agent configuration or expose them through tools.

## Open choices to resolve from samples

- Which report family comes first, and can it be exported as CSV/XLSX?
- Can the teacher save a reusable view with the fields needed for subsequent exports?
- Are item-level points, maximum points, standards, attempt identifiers, and assessment identifiers available?
- Is the immediate goal standards performance, question analysis, growth across tests, instructional grouping, written-response analysis, or a combination?
- Which local process will handle private records, and what access restrictions will enforce the agent boundary?

Do not block preliminary scaffolding on every choice. Start with synthetic data and the smallest verified report adapter. Do not build web scraping, district login automation, write-back, an agent server, or a dashboard unless later requested or justified by the confirmed workflow.

## Starting instruction for the next project chat

> Read PROJECT_HANDOFF.md. Help implement the local Eduphoria Aware results pipeline described here. Begin by reviewing the available sanitized/synthetic sample files and documenting the first report schema. If no samples exist, scaffold the project and define synthetic fixtures clearly labeled as provisional; do not claim compatibility with real Aware exports. Establish the private local ingestion versus restricted agent analysis boundary before processing real student records. Build one importer end to end, with dynamic question handling, validated SQLite storage, stable pseudonyms, and an allowlisted agent export. Keep calculations deterministic and validate source counts and totals where possible.
