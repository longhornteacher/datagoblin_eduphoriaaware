"""Sync setup tests use only synthetic temporary folders, never private storage."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sync_folder as sync


class SyncFolderTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.workspace = self.base / "synthetic-project"
        self.workspace.mkdir()
        self.destination = self.base / "Synthetic Sync Location" / "datagoblin_sync"
        self.config = self.workspace / sync.LOCAL_CONFIG

    def load(self, environ=None):
        return sync.load_sync_root(workspace_root=self.workspace, environ={} if environ is None else environ)

    def write_config(self, destination=None):
        # JSON quoting is also valid TOML basic-string quoting for these paths.
        self.config.write_text(
            "config_version = 1\nsync_dir = " + json.dumps(str(destination or self.destination)) + "\n",
            encoding="utf-8",
        )

    def assert_code(self, code, callback):
        with self.assertRaisesRegex(sync.SyncFolderError, f"^{code}$"):
            callback()

    def test_unconfigured_stops_without_creating_anything(self):
        self.assert_code("sync_directory_not_configured", self.load)
        self.assertFalse(self.destination.exists())

    def test_local_config_with_spaces_and_backslashes(self):
        self.write_config()
        self.assertEqual(self.load(), self.destination)
        self.assertFalse(self.destination.exists())

    def test_environment_overrides_even_malformed_local_config(self):
        self.config.write_text("this is not TOML", encoding="utf-8")
        self.assertEqual(self.load({sync.ENV_SETTING: str(self.destination)}), self.destination)

    def test_empty_environment_does_not_fall_back(self):
        self.write_config()
        self.assert_code("sync_directory_empty_or_invalid", lambda: self.load({sync.ENV_SETTING: ""}))

    def test_persisted_user_setting_works_without_project_configuration(self):
        with patch.dict(sync.os.environ,{},clear=False),patch.object(sync,'user_sync_setting',return_value=str(self.destination)):
            # Remove only this setting; retain Windows home variables.
            with patch.dict(sync.os.environ):
                sync.os.environ.pop(sync.ENV_SETTING,None)
                self.assertEqual(sync.load_sync_root(workspace_root=self.workspace),self.destination)
        self.assertFalse(self.config.exists())

    def test_explicit_process_setting_wins_over_persisted_user_setting(self):
        with patch.object(sync,'user_sync_setting',side_effect=AssertionError('should not read registry')):
            self.assertEqual(self.load({sync.ENV_SETTING:str(self.destination)}),self.destination)

    def test_empty_persisted_setting_does_not_silently_use_local_config(self):
        self.write_config()
        with patch.dict(sync.os.environ),patch.object(sync,'user_sync_setting',return_value=''):
            sync.os.environ.pop(sync.ENV_SETTING,None)
            self.assert_code('sync_directory_empty_or_invalid',lambda: sync.load_sync_root(workspace_root=self.workspace))

    def test_relative_and_nonstrings_rejected(self):
        self.assert_code("sync_directory_must_be_absolute", lambda: self.load({sync.ENV_SETTING: "relative/sync"}))
        self.config.write_text("config_version = 1\nsync_dir = 123\n", encoding="utf-8")
        self.assert_code("sync_directory_empty_or_invalid", self.load)

    def test_missing_unknown_and_invalid_config_versions_rejected(self):
        for contents in (
            "sync_dir = 'x'\n",
            "config_version = 2\nsync_dir = 'x'\n",
            "config_version = true\nsync_dir = 'x'\n",
            "config_version = 1\nsync_dir = 'x'\nunknown = 1\n",
        ):
            with self.subTest(contents=contents):
                self.config.write_text(contents, encoding="utf-8")
                self.assert_code("local_config_unsupported", self.load)

    def test_workspace_overlap_in_both_directions_rejected(self):
        for destination in (self.workspace, self.workspace / "private", self.base):
            with self.subTest(destination=destination):
                self.assert_code("sync_directory_overlaps_workspace", lambda: self.load({sync.ENV_SETTING: str(destination)}))

    def test_root_home_and_file_rejected(self):
        for destination in (Path(self.base.anchor), Path.home()):
            self.assert_code("sync_directory_must_be_dedicated", lambda: self.load({sync.ENV_SETTING: str(destination)}))
        self.destination.parent.mkdir()
        self.destination.write_text("synthetic file", encoding="utf-8")
        self.assert_code("sync_directory_is_not_directory", lambda: self.load({sync.ENV_SETTING: str(self.destination)}))

    def test_initializer_idempotent_and_preserves_unrelated_content(self):
        sync.initialize_sync_folder(self.destination)
        marker = self.destination / sync.MARKER_NAME
        original_marker_bytes = marker.read_bytes()
        report = self.destination / "inbox" / "synthetic-sentinel.txt"
        report.write_text("SYNTHETIC_PRIVATE_VALUE_NEVER_PRINT", encoding="utf-8")
        # Initialization must not open arbitrary stored content.
        with patch.object(Path, "read_bytes", side_effect=AssertionError("content must not be opened")):
            sync.initialize_sync_folder(self.destination)
        self.assertEqual(marker.read_bytes(), original_marker_bytes)
        self.assertEqual(report.read_text(encoding="utf-8"), "SYNTHETIC_PRIVATE_VALUE_NEVER_PRINT")
        self.assertTrue(all((self.destination / name).is_dir() for name in sync.DIRECTORIES))
        self.assertEqual(json.loads(marker.read_text()), sync.MARKER)

    def test_layout_file_conflict_prevents_partial_initialization(self):
        self.destination.mkdir(parents=True)
        (self.destination / "normalized").write_text("synthetic conflict", encoding="utf-8")
        self.assert_code("sync_layout_directory_conflict", lambda: sync.initialize_sync_folder(self.destination))
        self.assertFalse((self.destination / "inbox").exists())
        self.assertFalse((self.destination / sync.MARKER_NAME).exists())

    def test_unknown_marker_prevents_mutation(self):
        self.destination.mkdir(parents=True)
        marker = self.destination / sync.MARKER_NAME
        marker.write_text('{"format_version":999}', encoding="utf-8")
        self.assert_code("sync_marker_unsupported", lambda: sync.initialize_sync_folder(self.destination))
        self.assertFalse((self.destination / "inbox").exists())
        self.assertEqual(marker.read_text(), '{"format_version":999}')

    def test_escaping_child_link_rejected_when_os_supports_symlinks(self):
        self.destination.mkdir(parents=True)
        outside = self.base / "outside"
        outside.mkdir()
        try:
            (self.destination / "inbox").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("OS does not grant symlink creation for this session")
        self.assert_code("sync_layout_link_unsupported", lambda: sync.initialize_sync_folder(self.destination))
        self.assertFalse((self.destination / "identity").exists())

    def test_cli_errors_and_success_do_not_print_private_paths(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["sync_folder.py"]), patch.dict(
            sync.os.environ, {sync.ENV_SETTING: str(self.destination)}
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(sync.main(), 0)
        self.assertNotIn(str(self.destination), stdout.getvalue() + stderr.getvalue())
        self.assertFalse(self.destination.exists())
        with patch.object(sys, "argv", ["sync_folder.py"]), patch.dict(
            sync.os.environ, {sync.ENV_SETTING: "SYNTHETIC_PRIVATE_PATH"}
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(sync.main(), 1)
        self.assertNotIn("SYNTHETIC_PRIVATE_PATH", stdout.getvalue() + stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
