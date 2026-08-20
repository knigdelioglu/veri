from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset_factory.evaluate_predictions import evaluate_predictions


class EvaluatePredictionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "dataset" / "records" / "written").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _record(self, rid: str, *, needs_review: bool, quality: str, hard: list[str] | None = None) -> dict:
        return {
            "id": rid,
            "schema_version": "1.0",
            "modality": "written",
            "language": "tr",
            "grade": 10,
            "task": {"task_id": f"task-{rid}", "prompt": "Soru", "context": "Bağlam", "max_score": 10},
            "rubric": {
                "rubric_id": "r1",
                "version": "1.0",
                "criteria": [
                    {"criterion_id":"a","name":"A","description":"A","max_score":4,"scoring_anchors":[],"evidence_sources":["response_text"]},
                    {"criterion_id":"b","name":"B","description":"B","max_score":6,"scoring_anchors":[],"evidence_sources":["response_text"]},
                ],
            },
            "student_response": {"text":"Yanıt","source":"manual","observations":[]},
            "gold_evaluation": {
                "criterion_results": [
                    {"criterion_id":"a","score":3,"evidence":["Yanıt"],"justification":""},
                    {"criterion_id":"b","score":4,"evidence":["Yanıt"],"justification":""},
                ],
                "total_score": 7,
                "max_score": 10,
                "needs_review": needs_review,
                "review_reason": "Belirsiz" if needs_review else None,
                "overall_feedback":"",
            },
            "metadata": {
                "status":"ai_verified","split":"validation","created_at":"2026-08-20","tags":[],"pii_reviewed":True,
                "subject_group_id":None,"exam_family":f"exam-{rid}","question_family":f"family-{rid}","provenance":"synthetic",
                "verification_source":"ai","response_quality":quality,"hard_case_types":hard or [],"adversarial":False,
                "review_count":2,"adjudicated":False,
            },
        }

    def _write_record(self, record: dict) -> None:
        path=self.root/"dataset"/"records"/"written"/f"{record['id']}.json"
        path.write_text(json.dumps(record,ensure_ascii=False),encoding="utf-8")

    def _write_predictions(self, rows: list[dict]) -> Path:
        path=self.root/"predictions.jsonl"
        path.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n",encoding="utf-8")
        return path

    def test_perfect_predictions_and_gold_review_exclusion(self):
        self._write_record(self._record("normal", needs_review=False, quality="full_correct"))
        self._write_record(self._record("review", needs_review=True, quality="borderline", hard=["ocr_ambiguity"]))
        predictions=self._write_predictions([
            {"id":"normal","criterion_scores":{"a":3,"b":4},"needs_review":False},
            # Provisional scores intentionally differ; score metrics must ignore this gold escalation.
            {"id":"review","criterion_scores":{"a":0,"b":0},"needs_review":True},
        ])
        report=evaluate_predictions(self.root,predictions,split="validation")
        self.assertEqual(report["coverage"]["evaluated_records"],2)
        self.assertEqual(report["overall"]["resolvable_records"],1)
        self.assertEqual(report["overall"]["criterion_items"],2)
        self.assertEqual(report["overall"]["criterion_exact_rate"],1.0)
        self.assertEqual(report["overall"]["total_mae"],0.0)
        self.assertEqual(report["overall"]["needs_review"]["tp"],1)
        self.assertEqual(report["overall"]["needs_review"]["tn"],1)
        self.assertEqual(report["overall"]["needs_review"]["f1"],1.0)
        self.assertEqual(report["special_slices"]["hard_case"]["records"],1)

    def test_imperfect_prediction_metrics(self):
        self._write_record(self._record("normal", needs_review=False, quality="mid_partial"))
        predictions=self._write_predictions([
            {"id":"normal","criterion_scores":{"a":2,"b":6},"needs_review":True},
        ])
        report=evaluate_predictions(self.root,predictions,split="validation")
        self.assertAlmostEqual(report["overall"]["criterion_mae"],1.5)
        self.assertEqual(report["overall"]["criterion_exact_rate"],0.0)
        self.assertEqual(report["overall"]["criterion_within_1_rate"],0.5)
        self.assertEqual(report["overall"]["total_mae"],1.0)
        self.assertEqual(report["overall"]["needs_review"]["fp"],1)
        self.assertEqual(report["overall"]["needs_review"]["tn"],0)

    def test_strict_coverage_and_criterion_contract(self):
        self._write_record(self._record("a", needs_review=False, quality="full_correct"))
        self._write_record(self._record("b", needs_review=False, quality="full_correct"))
        missing=self._write_predictions([{"id":"a","criterion_scores":{"a":3,"b":4},"needs_review":False}])
        with self.assertRaisesRegex(ValueError,"Missing 1 predictions"):
            evaluate_predictions(self.root,missing,split="validation")

        bad=self._write_predictions([
            {"id":"a","criterion_scores":{"a":3},"needs_review":False},
            {"id":"b","criterion_scores":{"a":3,"b":4},"needs_review":False},
        ])
        with self.assertRaisesRegex(ValueError,"criterion_scores mismatch"):
            evaluate_predictions(self.root,bad,split="validation")


if __name__ == "__main__":
    unittest.main()
