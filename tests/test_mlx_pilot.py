from __future__ import annotations

import unittest

from dataset_factory.mlx_predict import evaluation_to_prediction, extract_json_object


class MlxPilotPredictionTest(unittest.TestCase):
    def test_extract_fenced_gold_evaluation_json(self):
        raw = '''```json
{"criterion_results":[{"criterion_id":"claim","score":3},{"criterion_id":"reasoning","score":2}],"needs_review":false}
```'''
        payload = extract_json_object(raw)
        prediction = evaluation_to_prediction("r1", payload)
        self.assertEqual(prediction, {
            "id": "r1",
            "criterion_scores": {"claim": 3.0, "reasoning": 2.0},
            "needs_review": False,
        })

    def test_accepts_direct_prediction_contract(self):
        prediction = evaluation_to_prediction(
            "r2",
            {"criterion_scores": {"evidence": 1, "clarity": 2.5}, "needs_review": True},
        )
        self.assertEqual(prediction["criterion_scores"], {"evidence": 1.0, "clarity": 2.5})
        self.assertTrue(prediction["needs_review"])

    def test_rejects_duplicate_criterion(self):
        with self.assertRaisesRegex(ValueError, "Duplicate criterion_id"):
            evaluation_to_prediction(
                "r3",
                {
                    "criterion_results": [
                        {"criterion_id": "claim", "score": 1},
                        {"criterion_id": "claim", "score": 2},
                    ],
                    "needs_review": False,
                },
            )

    def test_rejects_non_boolean_review(self):
        with self.assertRaisesRegex(ValueError, "needs_review boolean"):
            evaluation_to_prediction("r4", {"criterion_scores": {"claim": 1}, "needs_review": "false"})


if __name__ == "__main__":
    unittest.main()
