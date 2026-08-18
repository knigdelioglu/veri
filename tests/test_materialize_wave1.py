from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from dataset_factory.materialize_wave1 import SECOND_PASS_IDS, build_wave1_records


class Wave1MaterializationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.records = build_wave1_records(cls.root)
        cls.by_id = {record["id"]: record for record in cls.records}

    def test_builds_exactly_100_records(self):
        self.assertEqual(len(self.records), 100)
        self.assertEqual(len({record["id"] for record in self.records}), 100)

    def test_structural_distribution_is_preserved(self):
        self.assertEqual(Counter(r["modality"] for r in self.records), Counter({"written": 50, "speaking": 25, "listening": 25}))
        self.assertEqual(Counter(r["grade"] for r in self.records), Counter({9: 25, 10: 25, 11: 25, 12: 25}))

    def test_quality_distribution_tracks_final_gold_not_initial_quota(self):
        self.assertEqual(
            Counter(r["metadata"]["response_quality"] for r in self.records),
            Counter({"full_correct": 21, "high_partial": 20, "mid_partial": 20, "low_partial": 15, "incorrect": 10, "blank_irrelevant": 5, "borderline": 9}),
        )

    def test_all_records_are_ai_verified_synthetic(self):
        for record in self.records:
            metadata = record["metadata"]
            self.assertEqual(metadata["status"], "ai_verified")
            self.assertEqual(metadata["verification_source"], "ai")
            self.assertEqual(metadata["provenance"], "synthetic")
            self.assertTrue(metadata["pii_reviewed"])
            self.assertEqual(record["student_response"]["source"], "manual")

    def test_second_pass_count_and_genuine_review_target(self):
        self.assertEqual(len(SECOND_PASS_IDS), 30)
        self.assertEqual(sum(r["metadata"]["review_count"] >= 2 for r in self.records), 30)
        review_records = [r for r in self.records if r["gold_evaluation"]["needs_review"]]
        self.assertEqual(len(review_records), 1)
        self.assertEqual(review_records[0]["grade"], 11)
        self.assertIn("STT", review_records[0]["gold_evaluation"]["review_reason"])

    def test_ai_review_metadata_overrides_are_applied(self):
        records_by_text = {record["student_response"]["text"]: record for record in self.records}
        b1_13 = next(record for record in self.records if record["grade"] == 10 and record["task"]["task_id"].endswith("-a") and record["gold_evaluation"]["total_score"] == 10 and record["metadata"]["review_count"] == 2)
        self.assertEqual(b1_13["metadata"]["response_quality"], "full_correct")
        self.assertEqual(b1_13["metadata"]["hard_case_types"], [])

        stale_missing_evidence = [
            record for record in self.records
            if record["metadata"]["review_count"] == 2
            and record["gold_evaluation"]["needs_review"] is False
            and record["metadata"]["hard_case_types"] == ["missing_evidence"]
        ]
        self.assertEqual(stale_missing_evidence, [])
        self.assertTrue(records_by_text)

    def test_synthetic_speaking_is_transcript_only(self):
        speaking = [r for r in self.records if r["modality"] == "speaking"]
        self.assertEqual(len(speaking), 25)
        for record in speaking:
            self.assertEqual(record["task"]["max_score"], 8)
            self.assertTrue(record["rubric"]["rubric_id"].endswith("-transcript"))
            self.assertEqual(len(record["rubric"]["criteria"]), 4)
            for criterion in record["rubric"]["criteria"]:
                self.assertFalse(set(criterion["evidence_sources"]) & {"audio_delivery", "teacher_observation"})
            self.assertEqual(record["student_response"]["observations"], [])

    def test_totals_equal_criterion_sum(self):
        for record in self.records:
            gold = record["gold_evaluation"]
            criterion_total = sum(item["score"] for item in gold["criterion_results"])
            self.assertEqual(gold["total_score"], criterion_total)
            self.assertEqual(gold["max_score"], record["task"]["max_score"])


if __name__ == "__main__":
    unittest.main()
