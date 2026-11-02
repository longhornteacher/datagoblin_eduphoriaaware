# Template history

## 1.3.0 — 2026-11-02

- Extended the shared standard model to kindergarten, numeric grade levels and explicit course prefixes across subjects; numeric grade is nullable for K/course standards instead of fabricated.
- Added optional private subject/version registration and required explicit course registration for named prefixes. Conflicting framework/course registrations stop rather than reclassify historical data.
- Made R/S tags optional and added synthetically tested parenthetical, dotted and compact source forms. Original labels/tags remain private. Existing observed short-code mappings remain unchanged.
- Added database format 3 with paired-backup migrations from formats 1 and 2, preserving stable keys, aliases, scores, descriptions and historical provenance.
- Recorded synthetic cross-subject/K–12/course coverage separately from the unchanged real grade-5/6 structural evidence.
- Extended evidence metadata/schema for subject scope and K/course levels; fixed coverage pairing to distinguish subjects/frameworks and permit an unpaired method observation. Existing source labels and layout measurements remain unchanged.

## 1.2.0 — 2026-11-02

- Centralized TEKS normalization for both source notations: dotted codes with consistent numeric/case conventions and complete suffixes; original labels and tags remain private.
- Added framework-scoped standards catalog, structured code components, original-label provenance, and foreign-key references from both result tables. Missing descriptions remain null.
- Added natural standard ordering and the additive opaque `standards_scope_key` packet field; short code spellings alone do not establish cross-framework identity.
- Added database format 2 and an explicit paired-backup migration preserving aliases, snapshots, scores and historical provenance. Verification uses synthetic legacy records only; no private store was opened.
- Extended the structural-evidence verification record with shared-normalizer coverage; retained workbook facts remain unchanged.

## 1.1.0 — 2026-11-02

- Added adapter implementation/verification metadata without changing source-field meanings, headers, labels or merge evidence. Extended the four structure-only observations with a verified absence of table/auto-filter layouts.
- Implemented and tested both report adapters using independent synthetic XLSX files, including the documented dynamic widths/heights. Recorded the distinction from real-record acceptance in `observations/ADAPTER_VALIDATION.md`.
- Added compact matrix export profile `datagoblin.agent.v1`, shared null/status meanings and packet-level provenance, unweighted per-standard summaries, and selective packet queries. Unverified flags and original group counts remain excluded.
- Added private transactional normalized/identity databases, stable random aliases, immutable changed-export snapshots, quiet errors, and closed paired sync publication. Actual item-entity normalization and automated restore remain future work.

## Storage configuration clarification — 2026-11-02

- Defined a per-user private sync-folder setting and version-1 folder layout, with the user's actual location confined to ignored local configuration.
- Clarified that future processing publishes closed private database/identity snapshots from nonsynced working storage. Report meanings, layouts, contracts and structural evidence remain unchanged at 1.0.0.

## 1.0.0 — 2026-11-02

- Recorded two report methods from four supplied XLSX layouts: student learning standards and group item analysis, each in grade 5 / 2025 and grade 6 / 2026.
- Preserved only structural observations, including dynamic standard widths, dynamic question counts, merges, labels, and percent formats.
- Defined proposed detection, field mappings, cleaning, normalized storage, snapshot handling, tabulation, pseudonymized allowlists, and validation gates.
- Recorded unverified scoring, export-UI, population and cross-year semantics explicitly. No importer or private-record processing is claimed.
