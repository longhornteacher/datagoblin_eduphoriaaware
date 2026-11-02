"""Negative cases for release auditing use synthetic markers and temp files."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import check_repo_privacy as audit


class RepositoryPrivacyTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def test_private_export_and_local_setting_are_rejected_even_if_git_ignored(self):
        for name in ('report.xlsx','.datagoblin.local.toml','identity.sqlite3'):
            with self.subTest(name=name):
                target=self.root/name; target.write_text('SYNTHETIC_PRIVATE_MARKER')
                with self.assertRaisesRegex(audit.RepositoryPrivacyError,'^unapproved_file_or_private_configuration$'):
                    audit.inventory(self.root)
                target.unlink()

    def test_example_numerical_records_must_match_independent_fixture(self):
        original=json.loads((ROOT/'examples/synthetic-group-packet/data.json').read_text())
        altered=deepcopy(original)
        altered['tables']['group_items']['rows'][0][2]=0.123456
        (self.root/'data.json').write_text(json.dumps(altered),encoding='utf-8')
        (self.root/'README.md').write_text(audit.GUIDE,encoding='utf-8')
        with self.assertRaisesRegex(audit.RepositoryPrivacyError,'^example_does_not_match_synthetic_fixture$'):
            audit.verify_packet(self.root,original)

    def test_unknown_json_dataset_under_tests_requires_review(self):
        target=self.root/'tests'/'fixtures'/'student-export.json'
        target.parent.mkdir(parents=True)
        target.write_text('{"student_name":"SYNTHETIC_PRIVATE_NAME"}',encoding='utf-8')
        with self.assertRaisesRegex(audit.RepositoryPrivacyError,'^unreviewed_json_dataset$'):
            audit.inventory(self.root)

    def test_extra_packet_identity_field_is_rejected(self):
        original=json.loads((ROOT/'examples/synthetic-group-packet/data.json').read_text())
        altered={**original,'student_name':'SYNTHETIC_PRIVATE_NAME'}
        (self.root/'data.json').write_text(json.dumps(altered),encoding='utf-8')
        (self.root/'README.md').write_text(audit.GUIDE,encoding='utf-8')
        with self.assertRaisesRegex(audit.RepositoryPrivacyError,'^unreviewed_packet_fields$'):
            audit.verify_packet(self.root,original)


if __name__=='__main__': unittest.main()
