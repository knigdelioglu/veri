from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .core import load_records, repo_root


def _safe_div(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: each prediction must be a JSON object")
        rows.append(row)
    return rows


def _normalize_prediction(row: dict) -> dict:
    record_id = row.get("id")
    if not isinstance(record_id, str) or not record_id:
        raise ValueError("prediction.id must be a non-empty string")
    needs_review = row.get("needs_review")
    if not isinstance(needs_review, bool):
        raise ValueError(f"{record_id}: needs_review must be boolean")
    criterion_scores = row.get("criterion_scores")
    if not isinstance(criterion_scores, dict):
        raise ValueError(f"{record_id}: criterion_scores must be an object")
    normalized: dict[str, float] = {}
    for criterion_id, value in criterion_scores.items():
        if not isinstance(criterion_id, str) or not criterion_id:
            raise ValueError(f"{record_id}: criterion score keys must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{record_id}/{criterion_id}: score must be a finite number")
        normalized[criterion_id] = float(value)
    return {"id": record_id, "needs_review": needs_review, "criterion_scores": normalized}


def _load_gold(root: Path, split: str) -> dict[str, dict]:
    gold: dict[str, dict] = {}
    for _, record in load_records(root):
        if record.get("metadata", {}).get("split") == split:
            gold[record["id"]] = record
    return gold


def _validate_prediction_against_gold(prediction: dict, gold: dict) -> None:
    record_id = gold["id"]
    criteria = {c["criterion_id"]: c for c in gold["rubric"]["criteria"]}
    predicted_ids = set(prediction["criterion_scores"])
    expected_ids = set(criteria)
    if predicted_ids != expected_ids:
        missing = sorted(expected_ids - predicted_ids)
        extra = sorted(predicted_ids - expected_ids)
        parts = []
        if missing:
            parts.append(f"missing={','.join(missing)}")
        if extra:
            parts.append(f"extra={','.join(extra)}")
        raise ValueError(f"{record_id}: criterion_scores mismatch ({'; '.join(parts)})")
    for criterion_id, score in prediction["criterion_scores"].items():
        max_score = float(criteria[criterion_id]["max_score"])
        if score < 0 or score > max_score:
            raise ValueError(f"{record_id}/{criterion_id}: score {score:g} outside 0..{max_score:g}")


def _review_counts(records: Iterable[tuple[dict, dict]]) -> dict:
    tp = fp = fn = tn = 0
    for gold, prediction in records:
        expected = gold["gold_evaluation"]["needs_review"] is True
        predicted = prediction["needs_review"] is True
        if expected and predicted:
            tp += 1
        elif not expected and predicted:
            fp += 1
        elif expected and not predicted:
            fn += 1
        else:
            tn += 1
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = None if precision is None or recall is None or (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": _safe_div(tp + tn, tp + fp + fn + tn),
    }


def _slice_metrics(records: list[tuple[dict, dict]]) -> dict:
    criterion_count = 0
    criterion_exact = 0
    criterion_within_one = 0
    criterion_abs_error = 0.0
    total_count = 0
    total_exact = 0
    total_abs_error = 0.0
    total_normalized_abs_error = 0.0
    resolvable_records = 0

    for gold, prediction in records:
        # A gold escalation means the correct behavior is to ask for review. Its stored
        # criterion scores are provisional and therefore excluded from score agreement.
        if gold["gold_evaluation"]["needs_review"] is True:
            continue
        resolvable_records += 1
        gold_results = {item["criterion_id"]: float(item["score"]) for item in gold["gold_evaluation"]["criterion_results"]}
        predicted_total = 0.0
        gold_total = float(gold["gold_evaluation"]["total_score"])
        for criterion_id, gold_score in gold_results.items():
            pred_score = float(prediction["criterion_scores"][criterion_id])
            error = abs(pred_score - gold_score)
            criterion_count += 1
            criterion_abs_error += error
            criterion_exact += int(error <= 1e-9)
            criterion_within_one += int(error <= 1.0 + 1e-9)
            predicted_total += pred_score
        total_error = abs(predicted_total - gold_total)
        total_count += 1
        total_abs_error += total_error
        total_normalized_abs_error += total_error / float(gold["gold_evaluation"]["max_score"] or 1)
        total_exact += int(total_error <= 1e-9)

    return {
        "records": len(records),
        "resolvable_records": resolvable_records,
        "criterion_items": criterion_count,
        "criterion_exact_rate": _safe_div(criterion_exact, criterion_count),
        "criterion_within_1_rate": _safe_div(criterion_within_one, criterion_count),
        "criterion_mae": _safe_div(criterion_abs_error, criterion_count),
        "total_exact_rate": _safe_div(total_exact, total_count),
        "total_mae": _safe_div(total_abs_error, total_count),
        "total_normalized_mae": _safe_div(total_normalized_abs_error, total_count),
        "needs_review": _review_counts(records),
    }


def evaluate_predictions(root: Path, predictions_path: Path, *, split: str, strict: bool = True) -> dict:
    gold = _load_gold(root, split)
    if not gold:
        raise ValueError(f"No canonical records found for split={split}")

    rows = [_normalize_prediction(row) for row in _read_jsonl(predictions_path)]
    predictions: dict[str, dict] = {}
    for row in rows:
        if row["id"] in predictions:
            raise ValueError(f"Duplicate prediction id: {row['id']}")
        predictions[row["id"]] = row

    unknown = sorted(set(predictions) - set(gold))
    missing = sorted(set(gold) - set(predictions))
    if unknown:
        raise ValueError(f"Predictions contain ids outside split={split}: {', '.join(unknown[:10])}")
    if strict and missing:
        raise ValueError(f"Missing {len(missing)} predictions for split={split}; first: {', '.join(missing[:10])}")

    evaluated_ids = sorted(set(gold) & set(predictions))
    pairs: list[tuple[dict, dict]] = []
    for record_id in evaluated_ids:
        prediction = predictions[record_id]
        record = gold[record_id]
        _validate_prediction_against_gold(prediction, record)
        pairs.append((record, prediction))

    by_modality: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    by_grade: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    by_quality: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    by_family: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    by_hard_case_type: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    hard_case: list[tuple[dict, dict]] = []
    adversarial: list[tuple[dict, dict]] = []

    for pair in pairs:
        record, _ = pair
        metadata = record["metadata"]
        by_modality[str(record["modality"])].append(pair)
        by_grade[str(record["grade"])].append(pair)
        by_quality[str(metadata["response_quality"])].append(pair)
        by_family[str(metadata["question_family"])].append(pair)
        hard_types = metadata.get("hard_case_types") or []
        if hard_types:
            hard_case.append(pair)
            for hard_type in hard_types:
                by_hard_case_type[str(hard_type)].append(pair)
        if metadata.get("adversarial") is True:
            adversarial.append(pair)

    return {
        "schema_version": "1.0",
        "split": split,
        "coverage": {
            "gold_records": len(gold),
            "prediction_records": len(predictions),
            "evaluated_records": len(pairs),
            "missing_records": len(missing),
            "unknown_records": len(unknown),
            "strict": strict,
        },
        "scoring_policy": {
            "score_metrics_exclude_gold_needs_review": True,
            "needs_review_metrics_include_all_records": True,
            "predicted_total_is_sum_of_criterion_scores": True,
        },
        "overall": _slice_metrics(pairs),
        "by_modality": {key: _slice_metrics(value) for key, value in sorted(by_modality.items())},
        "by_grade": {key: _slice_metrics(value) for key, value in sorted(by_grade.items())},
        "by_response_quality": {key: _slice_metrics(value) for key, value in sorted(by_quality.items())},
        "by_question_family": {key: _slice_metrics(value) for key, value in sorted(by_family.items())},
        "special_slices": {
            "hard_case": _slice_metrics(hard_case),
            "adversarial": _slice_metrics(adversarial),
        },
        "by_hard_case_type": {key: _slice_metrics(value) for key, value in sorted(by_hard_case_type.items())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate model rubric-grading predictions against a frozen canonical split")
    parser.add_argument("predictions", type=Path, help="JSONL predictions: id, criterion_scores, needs_review")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--split", choices=["train", "validation", "test"], default="validation")
    parser.add_argument("--allow-partial", action="store_true", help="Evaluate only provided in-split ids instead of requiring full split coverage")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root()
    predictions_path = args.predictions if args.predictions.is_absolute() else Path.cwd() / args.predictions
    report = evaluate_predictions(root, predictions_path, split=args.split, strict=not args.allow_partial)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = args.output if args.output.is_absolute() else Path.cwd() / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
