# Private sync folder

The sync folder is a per-user location for all durable private project artifacts, including personally identifiable information (PII). Its location is configuration, never a path hardcoded in an adapter or report template. The user chooses the sync provider and account. DataGoblin uses ordinary filesystem paths; it does not implement cloud sync or configure sharing.

## Configuration

Resolution order:

1. `DATAGOBLIN_SYNC_DIR`, when present in the process environment.
2. The persisted Windows user environment value for `DATAGOBLIN_SYNC_DIR`, when present. This also works in a shell/app started before the setting was saved.
3. `sync_dir` in the project's Git-ignored `.datagoblin.local.toml` (legacy fallback).
4. Fail with `sync_directory_not_configured`. There is no private-data fallback into the repository.

Prefer configuration outside the project. In a trusted local PowerShell session:

```powershell
$env:DATAGOBLIN_SYNC_DIR = 'C:\path\to\datagoblin_sync'
[Environment]::SetEnvironmentVariable('DATAGOBLIN_SYNC_DIR', $env:DATAGOBLIN_SYNC_DIR, 'User')
python scripts/sync_folder.py
python scripts/sync_folder.py --init
```

The validation command checks configuration without creating folders. `--init` creates the layout and a version marker. It is repeatable and preserves existing files. Neither Python command lists, opens, imports, copies, or moves source reports. The initializer inspects only its known directory paths and marker, and emits no configured path. Environment-variable presence takes precedence even when empty or invalid, so a mistake cannot silently choose a different data location.

[config.example.toml](../config.example.toml) documents the legacy local-file format. A personal `.datagoblin.local.toml` must be removed from the workspace before the release privacy audit, even though Git ignores it. The current project's setting is persisted per user; its former personal config is archived privately with the relocated inputs.

The path must be a dedicated absolute directory outside the project, with neither directory containing the other. Home/drive roots and known child paths escaping the selected root through links are rejected. These checks prevent accidental placement; they do not restrict an agent's operating-system access. Keep the local config out of Git and out of later restricted analysis workspaces.

## Storage layout, version 1

```text
<sync_dir>/
  .datagoblin-sync.json    # Format marker only; no identities or absolute paths
  inbox/                  # New original exports awaiting trusted processing
  originals/              # Immutable archived source exports
  identity/               # Closed identity-map snapshots; PII and alias mappings
  normalized/             # Closed normalized-database snapshots; still private
  manifests/              # Source hashes, import context, snapshot versions/provenance
  quarantine/             # Conflicting or unsupported inputs and private diagnostics
  logs/                   # Private operational logs; minimize raw values
```

Every directory under this root is private, including normalized/pseudonymized data and logs. No subdirectory here is automatically approved for agents. A separate explicit export step writes only locally reviewed, allowlisted artifacts to a separately chosen restricted analysis location. Source names, paths, identity maps, and private manifests stay inside the trusted workflow.

## Processing and sync lifecycle

This layout, ingestion and closed-snapshot publication are implemented and tested with synthetic data; automated restore is not implemented. See [pipeline.md](pipeline.md) for commands. The lifecycle rules below also govern future extensions.

- A trusted local process reads inputs here and stages active processing in a separate, nonsynced per-user working directory, configured with `DATAGOBLIN_WORK_DIR` or `--work-dir`. The implemented working store has separate normalized and identity SQLite files.
- Publish immutable, complete artifacts under opaque unique snapshot names. For a database, finish transactions and close it before producing a standalone snapshot. Keep active SQLite databases, journal/WAL/SHM files, locks and temporary working files outside the sync folder. Publication must not depend on several database sidecar files syncing together.
- Record the identity-map generation used by each normalized snapshot in the private manifest. Preserve old generations for restore and provenance. A restored map must retain existing aliases.
- Require one active writer for an identity namespace. Before changing devices, finish publication, confirm sync completion locally, and restore the matching generation. Do not auto-merge provider conflict copies or regenerate aliases when a map appears missing. Missing/inconsistent maps, conflicts or incomplete snapshots must stop processing for local resolution.
- Sync presence alone does not mark an import ready. The implemented importer reads a bounded file, checks its size/modification stamp before and after reading, and validates the parsed payload before result commits. The trusted user must supply a complete, locally available file. No watcher exists yet.
- Sync-provider permissions and actual filesystem/tool restrictions establish who can read these files. This initializer does not configure either. The current unrestricted agent session must not ingest student records from this folder.

The four original workbooks and former personal config were moved to a private transfer batch under `inbox/`. A private manifest in `manifests/` records original/private locations, lengths and verified SHA-256 hashes. No student rows were parsed for relocation, and original filenames/paths are not retained in the public repository. This verifies local relocation; cloud synchronization completion is a provider state, not inferred from the move.
