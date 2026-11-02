"""Repository CLI. Run real-record processing locally outside agent sessions."""

import argparse
import json
import os
from pathlib import Path
import sys
import warnings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from aware_results.adapters import METHODS
from aware_results.errors import PipelineError, require
from aware_results.export import export_packet
from aware_results.migrate import migrate_store
from aware_results.publish import publish_store
from aware_results.storage import import_report, initialize_store, validate_work_root
from sync_folder import SyncFolderError, load_sync_root


class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default echoes unknown arguments, potentially private paths.
        raise PipelineError("invalid_command_arguments")


def main(argv=None) -> int:
    try:
        parser = QuietParser(description="Trusted local import, private storage and compact pseudonymized export.")
        parser.add_argument("--work-dir", type=Path, help="Nonsynced private working folder; or DATAGOBLIN_WORK_DIR.")
        sub = parser.add_subparsers(dest="command", required=True, parser_class=QuietParser)
        sub.add_parser("init-store", help="Explicitly create a new private store and identity map.")
        sub.add_parser("migrate-store", help="Back up and upgrade a v1/v2 private store for grade/course standards.")
        imp = sub.add_parser("import", help="Validate and privately store one XLSX report.")
        imp.add_argument("--input", type=Path, required=True)
        imp.add_argument("--method", choices=METHODS, required=True)
        imp.add_argument("--context", type=Path, required=True, help="Private JSON context file; see docs/pipeline.md.")
        exp = sub.add_parser("export", help="Create one compact packet for local review before agent access.")
        exp.add_argument("--snapshot", required=True)
        exp.add_argument("--out", type=Path, required=True)
        sub.add_parser("publish", help="Copy closed private DB generations and originals to configured sync storage.")
        args = parser.parse_args(argv)
        raw_work = args.work_dir if args.work_dir is not None else os.environ.get("DATAGOBLIN_WORK_DIR")
        require(bool(raw_work), "work_directory_not_configured")
        sync_root = load_sync_root()
        work_root = validate_work_root(Path(raw_work), project_root=PROJECT_ROOT, sync_root=sync_root)
        # Library warnings may echo source content. Convert them to quiet errors.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            if args.command == "init-store":
                initialize_store(work_root)
                print("Private store initialized. Preserve the identity database to keep aliases stable.")
            elif args.command == "migrate-store":
                changed = migrate_store(work_root)
                print("Private store migrated with a paired local backup." if changed else "Private store is already current.")
            elif args.command == "import":
                context = json.loads(args.context.read_text(encoding="utf-8"))
                snapshot, created = import_report(work_root, args.input, args.method, context)
                print(json.dumps({"status": "imported" if created else "already_imported", "snapshot_key": snapshot}, separators=(",", ":")))
            elif args.command == "export":
                export_packet(work_root, args.snapshot, args.out, sync_root=sync_root)
                print("Pseudonymized packet created for local review.")
            else:
                publish_store(work_root, sync_root)
                print("Closed private snapshots published. Confirm sync completion locally before changing devices.")
        return 0
    except (PipelineError, SyncFolderError) as error:
        print(f"Processing stopped: {error}", file=sys.stderr)
    except Exception:
        print("Processing stopped: private_processing_error", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
