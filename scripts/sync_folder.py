"""Configure/initialize private sync storage without opening student records.

This establishes a storage layout, not an agent access boundary or sync engine.
Only explicitly named layout directories and the format marker are inspected.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
import os
from pathlib import Path
import sys
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_SETTING = "DATAGOBLIN_SYNC_DIR"
LOCAL_CONFIG = ".datagoblin.local.toml"
DIRECTORIES = ("inbox", "originals", "identity", "normalized", "manifests", "quarantine", "logs")
MARKER_NAME = ".datagoblin-sync.json"
MARKER = {"format_version": 1, "purpose": "private_sync_storage"}


class SyncFolderError(ValueError):
    """Code-only errors avoid leaking private paths into development logs."""


def user_sync_setting() -> str | None:
    """Read only the explicit Windows user setting, including in older shells."""
    if sys.platform != "win32":
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, ENV_SETTING)[0]
    except FileNotFoundError:
        return None
    except OSError:
        raise SyncFolderError("user_sync_setting_unreadable") from None


def load_sync_root(
    *,
    workspace_root: Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
    config_path: Path | None = None,
) -> Path:
    environment = os.environ if environ is None else environ
    if ENV_SETTING in environment:
        raw = environment[ENV_SETTING]
    else:
        persisted = user_sync_setting() if environ is None else None
        if persisted is not None:
            return load_sync_root(workspace_root=workspace_root, environ={ENV_SETTING: persisted})
        path = config_path if config_path is not None else workspace_root / LOCAL_CONFIG
        try:
            with path.open("rb") as stream:
                config = tomllib.load(stream)
        except FileNotFoundError:
            raise SyncFolderError("sync_directory_not_configured") from None
        except (OSError, ValueError):
            raise SyncFolderError("local_config_unreadable") from None
        if set(config) != {"config_version", "sync_dir"} or type(config["config_version"]) is not int or config["config_version"] != 1:
            raise SyncFolderError("local_config_unsupported")
        raw = config["sync_dir"]
    if not isinstance(raw, str) or not raw.strip():
        raise SyncFolderError("sync_directory_empty_or_invalid")
    try:
        root = Path(raw)
        if not root.is_absolute():
            raise SyncFolderError("sync_directory_must_be_absolute")
        root = root.resolve()
        workspace = workspace_root.resolve()
        if root == Path(root.anchor) or root == Path.home().resolve():
            raise SyncFolderError("sync_directory_must_be_dedicated")
        if root.is_relative_to(workspace) or workspace.is_relative_to(root):
            raise SyncFolderError("sync_directory_overlaps_workspace")
        if root.exists() and not root.is_dir():
            raise SyncFolderError("sync_directory_is_not_directory")
    except (OSError, ValueError) as error:
        if isinstance(error, SyncFolderError):
            raise
        raise SyncFolderError("sync_directory_unavailable") from None
    return root


def initialize_sync_folder(root: Path) -> None:
    """Create only empty layout directories and a nonidentifying version marker."""
    try:
        # Preflight every known target before mutating anything. Never follow a
        # child symlink/junction outside the chosen sync root.
        for name in (*DIRECTORIES, MARKER_NAME):
            target = root / name
            if target.is_symlink() or not target.resolve().is_relative_to(root):
                raise SyncFolderError("sync_layout_link_unsupported")
            if name in DIRECTORIES and target.exists() and not target.is_dir():
                raise SyncFolderError("sync_layout_directory_conflict")
        marker = root / MARKER_NAME
        if marker.exists():
            try:
                existing = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise SyncFolderError("sync_marker_unreadable") from None
            if existing != MARKER:
                raise SyncFolderError("sync_marker_unsupported")
        root.mkdir(parents=True, exist_ok=True)
        for name in DIRECTORIES:
            (root / name).mkdir(exist_ok=True)
        if not marker.exists():
            with marker.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(MARKER, indent=2) + "\n")
    except OSError:
        raise SyncFolderError("sync_layout_initialization_failed") from None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate private sync configuration or initialize empty storage.")
    parser.add_argument("--init", action="store_true", help="Create private layout directories and format marker.")
    args = parser.parse_args()
    try:
        root = load_sync_root()
        if args.init:
            initialize_sync_folder(root)
    except SyncFolderError as error:
        print(f"Sync folder setup failed: {error}", file=sys.stderr)
        return 1
    except Exception:
        print("Sync folder setup failed: unexpected_configuration_error", file=sys.stderr)
        return 1
    print("Private sync folder initialized." if args.init else "Private sync folder configuration is valid.")
    print("No reports moved or opened. Storage access restrictions must be configured separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
