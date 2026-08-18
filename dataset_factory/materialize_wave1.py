from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path

from .core import dump_json, load_json, repo_root

BATCH_DIR = Path("dataset/candidates/pilot-wave-1")
FAMILY_FILES = (
    "g09-poetry-theme.json",
    "g10-narrator-viewpoint.json",
    "g11-speaking-character.json",
    "g12-listening-inference.json",
)

SECOND_PASS_IDS = {
    "a1-13", "a2-12", "b1-13", "b2-10", "b2-12",
    "c1-13", "c2-10", "c2-12", "d1-12", "d1-13",
    "a2-11", "b2-11", "c2-11", "d2-11",
    "a1-09", "a2-04", "a2-05", "b1-04", "b1-05", "b1-09",
    "b2-03", "b2-07", "c1-04", "c1-05", "c1-07", "c2-03",
    "c2-04", "d1-04", "d2-03", "d2-08",
}

AUDIO_ONLY_SOURCES = {"audio_delivery", "teacher_observation"}
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


def _family_recalibration(root: Path, family_file: str) -> dict[str, dict]:
    path = root / BATCH_DIR / "recalibration" / family_file
    return _overrides_by_id(load_json(path)) if path.exists() else {}


def _ai_review_overrides(root: Path) -> dict[str, dict]:
    path = root / BATCH_DIR / "recalibration" / "ai-review-phase-a-overrides.json"
    return _overrides_by_id(load_json(path)) if path.exists() else {}


def _drop_unobservable_speaking_criteria(criteria: list[dict], modality: str) -> list[dict]:
    if modality != "speaking":
        return copy.deepcopy(criteria)
    kept: list[dict] = []
    for criterion in criteria:
        sources = set(criterion.get("evidence_sources") or [])
        if sources.intersection(AUDIO_ONLY_SOURCES):
            continue
        kept.append(copy.deepcopy(criterion))
    return kept


def _final_score_map(
    source_criteria: list[dict],
    response: dict,
    recalibration: dict | None,
    ai_review: dict | None,
) -> dict[str, float]:
    raw_scores = response.get("scores") or []
    scores = {
        criterion["criterion_id"]: raw_scores[index]
        for index, criterion in enumerate(source_criteria)
        if index < len(raw_scores)
    }
    if recalibration:
        scores.update(recalibration.get("scores") or {})
        scores.update(recalibration.get("content_scores") or {})
    if ai_review:
        scores.update(ai_review.get("final_scores") or {})
    return scores


def _effective_text(response: dict, recalibration: dict | None, ai_review: dict | None) -> str:
    text = str(response.get("text") or "")
    if recalibration and "text_override" in recalibration:
        text = str(recalibration["text_override"])
    if ai_review and "text_override" in ai_review:
        text = str(ai_review["text_override"])
    return text.strip()


def _effective_quality(response: dict, recalibration: dict | None, ai_review: dict | None) -> str:
    quality = str(response.get("response_quality") or "mid_partial")
    if recalibration and recalibration.get("effective_response_quality"):
        quality = str(recalibration["effective_response_quality"])
    if ai_review and ai_review.get("effective_response_quality"):
        quality = str(ai_review["effective_response_quality"])
    return quality


def _effective_hard_cases(response: dict, ai_review: dict | None) -> list[str]:
    hard_cases = list(response.get("hard_case_types") or [])
    if ai_review and "hard_case_types_override" in ai_review:
        hard_cases = list(ai_review.get("hard_case_types_override") or [])
    return hard_cases


def _review_target(response: dict, ai_review: dict | None) -> tuple[bool, str | None]:
    needs_review = bool(response.get("needs_review", False))
    review_reason = response.get("review_reason")
    if ai_review and "needs_review" in ai_review:
        needs_review = bool(ai_review["needs_review"])
        review_reason = ai_review.get("review_reason")
    if not needs_review:
        review_reason = None
    return needs_review, review_reason


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
    if any(token in cid for token in ("evidence", "textual", "supporting")):
        chosen = parts[:2]
    elif any(token in cid for token in ("explanation", "effect", "interpretation")):
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
        return "Mevcut kanıtın güvenilirliği kesin puanlama için yeterli değildir; ek doğrulama gerekir."
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


