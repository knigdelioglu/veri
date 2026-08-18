from __future__ import annotations

import argparse
import copy
import re
from collections import Counter
from pathlib import Path

from .core import dump_json, load_json, repo_root


ALLOWED_QUALITIES = {
    "full_correct",
    "high_partial",
    "mid_partial",
    "low_partial",
    "incorrect",
    "blank_irrelevant",
    "borderline",
}


def _overrides_by_id(payload: dict) -> dict[str, dict]:
    return {
        item["candidate_id"]: item
        for item in payload.get("overrides", [])
        if isinstance(item, dict) and item.get("candidate_id")
    }


def _effective_text(response: dict, override: dict | None) -> str:
    text = str(response.get("text") or "")
    if override and "text_override" in override:
        text = str(override["text_override"])
    return text.strip()


def _effective_quality(response: dict, override: dict | None) -> str:
    quality = str(response.get("response_quality") or "mid_partial")
    if override and override.get("effective_response_quality"):
        quality = str(override["effective_response_quality"])
    return quality


def _effective_hard_cases(response: dict, override: dict | None) -> list[str]:
    hard_cases = list(response.get("hard_case_types") or [])
    if override and "hard_case_types_override" in override:
        hard_cases = list(override.get("hard_case_types_override") or [])
    return hard_cases


def _effective_review(response: dict, override: dict | None) -> tuple[bool, str | None]:
    needs_review = bool(response.get("needs_review", False))
    review_reason = response.get("review_reason")
    if override and "needs_review" in override:
        needs_review = bool(override["needs_review"])
        review_reason = override.get("review_reason")
    if not needs_review:
        review_reason = None
    return needs_review, review_reason


def _score_map(criteria: list[dict], response: dict, override: dict | None) -> dict[str, float]:
    raw_scores = response.get("scores") or []
    scores = {
        criterion["criterion_id"]: float(raw_scores[index])
        for index, criterion in enumerate(criteria)
        if index < len(raw_scores)
    }
    if override:
        for field in ("scores", "content_scores", "final_scores"):
            scores.update({key: float(value) for key, value in (override.get(field) or {}).items()})
    return scores


def _sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\s*/\s*", text) if part.strip()]
    return parts or [text]


def _clip(text: str, limit: int = 180) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _evidence_for(text: str, criterion_id: str, score: float) -> list[str]:
    if score <= 0 or not text:
        return []
    parts = _sentences(text)
    if not parts:
        return []
    cid = criterion_id.lower()
    if any(token in cid for token in ("evidence", "textual", "supporting", "detail")):
        chosen = parts[:2]
    elif any(token in cid for token in ("explanation", "effect", "function", "reasoning", "relationship", "inference")):
        chosen = [parts[-1]]
    elif any(token in cid for token in ("organization", "clarity")):
        chosen = parts[:2]
    else:
        chosen = [parts[0]]
    return [_clip(item) for item in chosen if item.strip()]


def _anchor_for_score(criterion: dict, score: float) -> dict | None:
    anchors = criterion.get("scoring_anchors") or []
    exact = [item for item in anchors if float(item.get("score", -1)) == float(score)]
    if exact:
        return exact[0]
    if not anchors:
        return None
    return min(anchors, key=lambda item: abs(float(item.get("score", 0)) - float(score)))


def _justification(criterion: dict, score: float) -> str:
    name = str(criterion.get("name") or criterion.get("criterion_id") or "Ölçüt")
    anchor = _anchor_for_score(criterion, score)
    if anchor and anchor.get("description"):
        return f"{name} için yanıt {score:g} puan düzeyindeki çıpayla uyumludur: {anchor['description']}"
    if score <= 0:
        return f"{name} açısından gerekli unsur yanıtta gösterilmemiştir."
    return f"{name} ölçütü mevcut öğrenci cevabına göre kısmen karşılanmıştır."


def _overall_feedback(total: float, maximum: float, needs_review: bool) -> str:
    if needs_review:
        return "Mevcut kanıt güvenilir bir final puanı için yeterli değildir; ek doğrulama gerekir."
    ratio = total / maximum if maximum else 0.0
    if ratio >= 0.999:
        return "Yanıt rubriğin temel beklentilerini tam olarak karşılıyor."
    if ratio >= 0.7:
        return "Yanıtın ana yönü doğru; bazı ölçütlerde sınırlı eksikler bulunuyor."
    if ratio >= 0.4:
        return "Yanıt kısmi başarı gösteriyor; kanıt, açıklama veya gerekçelendirmede belirgin eksikler var."
    if total > 0:
        return "Yanıtta sınırlı doğru unsurlar var; rubriğin temel beklentileri büyük ölçüde karşılanmıyor."
    return "Yanıt rubriğin temel beklentilerini karşılamıyor."


