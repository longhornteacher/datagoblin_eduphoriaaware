# DataGoblin: Eduphoria Aware reports

Local, reproducible assessment-data processing, with pseudonymized outputs for later agent analysis.

Start with [templates/README.md](templates/README.md). It records two observed XLSX report methods across two administrations, their field mappings, normalization rules, limits, and storage/export contracts. [The local pipeline](docs/pipeline.md) now implements both adapters, stable private aliases, SQLite storage, a shared [TEKS standards catalog](docs/standards.md), compact JSON packets, a packet query tool, and publication of closed private snapshots. Verification uses synthetic workbooks; real-record acceptance remains untested.

The project context is in [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md). The supplied real reports have been relocated into private sync storage and removed from this workspace. The repository contains code, documentation, structure-only report metadata and independently constructed synthetic records. No real student records, identity map, private database or personal configuration is included.

Private artifacts belong in a per-user sync folder configured outside the repository with `DATAGOBLIN_SYNC_DIR`. Windows can persist this as a user environment setting; the loader also reads it from older shells. The project-local TOML is a legacy fallback and must be removed before the release privacy check. See [private sync folder setup](docs/sync-folder.md) and [config.example.toml](config.example.toml). Validate with `python scripts/sync_folder.py`; initialize its empty storage layout with `python scripts/sync_folder.py --init`.

To check the template registry using Python 3.11 or later:

```powershell
python -m pip install -r requirements-dev.txt
python scripts/check_templates.py
python -m unittest discover -s tests
python scripts/check_repo_privacy.py
```

The contract checker reads specifications and structural observations only. The test suite generates independent synthetic XLSX inputs in temporary directories; it never opens the supplied private reports. See [pipeline commands and packet format](docs/pipeline.md) for trusted local use, and use `python scripts/read_packet.py --help` for selective queries in an analysis environment.

The release audit rejects raw-data files and personal settings in the workspace, and reproduces all three public packet datasets from independent synthetic fixtures. Review remains necessary for source/documentation edits; this is not a universal PII detector. GitHub checks run these validations on `dev`, `main` and pull requests.

[Synthetic example packets](examples/README.md) show the actual output format without any source report data.

Standards handling is shared across subject scopes, kindergarten, numeric grades, and explicitly registered course prefixes. Subject/version/course details are private configuration; no course is assigned a student grade by inference. New source notations are tested synthetically, while real workbook evidence still covers only the supplied grade-5/6 report layouts.
