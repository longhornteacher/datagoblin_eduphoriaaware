# Shared processing contract

This is the shared processing specification. Adapter 0.3.0 implements the subset documented in [pipeline.md](../docs/pipeline.md), verified using synthetic XLSX data only. The richer table model and unresolved semantics below remain design guidance. Only structural facts in `observations/` have been verified against the supplied workbooks.

## Stages and responsibility

| Stage | Deterministic behavior | Boundary |
| --- | --- | --- |
| Inspect | Identify XLSX/sheet/header structure, merges and known fields without displaying records | Local schema inspection; metadata still needs review |
| Register | Archive immutable original, hash bytes with SHA-256, record private import context and contract version | Trusted local process |
| Parse | Match one supported method, resolve merged headers, discover dynamic standards or questions | Trusted local process |
| Clean | Preserve source value and source cell privately; derive typed normalized value using documented rules | Trusted local process |
| Validate | Check keys, units, completeness and semantics; reject or quarantine unknown/conflicting data | Trusted local process |
| Store | Transactionally persist validated records and provenance; retain earlier snapshots | Trusted local process |
| Tabulate | Use explicit grains, populations and denominators; publish missingness counts | Trusted local process |
| Pseudonymize/export | Resolve stable random aliases; select an explicit field allowlist; exclude identifying text | Trusted local process |
| Analyze | Read only reviewed, allowlisted outputs through tools and filesystem restrictions | Restricted agent environment |

A directory name or `.gitignore` cannot create the boundary. The current unrestricted development session is for specifications and synthetic fixtures. Real-record processing must run in a separate trusted local process; later agents must lack access to originals and identity maps.

Durable private storage is the per-user sync folder specified in [docs/sync-folder.md](../docs/sync-folder.md). Resolve it from `DATAGOBLIN_SYNC_DIR` or local ignored configuration, never from report templates. Its `inbox`, `originals`, `identity`, `normalized`, `manifests`, `quarantine`, and `logs` directories are all private. Active processing uses `DATAGOBLIN_WORK_DIR` or `--work-dir` outside the sync folder. The implemented publisher copies closed immutable database snapshots and matching identity-map generations; the initializer itself still creates folders only.

## Cleaning and units

- Trim surrounding whitespace on recognized headers, normalize line endings, and collapse repeated whitespace for header matching. Match the resulting known label exactly, with case preserved. Do not apply this rule destructively to identifiers, free text, or unknown labels. Preserve original labels privately.
- Resolve merged **headers** from their top-left cells and constrain that inheritance to the actual merge rectangle. Do not blanket forward-fill student records or numeric measures. The group label in the item report is a separate, bounded merge rule.
- Ignore wholly empty trailing columns, even if Excel includes them in its dimension. A populated unknown column is a schema change, not a column to drop. Ignore wholly blank rows; a partial row must be validated. Detect repeated headers/totals separately and quarantine them unless a later contract documents them.
- `ratio_0_1`: finite JSON/SQL numeric value in `[0, 1]`, or null with `source_blank`. An Excel numeric value formatted `0%` or `0.00%` is already a fraction. Synthetic example: `0.625` displays as `63%` under `0%`, but store `0.625`, not `0.63` or `0.00625`. Multiply by 100 only for presentation. Preserve source precision; do not round to displayed precision.
- Numeric `0`, `false`, empty cell, whitespace text, string `"0"`, Excel errors, and formula-without-cache are distinct. No blanket `fillna(0)` or string-to-number coercion. Text percentages, new sentinels, and unexpected data types need a documented variant before acceptance.
- Reject NaN/infinity and Excel errors. Do not execute formulas from a source workbook. Version 1 accepts literal values only; a formula encountered in a mapped field quarantines the import even if it has a cached result.
- Local IDs are opaque text scoped to source system/district. Preserve leading zeros. Numeric ID cells need a separately verified recovery policy; converting a float or guessing zero padding is forbidden. Names alone cannot resolve identity.
- Preserve raw score, scaled score, overall percent, standard percent, and item correctness percent as distinct metrics. They are not interchangeable. No question count or maximum points can be inferred reliably from a raw score.
- Missing metric status is `source_blank`; its meaning remains unknown. Do not label it absent, not-tested, incorrect, omitted, or unscored without evidence. Nonblank literal metrics use `reported`. Preserve separately verified status encodings in a later version.

## Standards and assessment identity

For the observed notation only, parse student-standard headers using:

```text
^(?<grade>[0-9]+)\.(?<number>[0-9]+)\((?<expectation>[A-Z](?:\.[A-Za-z0-9]+)*)\) \[(?<tag>R|S)\]$
```

