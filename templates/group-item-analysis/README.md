# Group item analysis (`itemperc`)

Method ID: `group_item_analysis`. Contract version: `1.3.0`. Adapter: `0.3.0`, verified with independent synthetic XLSX inputs only. Real-record compatibility remains untested.

## Purpose and export checklist

This method provides reported correctness percentages for each question in a selected group, plus question-to-standard alignment. It can describe group item performance. It contains no student identifiers or individual responses, so it cannot produce student-item results or identify which students missed an item.

Configure a vertical question view with `Total Students`, `Question Number`, `Learning Standard Number`, and `Student Correct`, grouped by the selected population and assessment. Export XLSX. The full saved-view name and click path remain unconfirmed. Record the filters, group definition, role/scope, administration/form and roster timing privately.

## Verified layout

| Component | Grade 5 / 2025 | Grade 6 / 2026 |
| --- | --- | --- |
| Assessment title | B1:E1 merged | Same |
| Unlabeled group-header area | A1:A2 merged | Same |
| Field headers | B2:E2 | Same |
| Group label spanning data | A3:A43 merged | A3:A47 merged |
| Question rows | 3:43, labels 1..41 | 3:47, labels 1..45 |
| Distinct alignment codes | 29 | 33 |

Coordinates/counts are examples only. Each source has one worksheet and one group block; no formula cells or hidden rows/columns were observed. Multiple groups, multiple alignments per question, totals and missing-value encodings have not been verified. Do not read the last worksheet row as a fixed question count.

## Field meanings and mappings

| Source | Normalized target | Encoding / meaning | Privacy |
| --- | --- | --- | --- |
| Unlabeled column A merged block | private `report_populations` context | Group label, stored only at merge anchor | Map to opaque population key |
| Total Students | `group_item_results.reported_total_students` | Numeric integer, repeated by question; exact denominator semantics unverified | Private by default |
| Question Number | `items.question_label` | Numeric whole label in samples; normalize to decimal text without `.0` | Assessment/form-scoped label |
| Learning Standard Number | shared catalog + `group_item_results.standard_key` | Text normalized dotted code, e.g. `6.8.E.iii`, exact original retained privately | Allowlisted canonical code |
| Student Correct | `group_item_results.reported_correct_ratio` | Numeric, `0.00%` format; fraction `[0,1]` | Allowlisted group metric |

`Student Correct` is a percentage-formatted measure, not a raw count despite the label. Its precise numerator/denominator, partial-credit treatment, and treatment of untested students remain unverified. Do not derive an integer correct count from it.

Standards follow [standards.json](../standards.json), using the same framework-scoped catalog and canonical spelling as student-standard headers. R/S tags are not inferred where absent. Exact source codes are retained in `standard_source_labels`; unavailable descriptions remain null. The opaque `standards_scope_key` appears once in each packet so equal short codes from different subjects/versions need not be conflated. See [standards storage and migration](../../docs/standards.md).

K, grades 1–12 and explicitly registered named course prefixes share this model across subjects. Dotted, parenthetical and compact code forms, with optional R/S tags, are synthetically tested extensions. The actual field/grain/merge evidence remains limited to the supplied grade-5/6 report examples.

## Parse/clean recipe

1. Require XLSX with exactly one worksheet in v1. Locate the unique header row containing all four exact field labels, after header whitespace normalization. Reject duplicates, extra populated fields and ambiguity. Infer the header/title band from actual merges rather than row-number constants.
2. Locate the unlabeled group column adjacent to the field block and the merge containing the first data row. Version 1 requires exactly one group block. Inherit its label only within that exact merge rectangle, then register an opaque population key privately. Never forward-fill it beyond the merge or export the raw label. Unmerged or multiple group blocks need a separately verified variant.
3. Discover data rows inside that group merge. Ignore wholly blank rows; validate partial rows. Require one positive whole numeric question label per row in this observed variant; convert it losslessly to text. Do not require contiguous numbering or a fixed count. Text labels, subparts and repeated questions need explicit new evidence.
4. Validate each dotted standard code, normalize with the shared TEKS policy, and retain exact source spelling privately. Record one item/alignment per observed question and link it to the framework-scoped catalog entry. Repeated question labels within the snapshot quarantine the import rather than multiplying an aggregate across alignments.
5. Parse `Total Students` as a nonnegative integer and `Student Correct` as a finite ratio, never as a count. A blank ratio produces null/`source_blank`. Blank count, negative/fractional count, invalid percent, formula/error cells or out-of-block populated rows stop the import. Zero count with nonblank ratio is ambiguous and quarantines the import. If reported counts vary across questions, quarantine until the population/denominator meaning is confirmed; never silently choose one count.
6. Store immutable snapshot, catalog entries, original standard labels, group-item facts/alignments and private source-cell provenance in one transaction. In adapter 0.3.0, each item/alignment is represented directly in `group_item_results`; separate item entities remain proposed. Export only allowed fields after local review. The repeated counts stay attached to each source fact privately; do not sum them. The compact `group_items` packet excludes those counts and supplies shared provenance/scope keys once. See [pipeline commands and export format](../../docs/pipeline.md).

## Validation and tabulation

For `Q` accepted question rows require `Q` unique item labels, `Q` group-item facts, and `Q` alignments in this single-alignment variant. Question labels are scoped to assessment/form. Group label text is not a reliable cross-export identity. Check alignment-set coverage against the paired student-standard method only after registering the same assessment/form; a matching code set does not establish matching populations or scoring rules.

Show reported item ratios independently. Ranking within the same registered group/assessment is descriptive only. A standard-level mean of item rates, if requested, must be labeled an unweighted mean across reported items, with question count and missingness; it is not the student-standard report's measure. Pooled or weighted rates require verified numerators, denominators and point weights. Group counts cannot establish longitudinal student membership.

## Open source questions

- What is the exact saved-view/export workflow and how are its group filters applied?
- Does `Total Students` count rostered students, tested students, valid responses, or another population? Can it legitimately vary by item?
- Does `Student Correct` mean fully correct students, mean point fraction, or something else for partial-credit items?
- Can a question align to multiple standards and appear more than once? How are those repeated rows encoded?
- How are omitted/unanswered/untested items, zero groups, totals and multiple groups represented?
- Is there a stable assessment/form/item identifier or a richer item-detail export?

Follow [common.md](../common.md) for storage, pseudonymization, reconciliation and changes over time.
