from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset_factory.production import (
    export_sft_curated,
    next_batch_plan,
    production_findings,
    production_report,
)


def strategy() -> dict:
    return {
        "version": "1.0",
        "default_phase": "pilot",
        "phases": {"pilot": {"target_records": 10}},
        "target_distribution": {
            "modality": {"written": 0.5, "speaking": 0.25, "listening": 0.25},
            "grade": {"9": 0.25, "10": 0.25, "11": 0.25, "12": 0.25},
            "response_quality": {
                "full_correct": 0.2,
                "high_partial": 0.2,
                "mid_partial": 0.2,
                "low_partial": 0.15,
                "incorrect": 0.1,
                "blank_irrelevant": 0.05,
                "borderline": 0.1,
            },
        },
        "target_ranges": {
            "needs_review": [0.08, 0.12],
            "hard_case": [0.15, 0.20],
            "adversarial": [0.03, 0.05],
            "dual_review_overall": [0.20, 1.0],
        },
        "question_coverage": {
            "answers_per_exact_task": [2, 4],
            "answers_per_question_family": [2, 6],
            "target_question_families_by_phase": {"pilot": 2},
        },
        "rubric_diversity": {
            "min_distinct_criterion_counts": 1,
            "preferred_criterion_count_range": [1, 5],
        },
        "review_policy": {
            "teacher_verified_min_reviews": 1,
            "evaluation_split_min_reviews": 2,
            "borderline_min_reviews": 2,
            "needs_review_min_reviews": 2,
        },
    }


def record(record_id: str, *, split: str | None = "train", quality: str = "mid_partial") -> dict:
    return {
        "id": record_id,
        "schema_version": "1.0",
        "modality": "written",
        "language": "tr",
        "grade": 11,
        "task": {
            "task_id": "task-1",
            "prompt": "Bir şiirin ana düşüncesini açıklayınız.",
            "context": None,
            "max_score": 10,
        },
        "rubric": {
            "rubric_id": "r1",
            "version": "1.0",
            "criteria": [
                {
                    "criterion_id": "c1",
                    "name": "İçerik",
                    "description": "Ana düşünceyi açıklar.",
                    "max_score": 10,
                    "scoring_anchors": [
                        {"score": 0, "description": "Karşılanmıyor."},
                        {"score": 10, "description": "Tam karşılanıyor."},
                    ],
                    "evidence_sources": ["response_text"],
                }
            ],
        },
        "student_response": {"text": "Örnek cevap", "source": "manual", "observations": []},
        "gold_evaluation": {
            "criterion_results": [
                {
                    "criterion_id": "c1",
                    "score": 6,
                    "evidence": ["Örnek cevap"],
                    "justification": "Kısmen karşılıyor.",
                }
            ],
            "total_score": 6,
            "max_score": 10,
            "needs_review": False,
            "review_reason": None,
            "overall_feedback": "Kısmi başarı.",
        },
        "metadata": {
            "status": "teacher_verified",
            "split": split,
            "created_at": "2026-08-18",
            "tags": [],
            "pii_reviewed": True,
            "subject_group_id": f"student-{record_id}",
            "exam_family": "exam-1",
            "question_family": "family-1",
            "provenance": "real_anonymized",
            "response_quality": quality,
            "hard_case_types": [],
            "adversarial": False,
            "review_count": 1,
            "adjudicated": False,
        },
    }


class ProductionStrategyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "config").mkdir(parents=True)
        (self.root / "dataset" / "records" / "written").mkdir(parents=True)
        (self.root / "config" / "data-production.v1.json").write_text(
            json.dumps(strategy()), encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, payload: dict) -> None:
        path = self.root / "dataset" / "records" / "written" / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_complete_teacher_verified_profile_passes(self):
        self.write(record("tde11-written-000001"))
        self.assertEqual(production_findings(self.root), [])

    def test_missing_response_quality_blocks_verified_record(self):
        payload = record("tde11-written-000001")
        payload["metadata"].pop("response_quality")
        self.write(payload)
        findings = production_findings(self.root)
        self.assertTrue(any(item.code == "response_quality_required" and item.level == "error" for item in findings))

    def test_evaluation_split_requires_dual_review(self):
        payload = record("tde11-written-000001", split="test")
        self.write(payload)
        findings = production_findings(self.root)
        self.assertTrue(any(item.code == "evaluation_split_requires_dual_review" for item in findings))

    def test_prompt_injection_requires_adversarial_flag(self):
        payload = record("tde11-written-000001")
        payload["metadata"]["hard_case_types"] = ["prompt_injection"]
        payload["metadata"]["adversarial"] = False
        self.write(payload)
        findings = production_findings(self.root)
        self.assertTrue(any(item.code == "prompt_injection_must_be_adversarial" for item in findings))

    def test_next_batch_allocations_match_requested_size(self):
        plan = next_batch_plan(self.root, phase="pilot", count=17)
        self.assertEqual(sum(plan["modality"].values()), 17)
        self.assertEqual(sum(plan["grade"].values()), 17)
        self.assertEqual(sum(plan["response_quality"].values()), 17)

    def test_verified_needs_review_is_exported_as_gold_escalation(self):
        payload = record("tde11-written-000001")
        payload["gold_evaluation"]["needs_review"] = True
        payload["gold_evaluation"]["review_reason"] = "Rubrik için gerekli kanıt eksik."
        payload["metadata"]["review_count"] = 2
        payload["metadata"]["hard_case_types"] = ["missing_evidence"]
        self.write(payload)

        self.assertFalse(any(item.level == "error" for item in production_findings(self.root)))
        output, count = export_sft_curated(self.root, split="train")
        self.assertEqual(count, 1)
        row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
        assistant = json.loads(row["messages"][2]["content"])
        user = json.loads(row["messages"][1]["content"])
        self.assertTrue(assistant["needs_review"])
        self.assertNotIn("task_id", user["task"])
        self.assertEqual(row["metadata"]["task_id"], "task-1")

    def test_question_coverage_uses_exact_task_and_family(self):
        self.write(record("tde11-written-000001"))
        second = record("tde11-written-000002")
        second["metadata"]["subject_group_id"] = "student-2"
        self.write(second)
        report = production_report(self.root, phase="pilot")
        self.assertEqual(report["coverage"]["exact_tasks"]["unique"], 1)
        self.assertEqual(report["coverage"]["exact_tasks"]["in_range"], 1)
        self.assertEqual(report["coverage"]["question_families"]["unique"], 1)


if __name__ == "__main__":
    unittest.main()
