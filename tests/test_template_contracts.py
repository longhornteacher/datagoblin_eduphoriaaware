"""Specification tests only; original workbooks must never be test inputs."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_templates as check


def column(number):
    result = ""
    while number:
        number, rem = divmod(number - 1, 26)
        result = chr(65 + rem) + result
    return result


class TemplateContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_schema = check.load_json(check.TEMPLATES / "report-contract.schema.json")
        cls.observation_schema = check.load_json(check.TEMPLATES / "observation.schema.json")
        cls.contracts = {
            c["method_id"]: c for c in (
                check.load_json(path) for path in check.TEMPLATES.glob("*/contract.json")
            )
        }
        cls.student = check.load_json(check.TEMPLATES / "observations/slsb-2025-g5.json")
        cls.item = check.load_json(check.TEMPLATES / "observations/itemperc-2025-g5.json")

    def assert_invalid_observation(self, observation, code):
        contract = self.contracts[observation["method_id"]]
        with self.assertRaisesRegex(check.SpecificationError, f"^{code}$"):
            check.validate_observation(observation, contract, self.observation_schema)

    def test_registry(self):
        self.assertEqual(check.check_registry(), (2, 4))

    def test_kindergarten_and_course_metadata_are_valid(self):
        for level,course,subject in [('K',None,'mathematics'),('A','A','mathematics')]:
            with self.subTest(level=level):
                observation=deepcopy(self.item)
                observation.update(grade=None,level_code=level,course_code=course,subject=subject)
                observation['standard_codes']=[level+'.'+code.split('.',1)[1] for code in observation['standard_codes']]
                check.validate_observation(observation,self.contracts[observation['method_id']],self.observation_schema)

    def test_comparisons_do_not_cross_subjects_with_same_year_and_grade(self):
        observations=[]
        for subject,code in [('mathematics','5.2.B'),('science','5.3.A')]:
            for method in ('student_learning_standards','group_item_analysis'):
                observation=deepcopy(self.item)
                observation.update(subject=subject,method_id=method,standard_codes=[code])
                observations.append(observation)
        check.validate_comparisons(observations)

    def test_comparison_requires_matching_codes_only_when_counterparts_exist(self):
        first=deepcopy(self.item)
        check.validate_comparisons([first])
        second=deepcopy(first); second['method_id']='student_learning_standards'
        second['standard_codes']=['5.99.A']
        with self.assertRaisesRegex(check.SpecificationError,'^paired_standard_coverage_mismatch$'):
            check.validate_comparisons([first,second])

    def test_contract_rejects_undocumented_properties(self):
        contract = deepcopy(self.contracts["student_learning_standards"])
        contract["guessed_denominator"] = 42
        with self.assertRaisesRegex(check.SpecificationError, "^schema_shape_invalid$"):
            check.validate_contract(contract, self.contract_schema)

    def test_header_mapping_must_match_requirements(self):
        contract = deepcopy(self.contracts["student_learning_standards"])
        contract["fields"][0]["required"] = False
        with self.assertRaisesRegex(check.SpecificationError, "^required_header_mapping_mismatch$"):
            check.validate_contract(contract, self.contract_schema)

    def test_direct_identity_field_rejected_from_export(self):
        contract = deepcopy(self.contracts["student_learning_standards"])
        contract["export_tables"]["student_standard_results"].append("local_id")
        with self.assertRaisesRegex(check.SpecificationError, "^private_field_in_export_allowlist$"):
            check.validate_contract(contract, self.contract_schema)

    def test_snapshot_cannot_have_a_student_records_property(self):
        observation = deepcopy(self.student)
        observation["student_rows"] = []
        self.assert_invalid_observation(observation, "schema_shape_invalid")

    def test_snapshot_cannot_claim_student_records_are_present(self):
        observation = deepcopy(self.student)
        observation["contains_student_records"] = True
        self.assert_invalid_observation(observation, "schema_shape_invalid")

    def test_missing_and_duplicate_headers_rejected(self):
        observation = deepcopy(self.student)
        del observation["headers"]["B2"]
        self.assert_invalid_observation(observation, "observed_header_set_mismatch")
        observation = deepcopy(self.student)
        observation["headers"]["B2"] = observation["headers"]["A2"]
        self.assert_invalid_observation(observation, "duplicate_observed_header")

    def test_percent_format_drift_rejected(self):
        observation = deepcopy(self.item)
        observation["formats_by_field"]["Student Correct"] = "General"
        self.assert_invalid_observation(observation, "observed_format_unrecognized")

    def test_standard_grade_suffix_and_tag_preserved_correctly(self):
        pattern = self.contracts["student_learning_standards"]["dynamic_axis"]["standard_label_pattern"]
        self.assertEqual(check.canonical_standard("6.8(D.iii) [S]", pattern), "6.8.D.iii")
        self.assertNotEqual(check.canonical_standard("5.8(C) [R]", pattern), "6.8.C")
        for bad in ("6.8(D.iii) [X]", "6.8", "6.8(D.iii) private"):
            with self.subTest(label=bad), self.assertRaises(check.SpecificationError):
                check.canonical_standard(bad, pattern)

    def test_duplicate_canonical_standard_rejected_even_with_different_tag(self):
        observation = deepcopy(self.student)
        observation["standard_headers"]["G3"] = "5.2(B.v) [R]"
        self.assert_invalid_observation(observation, "duplicate_canonical_standard")

    def test_question_count_and_duplicate_labels_rejected(self):
        observation = deepcopy(self.item)
        observation["question_count"] += 1
        self.assert_invalid_observation(observation, "question_count_mismatch")
        observation = deepcopy(self.item)
        observation["question_labels"][1] = observation["question_labels"][0]
        self.assert_invalid_observation(observation, "schema_shape_invalid")

    def test_standard_merge_width_and_group_bounds_must_match(self):
        observation = deepcopy(self.student)
        observation["header_merges"].remove("F2:AH2")
        observation["header_merges"].append("F2:AG2")
        self.assert_invalid_observation(observation, "standard_header_geometry_mismatch")
        observation = deepcopy(self.item)
        observation["group_merge"] = "A3:A5"
        self.assert_invalid_observation(observation, "group_merge_geometry_mismatch")

    def test_synthetic_variable_counts_and_reordered_headers(self):
        fixtures = check.load_json(ROOT / "tests/fixtures/synthetic_layout_cases.json")
        self.assertFalse(fixtures["contains_student_records"])
        for case in fixtures["cases"]:
            with self.subTest(case=case["name"]):
                method = case["method_id"]
                contract = self.contracts[method]
                observation = deepcopy(self.student if method == "student_learning_standards" else self.item)
                observation["grade"] = 7
                observation["level_code"] = "7"
                if method == "student_learning_standards":
                    n = len(case["standard_headers"])
                    score_labels = [self.student["headers"][f"{column(i)}2"] for i in range(35, 41)]
                    observation["headers"] = {
                        "A2": "Local ID", "B2": "Student Name",
                        "C2": "Special Ed Indicator", "D2": "Emergent Bilingual",
                        "E2": "Ethnicity", "F2": "All Learning Standards",
                        **{f"{column(i + n + 6)}2": label for i, label in enumerate(score_labels)},
                    }
                    observation["header_merges"] = [
                        "A1:E1", f"F1:{column(n + 11)}1", f"F2:{column(n + 5)}2",
                        *[f"{column(i)}2:{column(i)}3" for i in [*range(1, 6), *range(n + 6, n + 12)]],
                    ]
                    observation["standard_headers"] = {
                        f"{column(i + 6)}3": label for i, label in enumerate(case["standard_headers"])
                    }
                    observation["standard_count"] = n
                    observation["standard_codes"] = case["expected_codes"]
                    observation["blank_trailing_columns"] = [column(n + 12)]
                else:
                    observation["headers"]["B2"], observation["headers"]["C2"] = (
                        observation["headers"]["C2"], observation["headers"]["B2"]
                    )
                    observation["question_labels"] = case["question_labels"]
                    observation["question_count"] = len(case["question_labels"])
                    observation["group_merge"] = f"A3:A{observation['question_count'] + 2}"
                    observation["standard_codes"] = case["standard_codes"]
                check.validate_observation(observation, contract, self.observation_schema)


if __name__ == "__main__":
    unittest.main()
