from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset_factory.apply_evaluation_review import apply_review


class ApplyEvaluationReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "dataset" / "records" / "speaking").mkdir(parents=True)
        (self.root / "dataset" / "evaluation").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _record(self, rid: str, split: str) -> dict:
        return {
            "id": rid,
            "schema_version": "1.0",
            "modality": "speaking",
            "language": "tr",
            "grade": 11,
            "task": {"task_id": "task-a", "prompt": "Bir görüşü tartışınız.", "context": None, "max_score": 10},
            "rubric": {
                "rubric_id": "r1",
                "version": "1.0",
                "criteria": [
                    {"criterion_id":"claim","name":"Görüş","description":"Açık görüş","max_score":3,"scoring_anchors":[{"score":0,"description":"Yok"},{"score":1,"description":"Belirsiz"},{"score":2,"description":"Sınırlı"},{"score":3,"description":"Açık"}],"evidence_sources":["response_text"]},
                    {"criterion_id":"reasoning","name":"Gerekçe","description":"Gerekçe","max_score":3,"scoring_anchors":[{"score":0,"description":"Yok"},{"score":1,"description":"Sınırlı"},{"score":2,"description":"Uygun"},{"score":3,"description":"Güçlü"}],"evidence_sources":["response_text"]},
                    {"criterion_id":"counterargument","name":"Karşı görüş","description":"Karşı görüş","max_score":2,"scoring_anchors":[{"score":0,"description":"Yok"},{"score":1,"description":"Anılmış"},{"score":2,"description":"Yanıtlanmış"}],"evidence_sources":["response_text"]},
                    {"criterion_id":"organization","name":"Düzen","description":"Düzen","max_score":2,"scoring_anchors":[{"score":0,"description":"Bozuk"},{"score":1,"description":"İzlenebilir"},{"score":2,"description":"Açık"}],"evidence_sources":["response_text"]},
                ],
            },
            "student_response": {"text":"Karşı görüşü açıkça savunuyorum ama gerekçem zayıf.","source":"manual","observations":[]},
            "gold_evaluation": {
                "criterion_results": [
                    {"criterion_id":"claim","score":0,"evidence":["Karşı görüşü açıkça savunuyorum"],"justification":"Eski yanlış puan"},
                    {"criterion_id":"reasoning","score":1,"evidence":["gerekçem zayıf"],"justification":"Sınırlı"},
                    {"criterion_id":"counterargument","score":0,"evidence":[],"justification":"Yok"},
                    {"criterion_id":"organization","score":1,"evidence":[],"justification":"İzlenebilir"},
                ],
                "total_score": 2,
                "max_score": 10,
                "needs_review": False,
                "review_reason": None,
                "overall_feedback": "Eski",
            },
            "metadata": {
                "status":"ai_verified","split":split,"created_at":"2026-08-20","tags":[],"pii_reviewed":True,
                "subject_group_id":None,"exam_family":"exam-a","question_family":"family-a","provenance":"synthetic",
                "verification_source":"ai","response_quality":"incorrect","hard_case_types":[],"adversarial":False,
                "review_count":1,"adjudicated":False,
            },
        }

    def test_applies_only_declared_score_correction_and_dual_reviews_all_eval(self):
        first=self._record("tde11-speaking-000001","validation")
        second=self._record("tde11-speaking-000002","test")
        for record in (first,second):
            path=self.root/"dataset"/"records"/"speaking"/f"{record['id']}.json"
            path.write_text(json.dumps(record,ensure_ascii=False),encoding="utf-8")

        review={
            "review_id":"pass-2",
            "scope":{"splits":["validation","test"],"expected_records":2},
            "corrections":{"tde11-speaking-000001":{"scores":{"claim":3},"response_quality":"low_partial"}},
        }
        review_path=self.root/"dataset"/"evaluation"/"review.json"
        review_path.write_text(json.dumps(review),encoding="utf-8")

        summary=apply_review(self.root,review_path)
        self.assertEqual(summary["records_reviewed"],2)
        self.assertEqual(summary["criterion_scores_changed"],1)

        a=json.loads((self.root/"dataset"/"records"/"speaking"/"tde11-speaking-000001.json").read_text())
        b=json.loads((self.root/"dataset"/"records"/"speaking"/"tde11-speaking-000002.json").read_text())
        self.assertEqual(a["gold_evaluation"]["criterion_results"][0]["score"],3.0)
        self.assertEqual(a["gold_evaluation"]["total_score"],5.0)
        self.assertEqual(a["metadata"]["response_quality"],"low_partial")
        self.assertEqual(a["metadata"]["review_count"],2)
        self.assertEqual(b["metadata"]["review_count"],2)
        self.assertEqual(b["gold_evaluation"]["total_score"],2)

    def test_rejects_correction_outside_evaluation_scope(self):
        record=self._record("tde11-speaking-000003","train")
        path=self.root/"dataset"/"records"/"speaking"/f"{record['id']}.json"
        path.write_text(json.dumps(record),encoding="utf-8")
        review={"review_id":"pass-2","scope":{"splits":["validation","test"],"expected_records":0},"corrections":{"tde11-speaking-000003":{"scores":{"claim":3}}}}
        review_path=self.root/"dataset"/"evaluation"/"review.json"
        review_path.write_text(json.dumps(review),encoding="utf-8")
        with self.assertRaises(ValueError):
            apply_review(self.root,review_path)


if __name__ == "__main__":
    unittest.main()
