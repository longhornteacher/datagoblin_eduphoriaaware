# Project working rules

- Read `PROJECT_HANDOFF.md` and `templates/README.md` before implementing adapters.
- `templates/` is the versioned source of report-method contracts. Update the contract, method notes, structural evidence, and changelog together when behavior changes.
- Distinguish observed structure from proposed processing behavior and unresolved source semantics. Do not claim importer compatibility from documentation checks.
- Supplied XLSX files are private source material, not sanitized fixtures. Do not print, copy, commit, or ingest student rows in an unrestricted agent session. For schema work, inspect only report headers, standard/question labels, merges, and formatting. Suppress student values, group labels, filenames, sheet names, and document metadata from generated artifacts.
- Use independently constructed, explicitly synthetic fixtures for importer development. Never generate fixtures by copying real student records and replacing only their names.
- A future trusted local process must handle originals, identity resolution, and the private alias map outside the restricted analysis environment. Git ignore rules do not enforce access restrictions.
- Resolve private sync storage from `DATAGOBLIN_SYNC_DIR` or the Git-ignored `.datagoblin.local.toml`; never hardcode a user's path in tracked files. Follow `docs/sync-folder.md`. Keep active databases outside sync storage and publish closed snapshots through the future trusted workflow. Do not browse or ingest the private sync folder from an unrestricted agent session.
- Do not equate student-standard aggregates, group-item aggregates, and individual item responses. They have different grains and cannot fill in each other's missing facts.
- Unknown layouts or ambiguous semantics must stop or quarantine processing. Never guess identifiers, missing-value meanings, scoring denominators, or comparable growth measures.
- Keep scripts deterministic; use stable private identity mappings and explicit export allowlists. Logs must use generic error codes and private provenance references rather than raw values.
- Validate specifications with `python scripts/check_templates.py` and `python -m unittest discover -s tests` after relevant edits. These checks do not validate real-record ingestion or privacy isolation.
- Real reports and personal configuration have been moved to private sync storage. Keep the repository free of real records even when Git would ignore them. Use per-user environment configuration outside the project. Run `python scripts/check_repo_privacy.py` before committing/pushing; public example datasets must reproduce independent synthetic fixtures. Do not read originals to generate a matching fixture or modify the audit to accept real data.
