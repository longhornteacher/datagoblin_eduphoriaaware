# Student learning standards (`slsb`)

Method ID: `student_learning_standards`. Contract version: `1.3.0`. Adapter: `0.3.0`, verified with independent synthetic XLSX inputs only. Real-record compatibility remains untested.

## Purpose and export checklist

This method provides each student's reported performance on each assessed standard plus overall reported scores. It supports within-assessment standards grouping and individual summaries. It cannot reconstruct individual question responses, points, or exact per-standard denominators.

Configure a student-row Aware view with `Student Name`, `Local ID`, `All Learning Standards`, `Raw Score`, `Scale Score`, `Percent Score`, and the three Texas achievement indicators below. The supplied views also include `Special Ed Indicator`, `Emergent Bilingual`, and `Ethnicity`. Those demographic fields are recorded as observed optional fields and excluded from default exports. Their omission has not yet been tested in a real export. Export XLSX. Record the exact saved-view name, click path, scope and filters privately when confirmed.

## Verified layout

| Component | Grade 5 / 2025 | Grade 6 / 2026 |
| --- | --- | --- |
| Identity/context headers | A2:E3, vertically merged per column | Same |
| Assessment title | F1:AN1 merged | F1:AR1 merged |
| Standards group | F2:AH2 merged | F2:AL2 merged |
| Dynamic standard headers | F3:AH3, 29 labels | F3:AL3, 33 labels |
| Overall score / flags | AI2:AN3, vertically merged per column | AM2:AR3, vertically merged per column |
| First candidate data row | 4 | 4 |
| Extra formatted but empty column | AO | AS |

Coordinates are evidence, not parser constants. Both examples have three header rows, one worksheet, no formulas, and no hidden rows/columns. Blank formatting extends the worksheet dimension; do not treat it as an unknown populated column. A1 contains non-schema context and must not be exported.

## Field meanings and mappings

| Source | Normalized target | Encoding / meaning | Privacy |
| --- | --- | --- | --- |
| Student Name | private identity context | Text, not a join key | Private only |
| Local ID | private identity map | Opaque text; namespace required | Replace with stable random alias |
| Special Ed Indicator | private optional attribute | Text; vocabulary unverified | Exclude |
| Emergent Bilingual | private optional attribute | Text; vocabulary unverified | Exclude |
| Ethnicity | private optional attribute | Text; vocabulary unverified | Exclude |
| All Learning Standards -> each row-3 header | `student_standard_results` | Numeric, `0%` format, ratio `[0,1]`; displayed rounded percentage, denominator unknown | Allowlisted ratio by alias |
| Raw Score | `attempt_summaries.reported_raw_score` | Numeric `General`; units/max/weighting unverified | Allowlisted reported metric |
| Scale Score | `attempt_summaries.reported_scale_score` | Numeric `General`; scale definition unverified | Allowlisted reported metric |
| Percent Score | `attempt_summaries.reported_percent_ratio` | Numeric `0.00%` fraction; scoring denominator unverified | Allowlisted reported metric |
| Approaches Grade Level (TX) | `attempt_summaries.approaches_flag` | Text indicator; vocabulary unverified | Export only after vocabulary verification |
| Meets Grade Level (TX) | `attempt_summaries.meets_flag` | Text indicator; vocabulary unverified | Export only after vocabulary verification |
| Masters Grade Level (TX) | `attempt_summaries.masters_flag` | Text indicator; vocabulary unverified | Export only after vocabulary verification |

The supplied standard headers include a literal `[R]` or `[S]` tag. Preserve it separately from canonical code. The cross-subject extension also permits untagged standard codes; absence stays null. No source assessment ID, attempt ID, per-student administration date, item response, item maximum, or denominator field is present among the observed headers.

Standards use the shared [standards policy](../standards.json) and framework-scoped catalog. For example `5.2(B.v) [S]` becomes `5.2.B.v`, with the original label/tag retained privately. Results reference the same catalog entry as a group-item report's equivalent dotted code within the same namespace/framework. Grade and all suffixes remain part of the code; descriptions stay null when unavailable. Packets include an opaque `standards_scope_key` and sort standards by numeric parts. See [storage details](../../docs/standards.md).

The standards layer also accepts K, grades 1–12 and explicitly registered course prefixes, with optional R/S tags. Course standards retain a nullable numeric grade and never infer students' grades. These broader forms and subject scopes are synthetic-tested; source files from other subjects/levels may need a new layout variant if required score/header fields differ.

## Parse/clean recipe

1. Inspect each worksheet locally. Require exactly one matching sheet in v1 and no additional sheets. Detect the known identity/score header labels after header whitespace normalization; locate one `All Learning Standards` merge. Do not choose a sheet by filename or name.
2. Identify the header band and resolve top-left labels only inside actual header merges. Every required label must occur exactly once. Optional demographic fields may be absent by proposed policy; verify before claiming that variant works.
3. Read the labels immediately below the standards group across its merge width. Parse every nonblank label with the contract regex; reject blanks inside the group, duplicate canonical codes and unknown tags. The group width determines standard count. Other top-level columns are matched by label, so the score block may move.
4. Data starts below the complete header band. Ignore wholly blank rows and columns, validate partial rows, and reject unknown populated columns, totals, repeated header rows, formula cells, and merged student-data cells. A blank ID cannot be replaced with the row's name. Duplicate IDs in the same snapshot are ambiguous; stop rather than invent multiple attempts.
5. In the trusted process, resolve the private namespace/ID to a persistent random alias, produce one attempt-summary row per valid student row, and unpivot one standard-result row for every discovered standard, including explicit null/status for blank results.
6. Preserve source precision, header/tag and source-cell provenance privately. Validate numeric types/ranges before a transaction commits. An unknown flag vocabulary quarantines the flag field for review and blocks exports requesting that field, while verified literal numeric metrics may still be staged privately. Never silently map arbitrary text to true/false.
7. Export the contract's two table-specific field allowlists after local validation and review. Demographics, private identity fields and raw flags are excluded.

## Validation and tabulation

For `N` accepted student rows and `S` discovered standards, require exactly `N` summaries and `N*S` standard-result records (including missing records), with unique keys and stable aliases. These are implemented/tested synthetic invariants, not measured private source counts. Ensure exactly one canonical standard per header and no grade stripping. Check percent ranges and each metric's blank status. Do not require standard percentages to sum to an overall percentage or raw score: points and denominators are unavailable.

The compact agent packet combines scores and standard results into a `students` matrix and includes the specified unweighted `standard_summary`. Null/status meanings and provenance keys are defined once at packet scope. It excludes all unverified flags. See [pipeline commands and export format](../../docs/pipeline.md).

An equal-student mean of available reported ratios can support within-assessment grouping, with observed/missing denominators. It is not a pooled correctness rate. Any instructional grouping cutoff is an explicit analysis parameter, not a source mastery threshold. Achievement-rate tabulation waits for verified flag meanings. See [shared rules](../common.md) for storage, snapshots and longitudinal limits.

## Open source questions

- What are the exact view name, export steps and roster/filter semantics?
- Are these standard percentages based on points, fully correct items, another denominator, and how is partial credit handled?
- What do blanks and each achievement-flag token mean? Are the three flags cumulative? Can they be missing independently?
- What are the raw-score maximum, weighting and scaled-score definition? Is there a separately available denominator?
- Can one export contain retests/forms or multiple actual attempts, and can IDs/form/date fields be added?
- Which standards framework/version and meanings of `[R]`/`[S]` apply?

Until resolved, preserve reported metrics and uncertainty; do not infer answers from display formatting or filenames.