def build_wave1_records(root: Path) -> list[dict]:
    ai_overrides = _ai_review_overrides(root)
    serial_by_modality: Counter[str] = Counter()
    records: list[dict] = []

    for family_file in FAMILY_FILES:
        family = load_json(root / BATCH_DIR / family_file)
        recalibrations = _family_recalibration(root, family_file)
        modality = str(family["modality"])
        grade = int(family["grade"])
        source_rubric = family["rubric"]
        source_criteria = source_rubric["criteria"]
        canonical_criteria = _drop_unobservable_speaking_criteria(source_criteria, modality)
        canonical_ids = {item["criterion_id"] for item in canonical_criteria}

        rubric = copy.deepcopy(source_rubric)
        rubric["criteria"] = canonical_criteria
        if modality == "speaking" and len(canonical_criteria) != len(source_criteria):
            rubric["rubric_id"] = f"{rubric['rubric_id']}-transcript"
            rubric["version"] = "1.1"

        max_score = sum(float(item["max_score"]) for item in canonical_criteria)

        for task in family["tasks"]:
            for response in task["responses"]:
                candidate_id = str(response["candidate_id"])
                recal = recalibrations.get(candidate_id)
                ai_review = ai_overrides.get(candidate_id)
                text = _effective_text(response, recal, ai_review)
                quality = _effective_quality(response, recal, ai_review)
                hard_cases = _effective_hard_cases(response, ai_review)
                score_map = _final_score_map(source_criteria, response, recal, ai_review)
                score_map = {key: float(value) for key, value in score_map.items() if key in canonical_ids}
                needs_review, review_reason = _review_target(response, ai_review)

                criterion_results: list[dict] = []
                for criterion in canonical_criteria:
                    cid = criterion["criterion_id"]
                    if cid not in score_map:
                        raise ValueError(f"{candidate_id}: {cid} için final puan bulunamadı")
                    score = score_map[cid]
                    criterion_results.append(
                        {
                            "criterion_id": cid,
                            "score": score,
                            "evidence": _evidence_for(text, cid, score),
                            "justification": _justification(criterion, score),
                        }
                    )

                total_score = sum(float(item["score"]) for item in criterion_results)
                serial_by_modality[modality] += 1
                record_id = _record_id(grade, modality, serial_by_modality[modality])

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
                            "tags": sorted(set((family.get("tags") or []) + ["synthetic", "pilot-wave-1"])),
                            "pii_reviewed": True,
                            "subject_group_id": None,
                            "exam_family": family.get("exam_family"),
                            "question_family": family.get("question_family"),
                            "provenance": "synthetic",
                            "verification_source": "ai",
                            "response_quality": quality,
                            "hard_case_types": hard_cases,
                            "adversarial": bool(response.get("adversarial", False)),
                            "review_count": 2 if candidate_id in SECOND_PASS_IDS else 1,
                            "adjudicated": False,
                        },
                    }
                )
    return records


def _assert_wave1_invariants(records: list[dict]) -> None:
    if len(records) != 100:
        raise ValueError(f"Wave 1 tam 100 kayıt üretmelidir; bulunan={len(records)}")
    modality = Counter(item["modality"] for item in records)
    grade = Counter(str(item["grade"]) for item in records)
    qualities = Counter(item["metadata"]["response_quality"] for item in records)
    expected_modality = {"written": 50, "speaking": 25, "listening": 25}
    expected_grade = {"9": 25, "10": 25, "11": 25, "12": 25}
    if dict(modality) != expected_modality:
        raise ValueError(f"Modalite dağılımı bozuldu: {dict(modality)}")
    if dict(grade) != expected_grade:
        raise ValueError(f"Sınıf dağılımı bozuldu: {dict(grade)}")
    if set(qualities) - ALLOWED_QUALITIES:
        raise ValueError(f"Desteklenmeyen final response_quality bulundu: {sorted(set(qualities) - ALLOWED_QUALITIES)}")
    if sum(qualities.values()) != 100:
        raise ValueError("Final response_quality sınıflaması 100 kaydın tamamını kapsamalıdır")
    if sum(item["gold_evaluation"]["needs_review"] for item in records) != 1:
        raise ValueError("Wave 1 ikinci AI review sonrası tam 1 genuine needs_review içermelidir")
    if sum(item["metadata"]["review_count"] >= 2 for item in records) != 30:
        raise ValueError("Wave 1 tam 30 ikinci-geçiş AI review kaydı içermelidir")
    if any(
        set(c.get("evidence_sources") or []).intersection(AUDIO_ONLY_SOURCES)
        for record in records if record["modality"] == "speaking"
        for c in record["rubric"]["criteria"]
    ):
        raise ValueError("Sentetik speaking canonical kayıtta audio-only criterion kaldı")


def materialize_wave1(root: Path, *, overwrite: bool = False) -> list[Path]:
    records = build_wave1_records(root)
    _assert_wave1_invariants(records)
    written: list[Path] = []
    for record in records:
        path = root / "dataset" / "records" / record["modality"] / f"{record['id']}.json"
        if path.exists() and not overwrite:
            raise FileExistsError(f"Kayıt zaten var: {path.relative_to(root)}")
        dump_json(path, record)
        written.append(path)

    modality = Counter(item["modality"] for item in records)
    grade = Counter(str(item["grade"]) for item in records)
    quality = Counter(item["metadata"]["response_quality"] for item in records)
    hard_case_records = sum(bool(item["metadata"]["hard_case_types"]) for item in records)
    adversarial_records = sum(item["metadata"]["adversarial"] for item in records)
    needs_review_records = sum(item["gold_evaluation"]["needs_review"] for item in records)

    manifest_path = root / BATCH_DIR / "manifest.json"
    manifest = load_json(manifest_path)
    manifest.update(
        {
            "status": "materialized_ai_verified",
            "candidate_records": 100,
            "canonical_records": 100,
            "ai_verified_records": 100,
            "ai_verified_records_pending_materialization": 0,
            "teacher_verified_records": 0,
            "final_needs_review_records": needs_review_records,
            "second_pass_ai_review_records": 30,
            "canonical_materialized_at": "2026-08-18",
            "canonical_policy": "candidate -> recalibration -> AI review -> ai_verified canonical",
            "canonical_distribution": {
                "modality": dict(sorted(modality.items())),
                "grade": dict(sorted(grade.items())),
                "response_quality": dict(sorted(quality.items())),
                "hard_case_records": hard_case_records,
                "adversarial_records": adversarial_records,
                "needs_review_records": needs_review_records,
            },
            "materialized_blocks": [
                "g09-poetry-theme",
                "g10-narrator-viewpoint",
                "g11-speaking-character",
                "g12-listening-inference",
            ],
            "next_action": "Run validate + production + leakage gates, then begin Wave 2.",
        }
    )
    dump_json(manifest_path, manifest)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pilot Wave 1 adaylarını canonical ai_verified kayıtlara materialize eder.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root()
    paths = materialize_wave1(root, overwrite=args.overwrite)
    print(f"Materialized {len(paths)} Wave 1 canonical record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
