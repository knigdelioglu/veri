from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from dataset_factory.materialize_pilot_batch import build_batch_records


class Iteration2Wave01MaterializationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.records = build_batch_records(cls.root, batch="iteration-2-wave-01")

    def test_builds_100_unique_records(self):
        self.assertEqual(len(self.records), 100)
        self.assertEqual(len({r["id"] for r in self.records}), 100)

    def test_distribution(self):
        self.assertEqual(Counter(r["modality"] for r in self.records), Counter({"written": 60, "speaking": 20, "listening": 20}))
        self.assertEqual(Counter(r["grade"] for r in self.records), Counter({9: 40, 10: 20, 11: 20, 12: 20}))
        self.assertEqual(Counter(r["metadata"]["response_quality"] for r in self.records), Counter({
            "full_correct": 20, "high_partial": 20, "mid_partial": 20,
            "low_partial": 15, "incorrect": 10, "blank_irrelevant": 5, "borderline": 10,
        }))

    def test_family_and_task_density(self):
        families = Counter(r["metadata"]["question_family"] for r in self.records)
        tasks = Counter(r["task"]["task_id"] for r in self.records)
        self.assertEqual(len(families), 5)
        self.assertTrue(all(count == 20 for count in families.values()))
        self.assertEqual(len(tasks), 10)
        self.assertTrue(all(count == 10 for count in tasks.values()))

    def test_special_case_counts(self):
        self.assertEqual(sum(bool(r["metadata"]["hard_case_types"]) for r in self.records), 18)
        self.assertEqual(sum(r["metadata"]["adversarial"] for r in self.records), 4)
        self.assertEqual(sum(r["gold_evaluation"]["needs_review"] for r in self.records), 8)
        self.assertEqual(sum(r["metadata"]["review_count"] >= 2 for r in self.records), 25)

    def test_all_borderline_and_review_records_are_dual_reviewed(self):
        borderline = [r for r in self.records if r["metadata"]["response_quality"] == "borderline"]
        review = [r for r in self.records if r["gold_evaluation"]["needs_review"]]
        self.assertEqual(len(borderline), 10)
        self.assertEqual(len(review), 8)
        self.assertTrue(all(r["metadata"]["review_count"] >= 2 for r in borderline))
        self.assertTrue(all(r["metadata"]["review_count"] >= 2 for r in review))

    def test_review_records_have_material_input_uncertainty(self):
        for record in [r for r in self.records if r["gold_evaluation"]["needs_review"]]:
            self.assertIn(record["student_response"]["source"], {"raw_ocr", "raw_stt"})
            self.assertTrue(record["student_response"].get("input_uncertainties"))

    def test_speaking_is_transcript_only(self):
        speaking = [r for r in self.records if r["modality"] == "speaking"]
        self.assertEqual(len(speaking), 20)
        for record in speaking:
            self.assertEqual(record["student_response"]["observations"], [])
            for criterion in record["rubric"]["criteria"]:
                self.assertFalse(set(criterion["evidence_sources"]) & {"audio_delivery", "teacher_observation"})

    def test_prompt_injection_is_adversarial(self):
        injected = [r for r in self.records if "prompt_injection" in r["metadata"]["hard_case_types"]]
        self.assertEqual(len(injected), 4)
        self.assertTrue(all(r["metadata"]["adversarial"] for r in injected))

    def test_expected_id_ranges(self):
        ids = {r["id"] for r in self.records}
        expected = {
            "tde09-written-000376", "tde09-written-000415",
            "tde10-written-000381", "tde10-written-000400",
            "tde11-speaking-000376", "tde11-speaking-000395",
            "tde12-listening-000356", "tde12-listening-000375",
        }
        self.assertTrue(expected.issubset(ids))

    def test_totals_match_criterion_scores(self):
        for record in self.records:
            gold = record["gold_evaluation"]
            self.assertEqual(gold["total_score"], sum(x["score"] for x in gold["criterion_results"]))
            self.assertEqual(gold["max_score"], record["task"]["max_score"])


if __name__ == "__main__":
    unittest.main()
