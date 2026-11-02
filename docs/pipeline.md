# Local report processing and compact agent packets

Version 0.3.0 implements both documented single-sheet XLSX report families and a shared, subject/grade/course-scoped TEKS catalog. Development and verification use independently constructed synthetic files, including the observed 29/33-standard widths and 41/45-question heights plus cross-subject K–12/course patterns. **Real-record import compatibility has not been tested.** No source workbooks or private sync data were ingested during implementation.

## Commands for the trusted local process

Install dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

Configure `DATAGOBLIN_SYNC_DIR` or your ignored local TOML as described in [sync-folder.md](sync-folder.md). Set `DATAGOBLIN_WORK_DIR` to a dedicated nonsynced private directory outside the repository and the sync root. Use a local location with appropriate filesystem permissions. The scripts reject path overlap but do not create Windows ACLs or an agent sandbox. Run real-record commands yourself in a trusted local session; the current unrestricted agent development session uses synthetic data only.

```powershell
$env:DATAGOBLIN_WORK_DIR = Join-Path $env:LOCALAPPDATA 'DataGoblin\work'
python scripts/process_reports.py init-store
```

Initialization is explicit and refuses to replace an existing store. The working directory contains `data.sqlite3`, a separate `identity.sqlite3`, and an immutable `originals/` archive. Never delete/recreate a missing identity map to get past an error: that would break historical aliases. A missing map or mismatched generation stops processing.

Existing format-1/2 stores need `python scripts/process_reports.py migrate-store` before imports/exports. This creates paired local backups and upgrades to format 3 without changing aliases, snapshot keys or scores. Existing format-2 catalog/scope keys and descriptions are preserved. See [standards storage and migration](standards.md).

Create a private JSON context file with these four required fields. Optional `subject` and `framework_version` go together; named course prefixes additionally require an explicit `course_code`. The strings below illustrate required decisions; replace them with privately registered references. Do not copy this illustrative context across unrelated assessments or populations.

```json
{
  "source_namespace": "district-and-source-system",
  "assessment_ref": "administration-grade-subject-form-reference",
  "population_ref": "explicit-filter-and-roster-snapshot-reference",
  "framework_ref": "standards-framework-and-version-reference"
}
```

References are opaque to the exporter and never appear in an agent packet. They must identify the assessment/form and population deliberately; titles, filename dates, row order and group-label text are never used to invent those relationships. Use the same source namespace across reports only when Local IDs identify the same students. A new population reference is needed when the meaning of the roster/filter snapshot changes.

The framework reference must distinguish the subject and applicable adoption/version; it is not just the text `TEKS`. Course standards use course-specific scopes with explicit subject/version/course registration. Standards are deduplicated by namespace/framework plus canonical code. The packet reveals only an opaque `standards_scope_key` for this registration, not private subject/version/course values. Descriptions remain null when unavailable. See [cross-subject registration examples](standards.md).

Import one report:

```powershell
python scripts/process_reports.py import --input 'C:\private\report.xlsx' --method student_learning_standards --context 'C:\private\context.json'
# For the group/question report use: --method group_item_analysis
```

Success prints only a status and opaque `snapshot_key`. Source paths/values are not echoed on failure; errors are fixed codes. Invalid data stops before result/identity commits. A failed transaction can leave an unreferenced archived original privately; it cannot expose a partially accepted snapshot. Unsupported files are left where they are, rather than moved automatically to quarantine.

To create a reviewable agent packet for one explicitly selected snapshot:

```powershell
python scripts/process_reports.py export --snapshot 'r_REPLACE_WITH_RETURNED_KEY' --out 'C:\analysis\selected-packet'
```

The destination must be new and outside both private roots. Export stages a complete pair of files before publishing the directory. It never overwrites a previous packet. Local review of the output's scope, small groups, curriculum disclosure and longitudinal linkage precedes granting agents access. No automatic release or access-control configuration occurs.

For private durable sync storage:

```powershell
python scripts/sync_folder.py --init
python scripts/process_reports.py publish
```

Publication holds the cooperating writer lock, closes both database connections, rejects database sidecars, and copies closed database generations plus archived originals. A private manifest, written last, records matching store/generation IDs and hashes. There is no live SQLite database inside sync storage. Partial/conflicting publications stop; a consumer must verify the complete manifest and every referenced hash, rather than treat a filename's presence as readiness. Confirm cloud sync completion locally before changing devices. Automated restore/conflict merging is not implemented. Preserve the matching identity/normalized pair and originals together; never mix generations.

## Implemented behavior

