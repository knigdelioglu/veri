from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from dataset_factory.materialize_pilot_batch import build_batch_records


class PilotBatchMaterializationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.records = build_batch_records(cls.root, batch="pilot-wave-2")

    def test_wave2_builds_exactly_100_unique_records(self):
        self.assertEqual(len(self.records), 100)
        self.assertEqual(len({record["id"] for record in self.records}), 100)

    def test_wave2_distribution(self):
        self.assertEqual(Counter(r["modality"] for r in self.records), Counter({"written": 60, "speaking": 20, "listening": 20}))
        self.assertEqual(Counter(r["grade"] for r in self.records), Counter({9: 40, 10: 20, 11: 20, 12: 20}))
        self.assertEqual(
            Counter(r["metadata"]["response_quality"] for r in self.records),
            Counter({"full_correct": 19, "high_partial": 20, "mid_partial": 20, "low_partial": 15, "incorrect": 10, "blank_irrelevant": 5, "borderline": 11}),
        )

    def test_wave2_special_case_counts(self):
        self.assertEqual(sum(bool(r["metadata"]["hard_case_types"]) for r in self.records), 20)
        self.assertEqual(sum(r["metadata"]["adversarial"] for r in self.records), 4)
        self.assertEqual(sum(r["gold_evaluation"]["needs_review"] for r in self.records), 0)
        self.assertEqual(sum(r["metadata"]["review_count"] >= 2 for r in self.records), 25)

    def test_all_borderline_records_have_second_pass(self):
        borderline = [r for r in self.records if r["metadata"]["response_quality"] == "borderline"]
        self.assertEqual(len(borderline), 11)
        self.assertTrue(all(r["metadata"]["review_count"] >= 2 for r in borderline))

    def test_rewrites_and_hard_case_cleanup_are_applied(self):
        texts = {r["student_response"]["text"]: r for r in self.records}
        rewritten = texts["Bacalarla ilgili bir kişileştirme var. Fabrikanın sessiz kaldığını anlatıyor."]
        self.assertEqual(rewritten["gold_evaluation"]["total_score"], 7)
        self.assertEqual(rewritten["metadata"]["response_quality"], "mid_partial")
        self.assertEqual(rewritten["metadata"]["hard_case_types"], [])

        stale = [
            r for r in self.records
            if r["student_response"]["text"].startswith("İki kişi de bir ulaşım aracını bekliyor")
        ]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["metadata"]["hard_case_types"], [])

    def test_speaking_is_transcript_only(self):
        speaking = [r for r in self.records if r["modality"] == "speaking"]
        self.assertEqual(len(speaking), 20)
        for record in speaking:
            self.assertEqual(record["student_response"]["observations"], [])
            for criterion in record["rubric"]["criteria"]:
                self.assertFalse(set(criterion["evidence_sources"]) & {"audio_delivery", "teacher_observation"})

    def test_record_id_ranges_do_not_overlap_wave1(self):
        ids = {r["id"] for r in self.records}
        self.assertIn("tde09-written-000026", ids)
        self.assertIn("tde09-written-000065", ids)
        self.assertIn("tde10-written-000051", ids)
        self.assertIn("tde10-written-000070", ids)
        self.assertIn("tde11-speaking-000026", ids)
        self.assertIn("tde11-speaking-000045", ids)
        self.assertIn("tde12-listening-000026", ids)
        self.assertIn("tde12-listening-000045", ids)

    def test_totals_match_criterion_sums(self):
        for record in self.records:
            gold = record["gold_evaluation"]
            self.assertEqual(gold["total_score"], sum(item["score"] for item in gold["criterion_results"]))
            self.assertEqual(gold["max_score"], record["task"]["max_score"])


if __name__ == "__main__":
    unittest.main()
