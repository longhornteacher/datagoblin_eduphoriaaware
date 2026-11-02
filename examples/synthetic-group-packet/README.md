# Reading this DataGoblin packet

Read `data.json`. Tables have `columns` once and positional `rows`; zip each row
with its columns. No original spreadsheet is needed. The packet describes one
explicit export snapshot, not automatically the latest assessment or a matched cohort.

- All ratios are underlying fractions in [0,1], with source precision retained.
- A numeric zero is a reported zero. `null` means source_blank, with no inferred
  reason. Non-null numeric cells are reported values, except the derived means.
- `std:CODE` columns contain student-standard reported ratios. They are aggregates,
  not individual item answers. Grade/suffixes remain part of the standard code.
- Standard keys use dotted LEVEL_OR_COURSE.NUMBER.EXPECTATION[.subexpectation]
  notation, e.g. K.2.B, 5.2.B.v or A.5.C. Compare codes across packets only with
  the same standards_scope_key; it scopes subject/version/course within the source
  namespace. A course prefix does not establish the student's enrolled grade.
- Raw score, scale score and percent score are distinct reported measures with
  unverified scoring denominators. Do not reconstruct points or pooled rates.
- `standard_summary` means are unweighted arithmetic means across available
  student ratios. `n_observed` and `n_missing` count that table's student rows.
- `group_items` ratios are reported group correctness measures; numerator,
  denominator and partial-credit semantics remain unverified. The original
  repeated Total Students counts are deliberately excluded.
- Student aliases persist within a private source namespace. Assessment,
  population, snapshot and provenance keys are opaque. Cite the provenance_ref,
  snapshot_key, student alias/question label and standard column to trace a fact
  through the trusted local process. Raw cell addresses are private.
- Achievement flags, identities, demographics, names, titles, filenames, group
  labels and unreviewed text are excluded. Standard codes disclose curriculum/grade.
- Do not infer a common cohort, equivalent standards, item correspondence or
  score growth across assessments. Keep student-standard and group-item grains distinct.

Pseudonymized data remains linkable student data. The trusted local user reviews
this packet before making it accessible to an analysis agent.