def _record_id(grade: int, modality: str, serial: int) -> str:
    return f"tde{grade:02d}-{modality}-{serial:06d}"


def _batch_dir(root: Path, batch: str) -> Path:
    path = root / "dataset" / "candidates" / batch
    if not (path / "manifest.json").exists():
        raise FileNotFoundError(f"Batch manifest bulunamadı: {path / 'manifest.json'}")
    return path


def build_batch_records(root: Path, *, batch: str) -> list[dict]:
    batch_dir = _batch_dir(root, batch)
    manifest = load_json(batch_dir / "manifest.json")
    override_path = manifest.get("ai_review_overrides")
    override_payload = load_json(batch_dir / str(override_path)) if override_path else {"overrides": [], "second_pass_ids": []}
    overrides = _overrides_by_id(override_payload)
    second_pass_ids = set(override_payload.get("second_pass_ids") or [])
    records: list[dict] = []

    for family_spec in manifest.get("families") or []:
        family_file = str(family_spec["file"])
        family = load_json(batch_dir / family_file)
        grade = int(family_spec["grade"])
        modality = str(family_spec["modality"])
        start = int(family_spec["record_id_start"])
        if int(family["grade"]) != grade or str(family["modality"]) != modality:
            raise ValueError(f"{family_file}: manifest grade/modality ile family uyuşmuyor")

        rubric = copy.deepcopy(family["rubric"])
        criteria = rubric.get("criteria") or []
        max_score = sum(float(item["max_score"]) for item in criteria)
        offset = 0

        for task in family.get("tasks") or []:
            for response in task.get("responses") or []:
                candidate_id = str(response["candidate_id"])
                override = overrides.get(candidate_id)
                text = _effective_text(response, override)
                quality = _effective_quality(response, override)
                hard_cases = _effective_hard_cases(response, override)
                needs_review, review_reason = _effective_review(response, override)
                scores = _score_map(criteria, response, override)
                if quality not in ALLOWED_QUALITIES:
                    raise ValueError(f"{candidate_id}: desteklenmeyen response_quality={quality}")

                criterion_results: list[dict] = []
                for criterion in criteria:
                    cid = criterion["criterion_id"]
                    if cid not in scores:
                        raise ValueError(f"{candidate_id}: {cid} için final puan bulunamadı")
                    score = float(scores[cid])
                    if score < 0 or score > float(criterion["max_score"]):
                        raise ValueError(f"{candidate_id}: {cid} puanı aralık dışında: {score}")
                    criterion_results.append(
                        {
                            "criterion_id": cid,
                            "score": score,
                            "evidence": _evidence_for(text, cid, score),
                            "justification": _justification(criterion, score),
                        }
                    )

                serial = start + offset
                offset += 1
                total_score = sum(float(item["score"]) for item in criterion_results)
                record_id = _record_id(grade, modality, serial)
                records.append(
                    {
                        "id": record_id,
                        "schema_version": "1.0",
                        "modality": modality,
                        "language": "tr",
                        "grade": grade,
                        "task": {
                            "task_id": task["task_id"],
                            "prompt": task["prompt"],
                            "context": task.get("context"),
                            "max_score": max_score,
                        },
                        "rubric": copy.deepcopy(rubric),
                        "student_response": {
                            "text": text,
                            "source": "manual",
                            "observations": [],
                        },
                        "gold_evaluation": {
                            "criterion_results": criterion_results,
                            "total_score": total_score,
                            "max_score": max_score,
                            "needs_review": needs_review,
                            "review_reason": review_reason,
                            "overall_feedback": _overall_feedback(total_score, max_score, needs_review),
                        },
                        "metadata": {
                            "status": "ai_verified",
                            "split": None,
                            "created_at": family.get("created_at", "2026-08-18"),
                            "tags": sorted(set((family.get("tags") or []) + ["synthetic", batch])),
                            "pii_reviewed": True,
                            "subject_group_id": None,
                            "exam_family": family.get("exam_family"),
                            "question_family": family.get("question_family"),
                            "provenance": "synthetic",
                            "verification_source": "ai",
                            "response_quality": quality,
                            "hard_case_types": hard_cases,
                            "adversarial": bool(response.get("adversarial", False)),
                            "review_count": 2 if candidate_id in second_pass_ids else 1,
                            "adjudicated": False,
                        },
                    }
                )

        expected_family_count = int(manifest.get("coverage", {}).get("answers_per_question_family", offset))
        if offset != expected_family_count:
            raise ValueError(f"{family_file}: beklenen {expected_family_count} cevap, bulunan {offset}")

    return records


