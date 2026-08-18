from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from dataset_factory.materialize_pilot_batch import build_batch_records


class Wave5MaterializationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.records = build_batch_records(cls.root, batch="pilot-wave-5")
        cls.by_id = {r["id"]: r for r in cls.records}

    def test_wave5_builds_100_unique_records(self):
        self.assertEqual(len(self.records), 100)
        self.assertEqual(len({r["id"] for r in self.records}), 100)

    def test_final_wave_distribution(self):
        self.assertEqual(Counter(r["modality"] for r in self.records), Counter({"written":60,"speaking":20,"listening":20}))
        self.assertEqual(Counter(r["grade"] for r in self.records), Counter({9:20,10:40,11:20,12:20}))
        self.assertEqual(Counter(r["metadata"]["response_quality"] for r in self.records), Counter({"full_correct":20,"high_partial":20,"mid_partial":20,"low_partial":15,"incorrect":10,"blank_irrelevant":5,"borderline":10}))

    def test_special_case_counts(self):
        self.assertEqual(sum(bool(r["metadata"]["hard_case_types"]) for r in self.records), 16)
        self.assertEqual(sum(r["metadata"]["adversarial"] for r in self.records), 4)
        self.assertEqual(sum(r["gold_evaluation"]["needs_review"] for r in self.records), 12)
        self.assertEqual(sum(r["metadata"]["review_count"] >= 2 for r in self.records), 30)

    def test_every_review_record_has_material_input_uncertainty(self):
        review = [r for r in self.records if r["gold_evaluation"]["needs_review"]]
        self.assertEqual(len(review), 12)
        for record in review:
            self.assertIn(record["student_response"]["source"], {"raw_ocr","raw_stt"})
            self.assertTrue(record["student_response"].get("input_uncertainties"))
            self.assertGreaterEqual(record["metadata"]["review_count"], 2)

    def test_false_escalation_stays_demoted(self):
        records = [r for r in self.records if r["task"]["task_id"] == "pilot-w5-g10-written-c" and r["metadata"]["response_quality"] == "borderline"]
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertFalse(record["gold_evaluation"]["needs_review"])
        self.assertEqual(record["metadata"]["hard_case_types"], [])
        self.assertEqual(record["student_response"]["source"], "manual")
        self.assertNotIn("input_uncertainties", record["student_response"])

    def test_diagnostic_pipeline_prose_is_not_student_text(self):
        forbidden = ("OCR'da", "STT'de", "transkriptte", "el yazısındaki", "ses kaydında", "doğru okuyup okumadığım")
        for record in self.records:
            text = record["student_response"]["text"]
            self.assertFalse(any(token in text for token in forbidden), text)

    def test_speaking_remains_transcript_only(self):
        speaking = [r for r in self.records if r["modality"] == "speaking"]
        self.assertEqual(len(speaking), 20)
        for record in speaking:
            self.assertEqual(record["student_response"]["observations"], [])
            for criterion in record["rubric"]["criteria"]:
                self.assertFalse(set(criterion["evidence_sources"]) & {"audio_delivery","teacher_observation"})

    def test_expected_id_ranges(self):
        ids = {r["id"] for r in self.records}
        expected = {
            "tde09-written-000106","tde09-written-000125",
            "tde10-written-000111","tde10-written-000150",
            "tde11-speaking-000106","tde11-speaking-000125",
            "tde12-listening-000106","tde12-listening-000125",
        }
        self.assertTrue(expected.issubset(ids))

    def test_totals_match_criterion_scores(self):
        for record in self.records:
            gold = record["gold_evaluation"]
            self.assertEqual(gold["total_score"], sum(x["score"] for x in gold["criterion_results"]))
            self.assertEqual(gold["max_score"], record["task"]["max_score"])


if __name__ == "__main__":
    unittest.main()
