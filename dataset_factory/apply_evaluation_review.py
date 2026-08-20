from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import dump_json, load_json, load_records, repo_root


def _anchor_description(criterion: dict, score: float) -> str:
    anchors = criterion.get("scoring_anchors") or []
    exact = [a for a in anchors if float(a.get("score", -999)) == float(score)]
    if exact:
        return str(exact[0].get("description") or "")
    if not anchors:
        return ""
    nearest = min(anchors, key=lambda a: abs(float(a.get("score", 0)) - float(score)))
    return str(nearest.get("description") or "")


def _feedback(record: dict) -> str:
    gold = record["gold_evaluation"]
    if gold.get("needs_review") is True:
        return "Mevcut girdi güvenilir bir final puanı için yeterli değildir; kaynak belirsizliği doğrulanmalıdır."
    ratio = float(gold["total_score"]) / float(gold["max_score"] or 1)
    if ratio >= 0.9:
        return "Yanıt rubriğin ölçütlerini güçlü ve tutarlı biçimde karşılıyor."
    if ratio >= 0.7:
        return "Yanıtın ana yönü güçlü; bazı ölçütlerde sınırlı eksikler bulunuyor."
    if ratio >= 0.4:
        return "Yanıt göreve kısmen yanıt veriyor; gerekçelendirme ve eksik ölçütler geliştirilmelidir."
    return "Yanıt rubriğin çoğu ölçütünü karşılamıyor; temel görev ve kanıt ilişkisi güçlendirilmelidir."


def apply_review(root: Path, review_path: Path) -> dict:
    review = load_json(review_path)
    scope = review.get("scope") or {}
    allowed_splits = set(scope.get("splits") or [])
    corrections = review.get("corrections") or {}

    loaded = load_records(root)
    by_id = {record["id"]: (path, record) for path, record in loaded}
    evaluation_ids = sorted(
        record_id
        for record_id, (_, record) in by_id.items()
        if record.get("metadata", {}).get("split") in allowed_splits
    )

    expected = int(scope.get("expected_records") or 0)
    if expected and len(evaluation_ids) != expected:
        raise ValueError(f"Evaluation review scope expected {expected} records, found {len(evaluation_ids)}")

    unknown = sorted(set(corrections) - set(by_id))
    if unknown:
        raise ValueError(f"Unknown correction ids: {', '.join(unknown)}")
    outside = sorted(set(corrections) - set(evaluation_ids))
    if outside:
        raise ValueError(f"Corrections outside evaluation splits: {', '.join(outside)}")

    changed_scores = 0
    changed_quality = 0
    for record_id in evaluation_ids:
        path, record = by_id[record_id]
        metadata = record["metadata"]
        metadata["review_count"] = max(2, int(metadata.get("review_count") or 0))

        correction = corrections.get(record_id)
        if correction:
            requested_scores = correction.get("scores") or {}
            criteria_by_id = {c["criterion_id"]: c for c in record["rubric"]["criteria"]}
            results_by_id = {r["criterion_id"]: r for r in record["gold_evaluation"]["criterion_results"]}
            if set(requested_scores) - set(criteria_by_id):
                invalid = sorted(set(requested_scores) - set(criteria_by_id))
                raise ValueError(f"{record_id} invalid criterion ids: {', '.join(invalid)}")

            for criterion_id, new_score in requested_scores.items():
                criterion = criteria_by_id[criterion_id]
                result = results_by_id[criterion_id]
                score = float(new_score)
                if not (0 <= score <= float(criterion["max_score"])):
                    raise ValueError(f"{record_id}/{criterion_id} score {score} outside criterion range")
                if float(result["score"]) != score:
                    changed_scores += 1
                result["score"] = score
                anchor = _anchor_description(criterion, score)
                result["justification"] = (
                    f"{criterion['name']} için ikinci AI değerlendirmesi {score:g}/{float(criterion['max_score']):g} puan verdi."
                    + (f" Rubrik çıpası: {anchor}" if anchor else "")
                )

            record["gold_evaluation"]["total_score"] = sum(
                float(item["score"]) for item in record["gold_evaluation"]["criterion_results"]
            )
            record["gold_evaluation"]["overall_feedback"] = _feedback(record)

            if "response_quality" in correction:
                if metadata.get("response_quality") != correction["response_quality"]:
                    changed_quality += 1
                metadata["response_quality"] = correction["response_quality"]

        dump_json(path, record)

    summary = {
        "review_id": review.get("review_id"),
        "records_reviewed": len(evaluation_ids),
        "records_with_declared_corrections": len(corrections),
        "criterion_scores_changed": changed_scores,
        "response_quality_changed": changed_quality,
        "all_evaluation_dual_reviewed": True,
    }
    output = root / "dataset" / "evaluation" / "pilot-evaluation-review-applied.json"
    dump_json(output, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply audited pilot evaluation second-pass corrections")
    parser.add_argument("--root", type=Path)
    parser.add_argument(
        "--review",
        type=Path,
        default=Path("dataset/evaluation/pilot-evaluation-review.json"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root()
    review_path = args.review if args.review.is_absolute() else root / args.review
    summary = apply_review(root, review_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
