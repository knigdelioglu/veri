from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset_factory.pilot_mlx_runner import build_lock_payload, verify_lock


class PilotMlxRunnerLockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        experiment = self.root / "experiments" / "pilot-qwen3-4b-mlx"
        reports = self.root / "reports" / "pilot-qwen3-4b"
        adapter = experiment / "adapters"
        experiment.mkdir(parents=True)
        reports.mkdir(parents=True)
        adapter.mkdir(parents=True)

        (experiment / "experiment.json").write_text('{"experiment":"x"}\n', encoding="utf-8")
        (experiment / "lora.yaml").write_text("model: x\n", encoding="utf-8")
        (adapter / "adapter_config.json").write_text('{"fine_tune_type":"lora"}\n', encoding="utf-8")
        (adapter / "adapters.safetensors").write_bytes(b"fake-adapter-weights")
        (reports / "base-validation.json").write_text('{"score":1}\n', encoding="utf-8")
        (reports / "qlora-validation.json").write_text('{"score":2}\n', encoding="utf-8")
        self.adapter = adapter

    def tearDown(self):
        self.tmp.cleanup()

    def test_lock_verifies_unchanged_configuration(self):
        lock = build_lock_payload(self.root, self.adapter)
        resolved = verify_lock(self.root, lock)
        self.assertEqual(resolved, self.adapter)
        self.assertFalse(lock["test_opened"])
        self.assertEqual(lock["mlx_lm_version"], "0.31.3")

    def test_lock_detects_adapter_mutation(self):
        lock = build_lock_payload(self.root, self.adapter)
        (self.adapter / "adapters.safetensors").write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "adapter_weights"):
            verify_lock(self.root, lock)

    def test_lock_detects_validation_report_mutation(self):
        lock = build_lock_payload(self.root, self.adapter)
        report = self.root / "reports" / "pilot-qwen3-4b" / "qlora-validation.json"
        report.write_text(json.dumps({"score": 999}), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "qlora_validation_report"):
            verify_lock(self.root, lock)


if __name__ == "__main__":
    unittest.main()