- Header-based parsing discovers variable standard columns/question rows, optional demographic columns, reordered fields, and blank formatted trailing cells. Header search is limited to the first 20 rows. The source must have one visible worksheet and supported merge topology. Hidden rows/columns, table/filter layouts, unknown populated fields, formulas/errors in mapped data, unsupported encodings, duplicate keys and multi-group reports stop processing.
- Literal Excel ratios remain fractions with source precision; zero stays zero and blank stays null. Text percentages, booleans as numbers and numeric Local IDs are rejected. Known percentage formats are checked against the method contract. Original workbook bytes remain private for exact source-literal recovery.
- Each namespace/Local ID receives a persistent, random 96-bit alias with a uniqueness check. Names do not determine aliases. A changed name for an existing key stops for identity review. The original ID/name is retained only in the identity database and original archive; normalized result rows use aliases. Raw flags remain private and are not interpreted.
- Both attached databases use rollback-journal transactions, and both generations advance together. An exclusive cooperating writer lock prevents overlapping imports/exports/publications. A stale lock after a process crash must be investigated locally; it is never automatically stolen. These are application coordination measures, not cross-device synchronization locks.
- Byte-identical reimports with identical context are no-ops. Reusing the same bytes under conflicting context stops. Changed exports create immutable snapshots; previous results remain accessible. Actual multiple attempts/retests are not inferred. There is no implicit latest-snapshot selection.
- Numerical results have natural-key constraints and private source-cell references. To trace an exported fact, resolve its opaque provenance/snapshot key and its alias/question plus field/standard through `source_cells` and the archived original. Framework metadata is private registration context; it is not a cross-grade equivalence claim.
- Both reports normalize TEKS to `LEVEL_OR_COURSE.NUMBER.EXPECTATION[.subexpectation]`, retaining K, numeric grades or explicitly registered named prefixes and the full suffix. R/S tags are optional, and absent tags remain null. The shared catalog stores code components and exact original labels separately; result key/code foreign keys must agree. Courses have no inferred numeric student grade. This is structural normalization, not an authoritative curriculum crosswalk. Extended source forms and other-subject patterns are synthetic-tested, not newly observed vendor layouts.

## Agent packet format `datagoblin.agent.v1`

Each packet contains `data.json` and `README.md`. The JSON uses explicit column names once and positional arrays for rows. Snapshot/assessment/provenance and standards-scope keys are stored once per packet instead of repeated in every record. Standard codes have consistent case/spelling, and the opaque scope key prevents short labels from different subjects/versions being treated as one identity. There is no lossy rounding, binary dependency, compression step or custom text parser. Ordinary JSON tools can read it.

| Table | Columns | Meaning |
| --- | --- | --- |
| `students` | `student_alias`, `reported_raw_score`, `reported_scale_score`, `reported_percent_ratio`, variable `std:CODE` columns | One row per student, all standard aggregates in a matrix |
| `standard_summary` | `standard_code`, `mean_reported_ratio`, `n_observed`, `n_missing` | Derived equal-student means across available standard ratios; no inferred item denominator |
| `group_items` | `question_label`, `standard_code`, `reported_correct_ratio` | One row per group/question; no individual answers or exact Total Students values |

The first two tables appear only for the student method; `group_items` appears only for the group method. They are never joined to manufacture student-item responses. Standard labels/codes are validated against the documented notation before export. Alias/key fields and numerical values are checked again during export. The exporter uses explicit SQL projections, never serialization of raw database rows or a denylist.

`null` encodes exactly `source_blank`, and every non-null literal numeric metric encodes `reported`. The guide defines this once rather than repeating status strings in thousands of cells. The `std:` prefix identifies standard columns without a separate repeated label dictionary. Unverified achievement flags, source labels/tags, identity fields, demographics, raw titles, filenames, worksheet names, private context and original repeated population counts are excluded.

This is a compact representation of a projection of the contract's allowlisted fields, plus its specified derived means. The packet envelope supplies shared provenance/snapshot keys; alias+standard or question identifies the source fact. Every row's meaning remains explicit despite avoiding repeated field names and statuses. Derived sample counts describe the exported student matrix; they do not assert equality to the other report's population count.

## Querying a reviewed packet efficiently

The standard-library-only reader operates exclusively on a packet the trusted user has reviewed. Copy just `scripts/read_packet.py` into a restricted analysis environment if needed; it has no dependency on private configuration, SQLite, XLSX or original reports.

```powershell
# Describe tables/columns and row counts without dumping values.
python scripts/read_packet.py --packet 'C:\analysis\selected-packet'
# Ask for a summary first.
python scripts/read_packet.py --packet 'C:\analysis\selected-packet' --table standard_summary
# Project just one standard, with up to 20 rows by default.
python scripts/read_packet.py --packet 'C:\analysis\selected-packet' --table students --standard '7.1.A.i'
# Filter an alias or page through results with --student, --offset and --limit.
```

The reader emits at most 1,000 rows per request and returns `next_offset` for pagination. Matrices reduce repeated keys; selective queries reduce unnecessary context further. Tests compare byte size with the equivalent wide JSON-object table, not model-token counts. There is no claim that every tokenizer or every dataset has an optimal representation.

## Verification and remaining work

Run `python scripts/check_templates.py` and `python -m unittest discover -s tests`. Synthetic tests cover the known shapes, different sizes/order, leading-zero IDs, partial ratios, zero versus blank, identity stability/namespaces, transaction rollback, duplicate/changed imports, malformed inputs, quiet errors, known identity-marker absence in packet files/logs, packet pagination, and closed snapshot publication. These tests do not prove universal identity redaction or enforce an operating-system access boundary.

Real-record acceptance remains a trusted local activity. Source achievement vocabularies, score denominators, roster/filter semantics, multi-alignment/multi-group variants and comparable longitudinal measures remain unresolved. Automated restore, a quarantine review UI, watcher, and verified flag exports are future work.
