from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from dataset_factory.materialize_pilot_batch import build_batch_records


class Iteration1Wave10MaterializationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.records = build_batch_records(cls.root, batch="iteration-1-wave-10")

    def test_builds_100_unique_records(self):
        self.assertEqual(len(self.records), 100)
        self.assertEqual(len({r["id"] for r in self.records}), 100)

    def test_distribution(self):
        self.assertEqual(Counter(r["modality"] for r in self.records), Counter({"written":50,"speaking":25,"listening":25}))
        self.assertEqual(Counter(r["grade"] for r in self.records), Counter({9:25,10:25,11:25,12:25}))
        self.assertEqual(Counter(r["metadata"]["response_quality"] for r in self.records), Counter({"full_correct":20,"high_partial":20,"mid_partial":20,"low_partial":15,"incorrect":10,"blank_irrelevant":5,"borderline":10}))

    def test_four_25_answer_families_and_task_density(self):
        families = Counter(r["metadata"]["question_family"] for r in self.records)
        self.assertEqual(len(families), 4)
        self.assertTrue(all(count == 25 for count in families.values()))
        tasks = Counter(r["task"]["task_id"] for r in self.records)
        self.assertEqual(len(tasks), 8)
        self.assertTrue(all(count in {12,13} for count in tasks.values()))

    def test_special_case_counts(self):
        self.assertEqual(sum(bool(r["metadata"]["hard_case_types"]) for r in self.records), 18)
        self.assertEqual(sum(r["metadata"]["adversarial"] for r in self.records), 4)
        self.assertEqual(sum(r["gold_evaluation"]["needs_review"] for r in self.records), 8)
        self.assertEqual(sum(r["metadata"]["review_count"] >= 2 for r in self.records), 25)

    def test_all_borderline_review_and_adversarial_records_are_dual_reviewed(self):
        borderline=[r for r in self.records if r["metadata"]["response_quality"] == "borderline"]
        self.assertEqual(len(borderline),10)
        self.assertTrue(all(r["metadata"]["review_count"] >= 2 for r in borderline))
        review=[r for r in self.records if r["gold_evaluation"]["needs_review"]]
        self.assertEqual(len(review),8)
        self.assertTrue(all(r["metadata"]["review_count"] >= 2 for r in review))
        adversarial=[r for r in self.records if r["metadata"]["adversarial"]]
        self.assertEqual(len(adversarial),4)
        self.assertTrue(all(r["metadata"]["review_count"] >= 2 for r in adversarial))
        self.assertTrue(all("prompt_injection" in r["metadata"]["hard_case_types"] for r in adversarial))

    def test_review_records_have_material_input_uncertainty(self):
        for record in [r for r in self.records if r["gold_evaluation"]["needs_review"]]:
            self.assertIn(record["student_response"]["source"], {"raw_ocr","raw_stt"})
            self.assertTrue(record["student_response"].get("input_uncertainties"))

    def test_diagnostic_prose_not_in_student_text(self):
        forbidden=("OCR'daki", "STT'deki", "transkriptte", "el yazısında", "ses kaydında")
        for record in self.records:
            text=record["student_response"]["text"]
            self.assertFalse(any(token in text for token in forbidden), text)

    def test_speaking_is_transcript_only(self):
        speaking=[r for r in self.records if r["modality"] == "speaking"]
        self.assertEqual(len(speaking),25)
        for record in speaking:
            self.assertEqual(record["student_response"]["observations"],[])
            for criterion in record["rubric"]["criteria"]:
                self.assertFalse(set(criterion["evidence_sources"]) & {"audio_delivery","teacher_observation"})

    def test_expected_id_ranges(self):
        ids={r["id"] for r in self.records}
        expected={
            "tde09-written-000351","tde09-written-000375",
            "tde10-written-000356","tde10-written-000380",
            "tde11-speaking-000351","tde11-speaking-000375",
            "tde12-listening-000331","tde12-listening-000355",
        }
        self.assertTrue(expected.issubset(ids))

    def test_totals_match_criterion_scores(self):
        for record in self.records:
            gold=record["gold_evaluation"]
            self.assertEqual(gold["total_score"],sum(x["score"] for x in gold["criterion_results"]))
            self.assertEqual(gold["max_score"],record["task"]["max_score"])


if __name__ == "__main__":
    unittest.main()
