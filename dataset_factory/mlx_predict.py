from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import repo_root
from .production import export_sft_curated


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model çıktısında JSON nesnesi bulunamadı")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Model çıktısındaki JSON nesne olmalıdır")
    return payload


def evaluation_to_prediction(record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    needs_review = payload.get("needs_review")
    if not isinstance(needs_review, bool):
        raise ValueError("needs_review boolean olmalıdır")

    criterion_scores: dict[str, float] = {}
    direct = payload.get("criterion_scores")
    if isinstance(direct, dict):
        for key, value in direct.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"criterion_scores.{key} sayısal olmalıdır")
            criterion_scores[str(key)] = float(value)
    else:
        results = payload.get("criterion_results")
        if not isinstance(results, list) or not results:
            raise ValueError("criterion_results dolu liste veya criterion_scores nesnesi olmalıdır")
        for item in results:
            if not isinstance(item, dict):
                raise ValueError("criterion_results öğeleri nesne olmalıdır")
            criterion_id = item.get("criterion_id")
            score = item.get("score")
            if not isinstance(criterion_id, str) or not criterion_id:
                raise ValueError("criterion_id zorunludur")
            if criterion_id in criterion_scores:
                raise ValueError(f"Duplicate criterion_id: {criterion_id}")
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                raise ValueError(f"{criterion_id} score sayısal olmalıdır")
            criterion_scores[criterion_id] = float(score)

    if not criterion_scores:
        raise ValueError("criterion_scores boş olamaz")
    return {"id": record_id, "criterion_scores": criterion_scores, "needs_review": needs_review}


def _iter_prompts(root: Path, split: str):
    source, _ = export_sft_curated(root, split=split)
    with source.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            row = json.loads(raw)
            record_id = row.get("id")
            messages = row.get("messages")
            if not isinstance(record_id, str) or not record_id:
                raise ValueError(f"{source}:{line_number} id eksik")
            if not isinstance(messages, list) or len(messages) < 3:
                raise ValueError(f"{source}:{line_number} messages beklenen chat yapısında değil")
            if messages[-1].get("role") != "assistant":
                raise ValueError(f"{source}:{line_number} son mesaj assistant değil")
            yield record_id, messages[:-1]


def run_mlx_predictions(
    root: Path,
    *,
    split: str,
    model_repo: str,
    adapter_path: str | None,
    output: Path,
    max_tokens: int = 700,
    limit: int | None = None,
) -> tuple[int, int]:
    try:
        from mlx_lm import generate, load
    except ImportError as exc:  # pragma: no cover - yalnız Apple Silicon çalışma ortamında
        raise RuntimeError('MLX-LM kurulu değil. `python -m pip install "mlx-lm[train]"` çalıştırın.') from exc

    model, tokenizer = load(model_repo, adapter_path=adapter_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    error_path = output.with_suffix(output.suffix + ".errors.jsonl")
    success = 0
    errors = 0

    with output.open("w", encoding="utf-8") as out, error_path.open("w", encoding="utf-8") as err:
        for index, (record_id, messages) in enumerate(_iter_prompts(root, split)):
            if limit is not None and index >= limit:
                break
            prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
            raw = generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)
            try:
                payload = extract_json_object(raw)
                prediction = evaluation_to_prediction(record_id, payload)
            except Exception as exc:
                err.write(json.dumps({"id": record_id, "error": str(exc), "raw": raw}, ensure_ascii=False) + "\n")
                errors += 1
                continue
            out.write(json.dumps(prediction, ensure_ascii=False, separators=(",", ":")) + "\n")
            success += 1

    if errors == 0:
        error_path.unlink(missing_ok=True)
    return success, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MLX-LM modeliyle frozen pilot prediction JSONL üret.")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--split", choices=["validation", "test"], default="validation")
    parser.add_argument("--model", default="mlx-community/Qwen3-4B-4bit")
    parser.add_argument("--adapter-path")
    parser.add_argument("--output", type=Path, default=Path("reports/pilot-qwen3-4b/validation-predictions.jsonl"))
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--unlock-test", action="store_true", help="Mühürlü test splitine erişimi bilinçli olarak aç.")
    args = parser.parse_args(argv)

    if args.split == "test" and not args.unlock_test:
        parser.error("test split mühürlüdür; yalnız final checkpoint seçildikten sonra --unlock-test ile açılabilir")
    if args.max_tokens <= 0:
        parser.error("--max-tokens 0'dan büyük olmalıdır")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit 0'dan büyük olmalıdır")

    root = args.root.resolve() if args.root else repo_root()
    output = args.output if args.output.is_absolute() else root / args.output
    adapter = args.adapter_path
    if adapter and not Path(adapter).is_absolute():
        adapter = str(root / adapter)

    success, errors = run_mlx_predictions(
        root,
        split=args.split,
        model_repo=args.model,
        adapter_path=adapter,
        output=output,
        max_tokens=args.max_tokens,
        limit=args.limit,
    )
    print(f"prediction={success} parse_error={errors} -> {output.relative_to(root) if output.is_relative_to(root) else output}")
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