Canonical code: `grade.number.EXPECTATION[.subexpectation]`, e.g. `6.8(D.iii) [S]` becomes `6.8.D.iii`, retaining the original header and tag separately. Both report methods use the shared normalizer and [standards.json](standards.json). Numeric components are unpadded, the expectation letter is uppercase and the complete suffix is lowercase. Preserve every suffix component; the original source case remains private. `R`/`S` likely denote readiness/supporting, but their expansion is unconfirmed; store the literal source tag until verified. Unknown notation stops normalization. Never collapse `5.8.C` and `6.8.C` into one standard. Available descriptions have a reserved nullable catalog field; the known exports do not supply them, so no text is invented or fetched.

The synthetically tested cross-subject extension generalizes the prefix to `LEVEL_OR_COURSE`: K, numeric grades and explicitly registered course prefixes. It permits dotted/parenthetical/compact codes and optional R/S tags. The observed regex above documents the original files only; current contracts contain the broader shared grammar. Course prefixes require private subject/version/course registration; numeric grade is null for K/course records, and absent tags remain null. No student grade or course alias is guessed. See [standards.md](../docs/standards.md).

Namespace standards by `(source_namespace, framework_ref)`, with the framework reference explicitly distinguishing subject and applicable version/adoption. The implemented catalog gives that scope an opaque key and deduplicates by scope plus canonical code. A label alone does not prove curriculum equivalence across revisions. Assign internal assessment keys using a private registry of source namespace, administration, grade, subject and verified form/version. Titles/year/filenames are matching hints, not guaranteed unique keys. Month/year from an assessment title is not a student's exact test date. Group keys represent privately recorded filter/scope snapshots, not an assumed stable class membership. See [standards.md](../docs/standards.md) for migration and scope rules.

## Proposed SQLite tables

This extends the handoff model because the two reports have no student-item results to populate. Types: keys and codes are `TEXT`, counts `INTEGER`, reported measures `REAL` with source literal/precision retained privately. Rates have `[0,1]` checks. Missing status is represented explicitly by null plus the packet's shared `source_blank` rule; unverified flags remain private. The implementation combines snapshot metadata into `imports` and stores item alignments directly in `group_item_results`; separate item entities remain proposed. `standards_frameworks`, `standards`, and `standard_source_labels` are implemented in database format 3, with foreign keys from both result tables and explicit level/course metadata. Formats 1/2 require a backed-up migration. Originals retain exact source bytes, and `source_cells` maps normalized facts back to them.

| Table | Grain / key | Main fields and constraints |
| --- | --- | --- |
| `imports` | `import_id` | private source SHA-256, method/version, parser version, context digest, import time, validation state |
| `assessments` | `assessment_key` | namespace, registered administration/form, grade, subject; privately reviewed title/date metadata |
| `report_populations` | `population_key` | opaque key, private filter/scope definition and roster snapshot, optional verified membership |
| `assessment_snapshots` | `snapshot_key` | import, assessment, population, method; changed export creates a new snapshot |
| `attempt_summaries` | `(snapshot_key, student_alias)` | reported raw/scale/percent scores and three separate threshold flags; no inferred actual attempt ID |
| `student_standard_results` | `(snapshot_key, student_alias, standard_key)` | reported ratio/status, original standard header/tag, private source cell |
| `standards` | `(framework_key, canonical_code)` | exact canonical code; framework/version unresolved until registered |
| `standards_frameworks` | `(source_namespace, framework_ref)` | opaque framework key; caller registers subject/version explicitly |
| `standard_source_labels` | `(snapshot_key, source_kind, source_key)` | catalog standard key, exact label and separate source tag |
| `items` | `(assessment_key, question_label)` | question label local to assessment/form; no inferred max points/type |
| `item_standards` | `(assessment_key, question_label, standard_key)` | distinct alignment; never multiply a fact by joining all alignments |
| `group_item_results` | `(snapshot_key, question_label)` | repeated reported population count and reported correctness ratio/status |
| `source_cells` | private provenance reference | table/record/field -> import, worksheet ordinal and cell; excluded from agent exports |
| separate private identity map | `(source_namespace, local_id)` | persistent random `student_alias`, locally resolved conflicts; unavailable to agents |

The snapshot key scopes records to a particular export context. Two methods from the same administration are separate snapshots. In v1, if a question repeats within a group, quarantine rather than assume the rate is additive or split by standard. A future multi-alignment variant may attach several alignments to one item fact only after verifying equal fact values and intended semantics.

Reimport policy: same source hash + same method/version + same private context digest is a no-op. Same bytes with conflicting context are a registration conflict. Changed bytes for an existing registered assessment/population/method create a new immutable snapshot. Do not append them as another actual attempt or silently overwrite the prior one. An explicit local selection chooses the current snapshot for tabulation. Parser-version reprocessing creates a recorded processing revision, never an in-place reinterpretation without provenance. Duplicate/conflicting natural keys abort the transaction. Identity ambiguities are resolved before any export.

