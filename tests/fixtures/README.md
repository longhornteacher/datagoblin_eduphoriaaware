# Synthetic fixtures

`synthetic_layout_cases.json` is independently authored, metadata-only test input. It contains no copied student rows, identities, scores or actual group counts. Labels are invented for exercising different standard/question counts, grade/suffix preservation and noncontiguous question numbering.

Tests use these cases to reshape in-memory structural observations. They check specification consistency only. They are not XLSX fixtures and do not prove Excel parsing, scoring, privacy isolation, pseudonymization or database behavior. Build independently authored synthetic XLSX files with the same merged-header patterns when implementing an actual adapter.

`legacy_store_v1.sql` freezes the historical 0.1.0 database schema for migration tests. It contains no data. `test_standards.py` populates it with independently invented temporary records and XLSX archives to verify catalog backfills, rollback and stable aliases. Do not update the historical schema alongside the production schema.

`legacy_store_v2.sql` similarly freezes the 0.2.0 catalog schema. `test_cross_subject_standards.py` fills it with synthetic records to verify the cross-subject/course upgrade. Both historical schemas remain independent of the current production schema.
