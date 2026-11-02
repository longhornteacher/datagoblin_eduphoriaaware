# Consistent TEKS standards

All supported adapters, catalog registration, specification checks and export validation use `src/aware_results/standards.py` as the shared normalization implementation. It applies across subject scopes, kindergarten, numbered grades and explicitly registered named courses. It is a structural parser, not an official TEKS-content lookup. The original grade-5/6 notations are observed evidence; broader forms are synthetic-tested extensions.

| Source label | Stored/exported code | Private source tag |
| --- | --- | --- |
| `5.2(B.v) [S]` | `5.2.B.v` | `S` |
| `5.2.B.v` | `5.2.B.v` | null |
| `6.8(E.iii) [R]` | `6.8.E.iii` | `R` |
| `K.2(B)` | `K.2.B` | null |
| `3.1A` | `3.1.A` | null |
| `A.5(C) [R]` | `A.5.C` | `R` |
| `B.5.A` | `B.5.A` | null |
| `E1.2(A.i)` | `E1.2.A.i` | null |

Canonical notation is `LEVEL_OR_COURSE.NUMBER.EXPECTATION[.subexpectation]`. Numeric components have no zero padding, named prefixes/expectation letters are uppercase, and subexpectation suffixes are lowercase. Keep every suffix and the complete level/course prefix. A parent code such as `5.2.B` is distinct from `5.2.B.v`; grade 5 and grade 6 codes remain distinct. The exact original spelling and optional R/S tag are stored separately. Missing tags are null, never inferred. Unknown patterns and tags stop processing rather than becoming guessed standards.

The parser accepts dotted, parenthetical and compact expectation forms. Additional official citation styles (including full TAC citations), arbitrary free text, descriptions and new workbook layouts require a documented extension. A syntactically valid code does not prove the standard exists in the registered subject/adoption. Course prefix abbreviations are not resolved to course names or student grades by a built-in alias list.

`level_code` retains K, the numeric grade string or the course prefix. `level_kind` distinguishes `kindergarten`, `grade` and `course`. Numeric `grade` is null for K/course codes, and `course_code` is null for K/numeric grades. K is not silently equated with a numeric `0` prefix from an unknown source convention. A course standard never establishes the student's enrolled grade.

## Scope and catalog

The short code is meaningful within its source namespace and a registered framework reference. `framework_ref` must distinguish the subject and applicable framework/adoption version; course scopes also distinguish the course. Numeric K–12 standards may share a subject/version scope while preserving their separate level prefixes. There is no hardcoded subject list. The [TEA TEKS index](https://tea.texas.gov/curriculum-and-instruction/texas-essential-knowledge-and-skills-teks) lists standards across subjects and grade/course resources. That resource is a reference, not an automatic framework assignment to any local report.

New contexts should supply `subject` and `framework_version` together. Legacy reference-only contexts remain usable for numeric/K codes. Named course prefixes require explicit subject, version and matching `course_code`, either supplied in the private context or already registered in that framework. For example:

```json
{
  "source_namespace": "district-and-source-system",
  "assessment_ref": "registered-administration-and-form",
  "population_ref": "registered-roster-and-filters",
  "framework_ref": "TEKS:mathematics:reviewed-version:algebra-I",
  "subject": "mathematics",
  "framework_version": "locally-verified-version",
  "course_code": "A"
}
```

The strings are illustrative registration values. Do not copy an unverified version or map a different prefix to A without confirming the source convention. Omit `course_code` for K/numeric-grade scopes. Conflicting subject/version/course details stop processing. A grade-based framework with existing standards cannot be silently reclassified as a course scope; register a distinct course reference. Private subject/version/course metadata is not automatically exported.

| Private table | Grain / retained fields |
| --- | --- |
| `standards_frameworks` | One opaque `framework_key` per `(source_namespace, framework_ref)`, with explicit optional subject/version/course metadata |
| `standards` | One opaque `standard_key` per `(framework_key, standard_code)`; level code/kind, nullable numeric grade/course code, knowledge/skill number, expectation, optional subexpectation, optional description |
| `standard_source_labels` | Snapshot + source kind + column-code/question key -> standard key, exact source label and source tag |
| Both result tables | Existing normalized code plus a foreign key to its shared catalog entry; key/code pairs must agree |

Both report methods reuse the same catalog entry when scope and canonical code match. The same short code in a different namespace, subject or version gets a separate catalog identity. R/S tags are source alignment metadata; they are not merged into the identity or treated as authoritative curriculum classifications.

The known files provide codes but no descriptions. Consequently `standards.description` remains null; no text is invented, fetched automatically, or inferred from a label. Future description ingestion needs an explicit verified source and privacy review before agent export. Existing exports contain canonical codes only.

## Agent representation

Packets keep short canonical codes for compactness and include one opaque `standards_scope_key` at packet scope. Agents may compare standard identities across packets only when both the scope key and code match. This does not establish identical scoring, item alignment, cohort membership or a valid growth measure. Private framework labels and original source labels remain excluded.

Student columns and standard summaries use natural numbered order: K before numeric grades, `5.2` before `5.10`, and `.ii` before `.ix` before `.x`. Named course scopes sort deterministically by prefix and standard parts, without asserting grade-level equivalence. Sorting reorders values together with their columns; source header order remains recoverable from private provenance. Group questions retain question-number order while their standard codes use the same normalization.

`datagoblin.agent.v1` remains the packet format: the scope key is an additive envelope field, and existing column/value meanings stay the same. Previously emitted packets are still readable, but lack this explicit scope key and must not be joined by short code without trusted framework verification. The packet reader preserves scope metadata when present.

## Existing stores

New stores use internal database format 3. Format-1/2 stores stop with `store_migration_required`. In a trusted local session with `DATAGOBLIN_WORK_DIR` configured, run:

```powershell
python scripts/process_reports.py migrate-store
```

The migration makes a paired SQLite backup in `<work_dir>/migrations/` and advances both database generations together. From format 1 it creates the shared catalog and label provenance directly. From format 2 it preserves existing catalog/scope keys, adds level fields, allows nullable grades/tags, and retains any private descriptions. Aliases, snapshot keys, numerical values, source-cell provenance, and historical parser/contract versions are preserved. Group labels are recovered from v1's verbatim dotted code; no original workbook is reread. New subject/version fields stay null for historical registrations rather than being guessed.

If a legacy label would change its stored code, its source label/tag conflicts, or metadata cannot be resolved, the transaction rolls back with a fixed error code. Resolve the discrepancy locally rather than rewriting or silently merging records. A second migration run is a no-op. Known 0.1.0/1.1.0 and 0.2.0/1.2.0 parser/contract pairs remain idempotent after successful migration. Publish the new closed generation using the normal `publish` command; the prior generation remains intact in sync storage.

Migration and normalization are tested only on independent synthetic records and retained nonstudent structural metadata. No private sync folder or real student records were opened for this change.

The extended tests cover mathematics, science, social studies, ELAR/SLAR, fine arts, technology, health, physical education and languages; these are test scopes rather than a limit on available subjects. Both report patterns are tested with K, grades 1–12 and example named courses. Real non-ELAR/K/course report files have not been accepted yet. Reports lacking currently required score/header fields still need a separately documented layout variant.