def assert_manifest_invariants(records: list[dict], manifest: dict) -> None:
    expected_total = int(manifest["candidate_records"])
    if len(records) != expected_total:
        raise ValueError(f"Batch {expected_total} kayıt üretmeli; bulunan={len(records)}")
    if len({record["id"] for record in records}) != len(records):
        raise ValueError("Batch içinde duplicate canonical record id var")

    expected = manifest.get("distribution") or {}
    modality = Counter(item["modality"] for item in records)
    grade = Counter(str(item["grade"]) for item in records)
    quality = Counter(item["metadata"]["response_quality"] for item in records)
    if dict(modality) != expected.get("modality"):
        raise ValueError(f"Modalite dağılımı bozuldu: {dict(modality)}")
    if dict(grade) != expected.get("grade"):
        raise ValueError(f"Sınıf dağılımı bozuldu: {dict(grade)}")
    if dict(quality) != expected.get("response_quality"):
        raise ValueError(f"Cevap profili dağılımı bozuldu: {dict(quality)}")

    hard_case_count = sum(bool(item["metadata"]["hard_case_types"]) for item in records)
    adversarial_count = sum(item["metadata"]["adversarial"] for item in records)
    needs_review_count = sum(item["gold_evaluation"]["needs_review"] for item in records)
    dual_review_count = sum(item["metadata"]["review_count"] >= 2 for item in records)
    if hard_case_count != int(expected.get("hard_case_records", hard_case_count)):
        raise ValueError(f"Hard-case sayısı bozuldu: {hard_case_count}")
    if adversarial_count != int(expected.get("adversarial_records", adversarial_count)):
        raise ValueError(f"Adversarial sayısı bozuldu: {adversarial_count}")
    if needs_review_count != int(expected.get("genuine_needs_review_records", needs_review_count)):
        raise ValueError(f"needs_review sayısı bozuldu: {needs_review_count}")
    if dual_review_count != int(expected.get("second_pass_ai_review_records", dual_review_count)):
        raise ValueError(f"İkinci AI geçişi sayısı bozuldu: {dual_review_count}")


def materialize_batch(root: Path, *, batch: str, overwrite: bool = False) -> list[Path]:
    batch_dir = _batch_dir(root, batch)
    manifest_path = batch_dir / "manifest.json"
    manifest = load_json(manifest_path)
    records = build_batch_records(root, batch=batch)
    assert_manifest_invariants(records, manifest)

    written: list[Path] = []
    for record in records:
        path = root / "dataset" / "records" / record["modality"] / f"{record['id']}.json"
        if path.exists():
            if not overwrite:
                raise FileExistsError(f"Kayıt zaten var: {path.relative_to(root)}")
            existing = load_json(path)
            if batch not in set(existing.get("metadata", {}).get("tags") or []):
                raise FileExistsError(f"Overwrite koruması: {path.relative_to(root)} başka batch'e ait")
        dump_json(path, record)
        written.append(path)

    modality = Counter(item["modality"] for item in records)
    grade = Counter(str(item["grade"]) for item in records)
    quality = Counter(item["metadata"]["response_quality"] for item in records)
    hard_case_count = sum(bool(item["metadata"]["hard_case_types"]) for item in records)
    adversarial_count = sum(item["metadata"]["adversarial"] for item in records)
    needs_review_count = sum(item["gold_evaluation"]["needs_review"] for item in records)
    dual_review_count = sum(item["metadata"]["review_count"] >= 2 for item in records)

    manifest.update(
        {
            "status": "materialized_ai_verified",
            "canonical_records": len(records),
            "ai_verified_records": len(records),
            "ai_verified_records_pending_materialization": 0,
            "canonical_materialized_at": "2026-08-18",
            "canonical_distribution": {
                "modality": dict(sorted(modality.items())),
                "grade": dict(sorted(grade.items())),
                "response_quality": dict(sorted(quality.items())),
                "hard_case_records": hard_case_count,
                "adversarial_records": adversarial_count,
                "needs_review_records": needs_review_count,
                "second_pass_ai_review_records": dual_review_count,
            },
            "next_action": "Run veri check and cumulative pilot quota review before producing the next wave.",
        }
    )
    dump_json(manifest_path, manifest)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manifest tabanlı pilot candidate batch'ini canonical ai_verified kayıtlara materialize eder.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root()
    paths = materialize_batch(root, batch=args.batch, overwrite=args.overwrite)
    print(f"Materialized {len(paths)} canonical record from {args.batch}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
