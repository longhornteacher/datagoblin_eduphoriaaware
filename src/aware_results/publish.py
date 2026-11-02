"""Publish closed, versioned private snapshots; commit manifest is written last."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from .errors import require
from .storage import canonical_json, connect, read_generation, writer_lock


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def publish_file(source: Path, target: Path) -> str:
    checksum = file_hash(source)
    if target.exists():
        require(target.is_file() and file_hash(target) == checksum, "sync_snapshot_conflict")
    else:
        with source.open("rb") as original, target.open("xb") as stream:
            shutil.copyfileobj(original, stream, length=1024 * 1024)
            stream.flush()
            os.fsync(stream.fileno())
        require(file_hash(target) == checksum, "sync_snapshot_copy_invalid")
    return checksum


def publish_store(root: Path, sync_root: Path) -> None:
    require(not root.is_relative_to(sync_root) and not sync_root.is_relative_to(root), "private_directory_overlap")
    marker = sync_root / ".datagoblin-sync.json"
    require(marker.is_file() and json.loads(marker.read_text(encoding="utf-8")) == {"format_version": 1, "purpose": "private_sync_storage"}, "sync_folder_not_initialized")
    for name in ("identity", "normalized", "manifests", "originals"):
        path = sync_root / name
        require(path.is_dir() and not path.is_symlink() and path.resolve().is_relative_to(sync_root), "sync_layout_invalid")
    with writer_lock(root):
        connection = connect(root)
        try:
            store_id, generation = read_generation(connection)
            hashes = [row[0] for row in connection.execute("SELECT source_hash FROM imports ORDER BY source_hash")]
            require(all(re.fullmatch(r"[a-f0-9]{64}", value) is not None for value in hashes), "archive_hash_invalid")
        finally:
            connection.close()
        # Connections are closed and our cooperating writer lock is still held.
        require(not any((root / (db + suffix)).exists() for db in ("data.sqlite3", "identity.sqlite3") for suffix in ("-wal", "-shm", "-journal")), "database_sidecar_present")
        stem = store_id + "-" + str(generation)
        data_name, identity_name = stem + ".sqlite3", stem + ".sqlite3"
        data_hash = publish_file(root / "data.sqlite3", sync_root / "normalized" / data_name)
        identity_hash = publish_file(root / "identity.sqlite3", sync_root / "identity" / identity_name)
        for source_hash in hashes:
            require(publish_file(root / "originals" / (source_hash + ".xlsx"), sync_root / "originals" / (source_hash + ".xlsx")) == source_hash, "private_archive_conflict")
        manifest = {"format_version": 1, "store_id": store_id, "generation": generation,
                    "normalized": {"file": data_name, "sha256": data_hash}, "identity": {"file": identity_name, "sha256": identity_hash}, "originals": hashes}
        target = sync_root / "manifests" / (stem + ".json")
        payload = (canonical_json(manifest) + "\n").encode("utf-8")
        if target.exists():
            require(target.read_bytes() == payload, "sync_manifest_conflict")
        else:
            with target.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
