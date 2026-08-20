from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .core import repo_root
from .production import export_sft_curated


def _copy_chat_only(source: Path, target: Path) -> int:
    count = 0
    with source.open("r", encoding="utf-8") as src, target.open("w", encoding="utf-8") as dst:
        for line_number, raw in enumerate(src, start=1):
            if not raw.strip():
                continue
            row = json.loads(raw)
            messages = row.get("messages")
            if not isinstance(messages, list) or not messages:
                raise ValueError(f"{source}:{line_number} messages listesi yok veya boş")
            if messages[-1].get("role") != "assistant":
                raise ValueError(f"{source}:{line_number} son mesaj assistant olmalıdır")
            dst.write(json.dumps({"messages": messages}, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def prepare_mlx_pilot(root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)

    # Test seti eğitim dizininde hiçbir koşulda bulunmaz. Daha önce kalmış bir dosya
    # varsa temizlenir; sealed-test protokolü fiziksel dizin seviyesinde de korunur.
    stale_test = output / "test.jsonl"
    if stale_test.exists():
        stale_test.unlink()

    train_source, train_count = export_sft_curated(root, split="train")
    validation_source, validation_count = export_sft_curated(root, split="validation")

    train_written = _copy_chat_only(train_source, output / "train.jsonl")
    valid_written = _copy_chat_only(validation_source, output / "valid.jsonl")
    if train_written != train_count or valid_written != validation_count:
        raise ValueError("MLX veri sayıları curated SFT export sayılarıyla uyuşmuyor")

    freeze_path = root / "dataset" / "evaluation" / "pilot-evaluation-freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    expected = {
        "train": int(freeze["splits"]["train"]["records"]),
        "validation": int(freeze["splits"]["validation"]["records"]),
        "test": int(freeze["splits"]["test"]["records"]),
    }
    if train_written != expected["train"] or valid_written != expected["validation"]:
        raise ValueError(f"Frozen pilot sayıları uyuşmuyor: actual train={train_written} valid={valid_written}, expected={expected}")

    manifest = {
        "schema_version": "1.0",
        "purpose": "mlx-lm training input",
        "source_of_truth": "dataset/records",
        "freeze": "dataset/evaluation/pilot-evaluation-freeze.json",
        "train_records": train_written,
        "validation_records": valid_written,
        "sealed_test_records": expected["test"],
        "test_materialized_here": False,
        "format": "chat/messages JSONL",
        "extra_fields_stripped": True,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Frozen pilot için MLX-LM train/valid verisi hazırla; test setini mühürlü tut.")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("experiments/pilot-qwen3-4b-mlx/data"))
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root()
    output = args.output if args.output.is_absolute() else root / args.output
    manifest = prepare_mlx_pilot(root, output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
