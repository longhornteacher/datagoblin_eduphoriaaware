# Adapter verification record — 2026-11-02

Adapter 0.1.0 is tested with independently constructed OOXML fixtures in `tests/synthetic_xlsx.py`. No supplied student rows, original report titles, group labels, worksheet names, demographics or score values are used as fixture data.

| Retained observation pattern | Synthetic structural coverage |
| --- | --- |
| `slsb-2025-g5`: 29 child standards, three-row merged header band | 29 invented grade-7 codes, same merge relationships and field labels; literal ratios and synthetic identities |
| `slsb-2026-g6`: 33 child standards, wider merged header band | 33 invented grade-7 codes, dynamic score-block position |
| `itemperc-2025-g5`: 41 question rows, one vertically merged group | 41 invented question/alignment rows, no actual group counts/rates |
| `itemperc-2026-g6`: 45 question rows | 45 invented question/alignment rows, dynamic group bounds |

Additional fixtures cover smaller sizes, reordered fields, optional demographic omission, invalid merges/types/keys, and missing values. This records synthetic testing of corresponding layout patterns, **not execution of the adapters against the original workbooks**. The four observations retain their original header, label, merge and format facts. A source metadata-only check additionally established no table/auto-filter layout in any supplied workbook, recorded as `table_or_filter_layout_observed: false`. No student values or new scoring semantics were inspected.

## Shared standards catalog — adapter 0.2.0

All retained standard-header/code metadata are checked through the shared TEKS normalizer; the existing canonical codes remain unchanged. Independent synthetic tests cover case/numeric-padding normalization, complete suffix retention, cross-method catalog reuse, framework separation, natural ordering and raw-label/tag preservation. Format-1 migration tests use the frozen historical schema plus newly invented rows, and check backups, rollback, aliases, scores, provenance and generation preservation. No original workbook or private store was opened for this catalog change.

## Cross-subject/level extension — adapter 0.3.0

Independent synthetic reports exercise mathematics, science, social studies, ELAR, SLAR, fine arts, technology, health, physical education and languages under separate framework scopes. Both adapters are exercised with K and grades 1–12, plus explicitly registered example course prefixes including A, B, E1, US, ART1 and CS1. Prefixes are not resolved to courses/grades from a hardcoded alias list. Untagged, dotted, parenthetical and compact code forms are tested as syntax extensions, not as observations from new vendor files. Format-2 fixtures verify preserved standard/scope keys and rollback during nullable-grade/catalog migration. No new real subject/grade workbook was opened or claimed compatible.

The existing four evidence records were extended with the already established ELAR subject and report grade, an explicit unverified-version scope, null course/version values and public comparison-group identifiers. Their source labels, codes, merges and measured layouts remain unchanged. The checker now supports K/course metadata and compares paired code coverage by subject/scope/level/year/group, preventing unrelated subjects in the same grade/year from being combined.
