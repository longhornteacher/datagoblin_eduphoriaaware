# Synthetic agent packets

These packets were produced by the implemented adapters and exporter from independently generated synthetic XLSX workbooks. They contain invented grade-7 standard codes, artificial scores, and random test aliases. They contain no original report data and are for reviewing the output format only.

- [Student packet](synthetic-student-packet/data.json): 2 synthetic students and 29 invented standards, reported score columns, and unweighted standard summaries.
- [Group packet](synthetic-group-packet/data.json): 5 synthetic question results with invented alignments, without original group counts or individual answers.
- [Course packet](synthetic-course-packet/data.json): the same synthetic student-report pattern with an explicitly registered example mathematics course prefix `A`; no student grade is inferred.

Each directory's README explains units, nulls, provenance and limitations. Inspect a few rows with:

```powershell
python scripts/read_packet.py --packet examples/synthetic-student-packet --table standard_summary --limit 5
```

These examples intentionally retain test pseudonyms so they remain usable as static artifacts. They do not provide an identity map. Production packets belong in a separately reviewed analysis location, not in this examples directory.
