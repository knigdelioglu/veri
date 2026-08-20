from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from dataset_factory.materialize_pilot_batch import build_batch_records


class Iteration1Wave01MaterializationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.records = build_batch_records(cls.root, batch="iteration-1-wave-01")

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

    def test_special_case_counts(self):
        self.assertEqual(sum(bool(r["metadata"]["hard_case_types"]) for r in self.records), 18)
        self.assertEqual(sum(r["metadata"]["adversarial"] for r in self.records), 4)
        self.assertEqual(sum(r["gold_evaluation"]["needs_review"] for r in self.records), 8)
        self.assertEqual(sum(r["metadata"]["review_count"] >= 2 for r in self.records), 25)

    def test_review_records_have_real_input_uncertainty(self):
        review = [r for r in self.records if r["gold_evaluation"]["needs_review"]]
        self.assertEqual(len(review), 8)
        for record in review:
            self.assertIn(record["student_response"]["source"], {"raw_ocr", "raw_stt"})
            self.assertTrue(record["student_response"].get("input_uncertainties"))
            self.assertGreaterEqual(record["metadata"]["review_count"], 2)

    def test_borderline_records_are_dual_reviewed_but_not_forced_to_escalate(self):
        borderline = [r for r in self.records if r["metadata"]["response_quality"] == "borderline"]
        self.assertEqual(len(borderline), 10)
        self.assertTrue(all(r["metadata"]["review_count"] >= 2 for r in borderline))
        self.assertTrue(all(r["gold_evaluation"]["needs_review"] is False for r in borderline))

    def test_diagnostic_prose_is_not_student_text(self):
        forbidden = ("OCR'da", "STT'de", "transkriptte", "el yazısındaki", "ses kaydında")
        for record in self.records:
            text = record["student_response"]["text"]
            self.assertFalse(any(token in text for token in forbidden), text)

    def test_speaking_is_transcript_only(self):
        speaking = [r for r in self.records if r["modality"] == "speaking"]
        self.assertEqual(len(speaking), 20)
        for record in speaking:
            self.assertEqual(record["student_response"]["observations"], [])
            for criterion in record["rubric"]["criteria"]:
                self.assertFalse(set(criterion["evidence_sources"]) & {"audio_delivery", "teacher_observation"})

    def test_expected_id_ranges(self):
        ids = {r["id"] for r in self.records}
        expected = {
            "tde09-written-000126", "tde09-written-000165",
            "tde10-written-000151", "tde10-written-000170",
            "tde11-speaking-000126", "tde11-speaking-000145",
            "tde12-listening-000126", "tde12-listening-000145",
        }
        self.assertTrue(expected.issubset(ids))

    def test_second_pass_removed_three_nonessential_hard_labels(self):
        by_candidate_text = {r["student_response"]["text"]: r for r in self.records}
        self.assertEqual(sum(bool(r["metadata"]["hard_case_types"]) for r in self.records), 18)
        self.assertEqual(by_candidate_text["İmge eksik kalmış bir geçmişi düşündürüyor. Kanıt olarak 'gölge yarım kaldı' ifadesine dayanıyorum."]["metadata"]["hard_case_types"], [])

    def test_totals_match(self):
        for record in self.records:
            gold = record["gold_evaluation"]
            self.assertEqual(gold["total_score"], sum(item["score"] for item in gold["criterion_results"]))
            self.assertEqual(gold["max_score"], record["task"]["max_score"])


if __name__ == "__main__":
    unittest.main()
