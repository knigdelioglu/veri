from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from dataset_factory.materialize_pilot_batch import build_batch_records


class PilotWave3MaterializationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.records = build_batch_records(cls.root, batch="pilot-wave-3")

    def test_builds_exactly_100_unique_records(self):
        self.assertEqual(len(self.records), 100)
        self.assertEqual(len({r["id"] for r in self.records}), 100)

    def test_distribution_is_exact(self):
        self.assertEqual(Counter(r["modality"] for r in self.records), Counter({"written": 40, "speaking": 20, "listening": 40}))
        self.assertEqual(Counter(r["grade"] for r in self.records), Counter({9: 20, 10: 20, 11: 20, 12: 40}))
        self.assertEqual(
            Counter(r["metadata"]["response_quality"] for r in self.records),
            Counter({"full_correct": 20, "high_partial": 20, "mid_partial": 20, "low_partial": 15, "incorrect": 10, "blank_irrelevant": 5, "borderline": 10}),
        )

    def test_special_case_counts(self):
        self.assertEqual(sum(bool(r["metadata"]["hard_case_types"]) for r in self.records), 20)
        self.assertEqual(sum(r["metadata"]["adversarial"] for r in self.records), 4)
        self.assertEqual(sum(r["gold_evaluation"]["needs_review"] for r in self.records), 12)
        self.assertEqual(sum(r["metadata"]["review_count"] >= 2 for r in self.records), 30)

    def test_all_escalations_have_explicit_raw_input_uncertainty(self):
        escalations = [r for r in self.records if r["gold_evaluation"]["needs_review"]]
        self.assertEqual(len(escalations), 12)
        self.assertEqual(Counter(r["student_response"]["source"] for r in escalations), Counter({"raw_ocr": 6, "raw_stt": 6}))
        for record in escalations:
            self.assertTrue(record["student_response"].get("input_uncertainties"))
            self.assertGreaterEqual(record["metadata"]["review_count"], 2)

    def test_student_text_does_not_contain_capture_diagnostic_prose(self):
        forbidden = ("Transkriptte", "transkriptimde", "OCR’da", "OCR'da", "taranan cevabımda")
        for record in self.records:
            text = record["student_response"]["text"]
            self.assertFalse(any(token in text for token in forbidden), text)

    def test_borderline_without_source_uncertainty_is_scoreable(self):
        target = [r for r in self.records if r["student_response"]["text"].startswith("Cümle büyük olasılıkla ironik")]
        self.assertEqual(len(target), 1)
        self.assertFalse(target[0]["gold_evaluation"]["needs_review"])
        self.assertEqual(target[0]["student_response"]["source"], "manual")
        self.assertNotIn("input_uncertainties", target[0]["student_response"])

    def test_raw_sources_are_never_used_without_uncertainty_metadata(self):
        raw = [r for r in self.records if r["student_response"]["source"] in {"raw_ocr", "raw_stt"}]
        self.assertEqual(len(raw), 12)
        self.assertTrue(all(r["student_response"].get("input_uncertainties") for r in raw))

    def test_record_id_ranges_follow_existing_canonical_data(self):
        ids = {r["id"] for r in self.records}
        self.assertIn("tde09-written-000066", ids)
        self.assertIn("tde09-written-000085", ids)
        self.assertIn("tde10-written-000071", ids)
        self.assertIn("tde10-written-000090", ids)
        self.assertIn("tde11-speaking-000046", ids)
        self.assertIn("tde11-speaking-000065", ids)
        self.assertIn("tde12-listening-000046", ids)
        self.assertIn("tde12-listening-000085", ids)

    def test_totals_match_criterion_sums(self):
        for record in self.records:
            gold = record["gold_evaluation"]
            self.assertEqual(gold["total_score"], sum(item["score"] for item in gold["criterion_results"]))
            self.assertEqual(gold["max_score"], record["task"]["max_score"])


if __name__ == "__main__":
    unittest.main()
