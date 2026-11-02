# Report methods

This directory is the durable record for interpreting and processing each supported report method. Version 1.0.0 recorded the four local workbook layouts on **2026-11-02**. Contracts are now at 1.3.0 with adapter 0.3.0, cross-subject grade/course standards, and a compact agent format; observed source meanings remain unchanged. Inputs were initially supplied in `report examples/` (`recentexamples/` in the request) and have now been relocated into private sync storage. No original report directory remains in this workspace or belongs in Git.

| Method | Source nickname | Source grain | Evidence | Specification |
| --- | --- | --- | --- | --- |
| Student learning standards | `slsb` | One student report row, with repeated standard-percentage columns | Grade 5 / 2025: 29 standards; grade 6 / 2026: 33 standards | [Method](student-learning-standards/README.md), [contract](student-learning-standards/contract.json) |
| Group item analysis | `itemperc` | One group/question/alignment row, with a reported correctness percentage | Grade 5 / 2025: 41 question rows; grade 6 / 2026: 45 question rows | [Method](group-item-analysis/README.md), [contract](group-item-analysis/contract.json) |

The nicknames come from the supplied filenames. Full UI report/view names and export-click paths have **not** been confirmed. Both files appear to be configured data views. Do not turn a filename abbreviation into an asserted Eduphoria product feature.

## What is established

- Both methods are XLSX with a single worksheet in each supplied example. Headers are merged and multirow; they are not ordinary row-1 CSV tables.
- Standard columns and question rows vary with the assessment. Never hardcode the observed counts, letters, years, grades, row counts, filenames, or worksheet names.
- `slsb` contains standard percentages and reported overall scores, not each student's answer to each question.
- `itemperc` contains group percentages, a repeated student-count field, and question-to-standard labels, not student identities or individual answers.
- Header standard notation differs between methods. `5.2(B.v) [S]` corresponds structurally to `5.2.B.v`. Grade remains part of the key.
- [standards.json](standards.json) defines shared TEKS normalization: unpadded numeric parts, uppercase expectation, lowercase full suffix. Original labels/tags stay private; catalog identity is scoped to the registered namespace/framework reference. See [standards storage and migration](../docs/standards.md).
- The standards layer supports `K`, numbered grades, and explicit named course prefixes across subject scopes. R/S tags are optional. Cross-subject/course and compact/untagged input extensions are synthetic-tested only; they do not establish real XLSX-layout compatibility outside the four supplied examples.
- Percentage cells use Excel percent formats. Store their underlying fraction as a ratio; formatting is not an instruction to divide a second time.

## Evidence and limits

[observations/](observations/) contains manually reviewed, structure-only snapshots. They preserve headers, standard labels, observed coordinates, merge topology, and relevant number formats. They intentionally omit source paths, sheet names, titles, group labels, student counts, student rows, and scores. A snapshot ID is a documentation key, not an assessment ID or a hash of the original file.

Evidence metadata distinguishes subject, framework scope/version, report level and course; numeric grade can be null for K/course records. Version is null for the supplied ELAR examples because it was not verified. Optional `comparison_group` identifiers mark intentionally paired layout evidence. Coverage is compared only within the same subject/scope/level/year/group, and a missing counterpart is not invented. These are reviewed structural references, not private import-context values.

These observations establish **layout**, not scoring semantics or production compatibility. Source student values were not retained or analyzed. Adapters, private storage, alias generation and exports are implemented and tested with independent synthetic XLSX inputs. See [the adapter verification record](observations/ADAPTER_VALIDATION.md) and [pipeline documentation](../docs/pipeline.md). The original synthetic JSON layout cases in [tests/fixtures/](../tests/fixtures/) remain specification-only checks; they are separate from the new generated XLSX parser tests.

Read [common.md](common.md) for shared cleaning, storage, pseudonymization, comparison, validation, and provenance rules. Each JSON contract conforms to [report-contract.schema.json](report-contract.schema.json). Schema validation checks the contract's shape; `scripts/check_templates.py` also checks observations against its required headers and standard-label rules. JSON Schema alone does not execute a processing pipeline.

Private storage location is a per-user setting documented in [sync-folder.md](../docs/sync-folder.md), not a report-method field. No personal path belongs in these contracts or observations.

## Recreating the report methods

Until the exact saved-view names and click paths are recorded, use the field checklist in each method's README, export XLSX, and inspect the resulting headers locally. Record privately: assessment selection, population filters, role/scope, current versus historical roster behavior, administration/form, export time, and view settings. An apparently matching title does not establish a matching population.

Do not flatten merges or edit originals before hashing and archiving them in the trusted local process. Keep that private manifest separate from these public structural records. A CSV or PDF export is a new format variant requiring its own evidence and adapter rules.

## Versioning and next work

- Keep `method_id` stable. Increment contract major version for a changed grain, field meaning, unit, identity policy, or incompatible layout; minor version for a compatible documented extension; patch for a clarification with unchanged behavior.
- Add a new structure-only observation for a newly verified layout. Review it before committing. Historical observations remain attached to the version that documented them.
- A new header, missing required header, duplicate label, new percent encoding, unexpected sheet, or new merge pattern requires review. Do not silently broaden detection.
- Both methods now have adapters tested on independently generated synthetic XLSX patterns. The first supports student-level standards work; the second adds item alignment and group context without fabricating student-item results. Contract `status` continues to describe source evidence; `implementation` describes the adapter's synthetic verification level.
- Before production use, resolve source questions needed for the intended analysis and perform acceptance in the trusted local environment. Synthetic tests already cover different widths/heights, reordering, leading-zero IDs, zero versus blank, formulas/errors, duplicate keys, changed exports, and known identity-leak markers; they do not prove real-record compatibility or privacy isolation.

History: [CHANGELOG.md](CHANGELOG.md).
