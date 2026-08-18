from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset_factory.core import assign_splits, check_leakage, export_sft, validate_dataset


CANONICAL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id", "schema_version", "modality", "language", "grade", "task", "rubric", "student_response", "gold_evaluation", "metadata"],
    "properties": {
        "id": {"type": "string"},
        "schema_version": {"type": "string"},
        "modality": {"type": "string"},
        "language": {"type": "string"},
        "grade": {"type": "integer"},
        "task": {"type": "object"},
        "rubric": {"$ref": "rubric.schema.json"},
        "student_response": {"type": "object"},
        "gold_evaluation": {"type": "object"},
        "metadata": {"type": "object"},
    },
}

RUBRIC_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "rubric.schema.json",
    "type": "object",
}


def record(record_id: str, *, subject: str, exam: str, question: str) -> dict:
    return {
        "id": record_id,
        "schema_version": "1.0",
        "modality": "written",
        "language": "tr",
        "grade": 11,
        "task": {"prompt": "Soru", "context": None, "max_score": 10},
        "rubric": {
            "rubric_id": "r1",
            "version": "1.0",
            "criteria": [{
                "criterion_id": "c1",
                "name": "İçerik",
                "description": "Açıklama",
                "max_score": 10,
                "scoring_anchors": [
                    {"score": 0, "description": "Yok"},
                    {"score": 10, "description": "Tam"},
                ],
                "evidence_sources": ["response_text"],
            }],
        },
        "student_response": {"text": "Cevap", "source": "manual", "observations": []},
        "gold_evaluation": {
            "criterion_results": [{"criterion_id": "c1", "score": 8, "evidence": ["Cevap"], "justification": "Büyük ölçüde doğru."}],
            "total_score": 8,
            "max_score": 10,
            "needs_review": False,
            "review_reason": None,
            "overall_feedback": "İyi.",
        },
        "metadata": {
            "status": "teacher_verified",
            "split": None,
            "created_at": "2026-08-18",
            "tags": [],
            "pii_reviewed": True,
            "subject_group_id": subject,
            "exam_family": exam,
            "question_family": question,
            "provenance": "real_anonymized",
        },
    }


class DatasetFactoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "schemas").mkdir()
        (self.root / "schemas" / "canonical-record.schema.json").write_text(json.dumps(CANONICAL_SCHEMA), encoding="utf-8")
        (self.root / "schemas" / "rubric.schema.json").write_text(json.dumps(RUBRIC_SCHEMA), encoding="utf-8")
        (self.root / "dataset" / "records" / "written").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, payload: dict):
        path = self.root / "dataset" / "records" / "written" / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_semantic_validation_catches_total_mismatch(self):
        payload = record("tde11-written-000001", subject="s1", exam="e1", question="q1")
        payload["gold_evaluation"]["total_score"] = 3
        self.write(payload)
        findings = validate_dataset(self.root)
        self.assertTrue(any(item.code == "total_score_mismatch" for item in findings))

    def test_connected_groups_never_split(self):
        self.write(record("tde11-written-000001", subject="s1", exam="e1", question="q1"))
        self.write(record("tde11-written-000002", subject="s1", exam="e2", question="q2"))
        self.write(record("tde11-written-000003", subject="s3", exam="e2", question="q3"))
        assignments = assign_splits(self.root, seed="test")
        locations = {rid: split for split, ids in assignments.items() for rid in ids}
        self.assertEqual(locations["tde11-written-000001"], locations["tde11-written-000002"])
        self.assertEqual(locations["tde11-written-000002"], locations["tde11-written-000003"])
        self.assertEqual(check_leakage(self.root), [])

    def test_existing_split_is_preserved(self):
        first = record("tde11-written-000001", subject="s1", exam="e1", question="q1")
        first["metadata"]["split"] = "test"
        second = record("tde11-written-000002", subject="s1", exam="e2", question="q2")
        self.write(first)
        self.write(second)
        assignments = assign_splits(self.root, seed="different-seed")
        self.assertIn("tde11-written-000001", assignments["test"])
        self.assertIn("tde11-written-000002", assignments["test"])

    def test_benchmark_family_collision_blocks_split(self):
        benchmark = record("tde11-written-000001", subject="s-bench", exam="e1", question="q1")
        benchmark["metadata"]["split"] = "benchmark"
        candidate = record("tde11-written-000002", subject="s-bench", exam="e2", question="q2")
        self.write(benchmark)
        self.write(candidate)
        with self.assertRaises(ValueError):
            assign_splits(self.root, seed="test")

    def test_export_omits_needs_review(self):
        clean = record("tde11-written-000001", subject="s1", exam="e1", question="q1")
        clean["metadata"]["split"] = "train"
        review = record("tde11-written-000002", subject="s2", exam="e2", question="q2")
        review["metadata"]["split"] = "train"
        review["gold_evaluation"]["needs_review"] = True
        review["gold_evaluation"]["review_reason"] = "Öğretmen incelemesi."
        self.write(clean)
        self.write(review)
        output, count = export_sft(self.root, split="train")
        self.assertEqual(count, 1)
        lines = output.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["id"], "tde11-written-000001")


if __name__ == "__main__":
    unittest.main()
