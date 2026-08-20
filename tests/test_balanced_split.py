from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset_factory.balanced_split import assign_balanced_splits
from dataset_factory.production import check_leakage_curated


class BalancedSplitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "dataset" / "records" / "written").mkdir(parents=True)
        (self.root / "dataset" / "records" / "speaking").mkdir(parents=True)
        (self.root / "dataset" / "records" / "listening").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_family(self, family_index: int, *, modality: str, grade: int, size: int = 10) -> None:
        for index in range(size):
            rid = f"tde{grade:02d}-{modality}-{family_index:03d}{index:03d}"
            record = {
                "id": rid,
                "schema_version": "1.0",
                "modality": modality,
                "language": "tr",
                "grade": grade,
                "task": {"task_id": f"task-{family_index}-{index // 5}", "prompt": "Soru", "context": None, "max_score": 10},
                "rubric": {"rubric_id": f"r-{family_index}", "version": "1.0", "criteria": []},
                "student_response": {"text": "Yanıt", "source": "manual", "observations": []},
                "gold_evaluation": {"criterion_results": [], "total_score": 0, "max_score": 10, "needs_review": False, "review_reason": None, "overall_feedback": ""},
                "metadata": {
                    "status": "ai_verified",
                    "split": None,
                    "created_at": "2026-08-20",
                    "tags": [],
                    "pii_reviewed": True,
                    "subject_group_id": None,
                    "exam_family": f"exam-{family_index}",
                    "question_family": f"family-{family_index}",
                    "provenance": "synthetic",
                    "verification_source": "ai",
                    "response_quality": ("full_correct", "high_partial", "mid_partial", "low_partial", "incorrect")[index % 5],
                    "hard_case_types": [],
                    "adversarial": False,
                    "review_count": 1,
                    "adjudicated": False,
                },
            }
            path = self.root / "dataset" / "records" / modality / f"{rid}.json"
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    def test_balanced_split_is_deterministic_group_safe_and_near_target(self):
        modalities = ["written", "speaking", "listening"]
        grades = [9, 10, 11, 12]
        for family_index in range(12):
            self._write_family(
                family_index,
                modality=modalities[family_index % len(modalities)],
                grade=grades[family_index % len(grades)],
            )

        first = assign_balanced_splits(self.root, seed="balanced-test", rebalance=True)
        self.assertEqual(check_leakage_curated(self.root), [])
        self.assertEqual(sum(map(len, first.values())), 120)
        # Component size is 10, so each requested target should be reachable within one component.
        self.assertLessEqual(abs(len(first["train"]) - 96), 10)
        self.assertLessEqual(abs(len(first["validation"]) - 12), 10)
        self.assertLessEqual(abs(len(first["test"]) - 12), 10)

        family_split = {}
        for split, ids in first.items():
            for rid in ids:
                family = int(rid.split("-")[-1][:3])
                family_split.setdefault(family, set()).add(split)
        self.assertTrue(all(len(splits) == 1 for splits in family_split.values()))

        second = assign_balanced_splits(self.root, seed="balanced-test", rebalance=True)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