## Pseudonymization and agent export

Generate aliases with a cryptographically secure random generator in the trusted local process, for example a random UUID. Persist one alias per private namespace/ID key and enforce uniqueness. Do not derive aliases from names, ID suffixes, or unkeyed hashes. Reuse aliases across administrations only after local identity matching, not by report row order or names.

Exports are explicit projections, not normalized tables with a denylist applied. Contracts enumerate each method's allowed output fields. Agent format `datagoblin.agent.v1` projects a subset, lifting shared keys/status meanings to packet scope and pivoting standard results into columns. It also includes the specified derived standard means with observed/missing row counts. Flags remain excluded. Provenance references supplied to agents are random opaque export references; keep source hashes, private paths, row/cell addresses, raw titles and original population labels private. Agent output contains no original IDs/names, demographics, free-text responses, filenames, worksheet names, or unreviewed context. Grade/year/subject and source-reported population sizes require purpose-specific review before adding to an export profile; they are not default v1 exports.

Packets include one opaque `standards_scope_key`, alongside canonical codes, so matching labels from different namespaces/subjects/versions can be kept distinct without disclosing private framework references. Standard columns/summaries use numbered and Roman-part ordering. The scope/code pair establishes catalog identity only, not comparable scoring or a common cohort.

`student_standard_results` exports carry only alias, opaque assessment/snapshot keys, canonical standard code, ratio/status and opaque provenance reference. Student summary exports carry only alias, opaque assessment/snapshot keys, reported scores, validated threshold flags, and opaque provenance reference. Group-item exports carry only opaque assessment/population/snapshot keys, question label, canonical alignment code, ratio/status and opaque provenance reference. Exact student counts stay private by default. Canonical standard codes themselves expose grade and curriculum context: review that disclosure for the intended analysis. Do not describe these datasets as anonymous.

Small groups and longitudinal results can remain identifying. A trusted person reviews scope and whether counts/context require suppression before release. Any chosen minimum-group rule is a recorded export-policy setting, not a guessed legal threshold. Free text and unknown columns are excluded by default. JSON exports must encode true nulls and finite numbers; a later CSV writer must also address spreadsheet formula injection for any permitted text.

## Tabulation, reconciliation, and time

- Report an equal-student mean of available student-standard ratios with `n_observed` and `n_missing`. Its label must say that it is an unweighted mean of reported percentages. Do not call it a pooled percent correct or infer item denominators. Keep reported values and derived statistics separate.
- Threshold counts require a verified flag vocabulary. Preserve the three achievement flags independently; do not coerce three cumulative indicators into one exclusive category. For a verified yes/no variant, use count-yes divided by nonmissing validated flags and publish the denominator.
- Preserve group item rates as reported. Do not compute exact correct counts by multiplying rate by `Total Students`, sum the repeated student counts, average across different groups, or combine item rates into a weighted test score without verified denominators/weights and nonoverlapping populations.
- An item-to-standard join supplies alignment, not student-item performance. No synthetic student answers, correctness, earned points or item attempts may be generated from these reports.
- Within one assessment/form/population, compare standard-label sets between methods; the supplied examples match after canonicalization. This checks alignment coverage only, not scoring equivalence or identity/roster matching.
- To compare group counts with student rows, first verify population filters, roster timing, attempts and missing-test policy. The same file nickname does not establish equal populations. Only then reconcile counts exactly. Actual counts were not compared in this specification work.
- Grade 5 (2025) and grade 6 (2026) are separate assessments with different standards and question sets. Do not join by question number, strip grade, infer the same cohort, or subtract scaled scores as a growth measure. A longitudinal analysis needs locally resolved student aliases, explicit cohort membership, missingness/attrition counts, and a separately justified comparable measure/crosswalk.
- Reconcile counts/keys exactly; preserve source numeric precision. Header percent display rounding is presentation only, so do not use its rounding width as an import tolerance. Any future reconciliation of independently computed scores requires verified denominators plus a separately recorded tolerance in those units; v1 cannot perform that reconciliation.

## Acceptance gate for future importers

Require synthetic XLSX fixtures for both observed layouts plus a different number of standards/questions, changed column order, merged group bounds, blank trailing columns, leading-zero IDs, duplicate IDs/questions/standards, partial rows, percent encoding changes, errors/formulas, unknown headers/sheets, and changed-export conflicts. Test stable aliases, no duplicate reimports, transaction rollback, and absence of unique synthetic identity markers in all exported datasets and public logs. Testing known markers does not prove universal redaction. Run real-record acceptance only in the trusted local environment after the boundary exists.
