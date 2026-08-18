from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from jsonschema import Draft202012Validator, FormatChecker


RECORD_GLOB = "dataset/records/*/*.json"
SUPPORTED_MODALITIES = {"written", "speaking", "listening"}
SUPPORTED_SPLITS = ("train", "validation", "test")

PII_PATTERNS = (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("telefon", re.compile(r"(?<!\d)(?:\+?90\s*)?(?:0?\s*)?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}(?!\d)")),
    ("tc_kimlik_etiketi", re.compile(r"\b(?:T\.?\s*C\.?\s*)?(?:kimlik|kimlik\s*no|tc\s*no)\b", re.IGNORECASE)),
    ("okul_numarasi_etiketi", re.compile(r"\b(?:okul|öğrenci)\s*(?:no|numara|numarası)\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str
    path: str | None = None

    def render(self) -> str:
        where = f" [{self.path}]" if self.path else ""
        return f"{self.level.upper():7} {self.code}: {self.message}{where}"


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "schemas" / "canonical-record.schema.json").exists():
            return candidate
    raise FileNotFoundError(
        "Repo kökü bulunamadı. Komutu schemas/canonical-record.schema.json bulunan repo içinde çalıştırın."
    )


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def iter_record_paths(root: Path) -> list[Path]:
    return sorted(root.glob(RECORD_GLOB))


def load_records(root: Path) -> list[tuple[Path, dict]]:
    return [(path, load_json(path)) for path in iter_record_paths(root)]


def _canonical_validator(root: Path) -> Draft202012Validator:
    canonical = load_json(root / "schemas" / "canonical-record.schema.json")
    rubric = load_json(root / "schemas" / "rubric.schema.json")
    canonical = json.loads(json.dumps(canonical))
    canonical["properties"]["rubric"] = rubric
    return Draft202012Validator(canonical, format_checker=FormatChecker())


def _flatten_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _flatten_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _flatten_strings(child)


def _find_pii(record: dict) -> list[str]:
    hits: set[str] = set()
    for text in _flatten_strings(record):
        for name, pattern in PII_PATTERNS:
            if pattern.search(text):
                hits.add(name)
    return sorted(hits)


def validate_record(
    root: Path,
    path: Path,
    record: dict,
    *,
    validator: Draft202012Validator | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    rel = str(path.relative_to(root))
    validator = validator or _canonical_validator(root)

    for error in sorted(validator.iter_errors(record), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        findings.append(Finding("error", "schema", f"{location}: {error.message}", rel))

    record_id = record.get("id")
    modality = record.get("modality")
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    task = record.get("task") if isinstance(record.get("task"), dict) else {}
    rubric = record.get("rubric") if isinstance(record.get("rubric"), dict) else {}
    gold = record.get("gold_evaluation") if isinstance(record.get("gold_evaluation"), dict) else {}
    response = record.get("student_response") if isinstance(record.get("student_response"), dict) else {}

    if isinstance(record_id, str) and path.stem != record_id:
        findings.append(Finding("error", "filename_id_mismatch", f"Dosya adı '{path.stem}', kayıt ID'si '{record_id}' olmalı.", rel))

    if modality in SUPPORTED_MODALITIES and path.parent.name != modality:
        findings.append(Finding("error", "modality_folder_mismatch", f"'{modality}' kaydı '{modality}/' klasöründe bulunmalı.", rel))

    criteria = rubric.get("criteria") if isinstance(rubric.get("criteria"), list) else []
    criterion_ids = [c.get("criterion_id") for c in criteria if isinstance(c, dict)]
    if len(criterion_ids) != len(set(criterion_ids)):
        findings.append(Finding("error", "duplicate_criterion_id", "Rubrikte yinelenen criterion_id var.", rel))

    results = gold.get("criterion_results") if isinstance(gold.get("criterion_results"), list) else []
    result_ids = [r.get("criterion_id") for r in results if isinstance(r, dict)]
    if len(result_ids) != len(set(result_ids)):
        findings.append(Finding("error", "duplicate_result_id", "Gold değerlendirmede yinelenen criterion_id var.", rel))

    if criteria and results and set(criterion_ids) != set(result_ids):
        missing = sorted(set(criterion_ids) - set(result_ids))
        extra = sorted(set(result_ids) - set(criterion_ids))
        findings.append(
            Finding(
                "error",
                "criterion_result_mismatch",
                f"Rubrik/sonuç ölçütleri eşleşmiyor. eksik={missing}, fazla={extra}",
                rel,
            )
        )

    criterion_by_id = {
        item.get("criterion_id"): item
        for item in criteria
        if isinstance(item, dict) and isinstance(item.get("criterion_id"), str)
    }
    for result in results:
        if not isinstance(result, dict):
            continue
        cid = result.get("criterion_id")
        score = result.get("score")
        criterion = criterion_by_id.get(cid)
        if criterion and isinstance(score, (int, float)):
            max_score = criterion.get("max_score")
            if isinstance(max_score, (int, float)) and score > max_score + 1e-9:
                findings.append(Finding("error", "criterion_score_overflow", f"{cid}: {score} > {max_score}", rel))

    rubric_max = sum(
        float(c.get("max_score", 0))
        for c in criteria
        if isinstance(c, dict) and isinstance(c.get("max_score"), (int, float))
    )
    task_max = task.get("max_score")
    gold_max = gold.get("max_score")
    if criteria and isinstance(task_max, (int, float)) and abs(rubric_max - float(task_max)) > 1e-9:
        findings.append(Finding("error", "rubric_task_max_mismatch", f"Rubrik toplamı {rubric_max:g}, task.max_score {task_max}.", rel))
    if isinstance(task_max, (int, float)) and isinstance(gold_max, (int, float)) and abs(float(task_max) - float(gold_max)) > 1e-9:
        findings.append(Finding("error", "task_gold_max_mismatch", f"task.max_score {task_max}, gold.max_score {gold_max}.", rel))

    result_total = sum(
        float(r.get("score", 0))
        for r in results
        if isinstance(r, dict) and isinstance(r.get("score"), (int, float))
    )
    total_score = gold.get("total_score")
    if results and isinstance(total_score, (int, float)) and abs(result_total - float(total_score)) > 1e-9:
        findings.append(Finding("error", "total_score_mismatch", f"Ölçüt toplamı {result_total:g}, total_score {total_score}.", rel))

    if isinstance(total_score, (int, float)) and isinstance(gold_max, (int, float)) and total_score > gold_max + 1e-9:
        findings.append(Finding("error", "total_score_overflow", f"total_score {total_score} > max_score {gold_max}.", rel))

    needs_review = gold.get("needs_review")
    review_reason = gold.get("review_reason")
    if needs_review is True and not (isinstance(review_reason, str) and review_reason.strip()):
        findings.append(Finding("error", "review_reason_required", "needs_review=true iken review_reason zorunludur.", rel))
    if needs_review is False and isinstance(review_reason, str) and review_reason.strip():
        findings.append(Finding("warning", "unexpected_review_reason", "needs_review=false iken review_reason dolu.", rel))

    if metadata.get("status") == "teacher_verified" and metadata.get("pii_reviewed") is not True:
        findings.append(Finding("error", "verified_without_pii_review", "teacher_verified kayıt pii_reviewed=true olmalıdır.", rel))

    pii_hits = _find_pii(record)
    if pii_hits:
        findings.append(Finding("warning", "possible_pii", f"Olası kişisel veri işaretleri: {', '.join(pii_hits)}", rel))

    observations = response.get("observations") if isinstance(response.get("observations"), list) else []
    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        sources = set(criterion.get("evidence_sources") or [])
        if sources.intersection({"audio_delivery", "teacher_observation"}) and not observations:
            findings.append(
                Finding(
                    "warning",
                    "missing_nontext_observation",
                    f"{criterion.get('criterion_id')}: metin dışı kanıt kaynağı tanımlı fakat student_response.observations boş.",
                    rel,
                )
            )

    return findings


def validate_dataset(root: Path, *, include_examples: bool = False) -> list[Finding]:
    validator = _canonical_validator(root)
    findings: list[Finding] = []
    seen_ids: dict[str, str] = {}

    paths = iter_record_paths(root)
    if include_examples:
        paths.extend(sorted((root / "examples").glob("*.json")))

    for path in paths:
        try:
            record = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(Finding("error", "invalid_json", str(exc), str(path.relative_to(root))))
            continue

        findings.extend(validate_record(root, path, record, validator=validator))
        rid = record.get("id")
        if isinstance(rid, str):
            previous = seen_ids.get(rid)
            if previous:
                findings.append(
                    Finding(
                        "error",
                        "duplicate_record_id",
                        f"'{rid}' ayrıca {previous} içinde kullanılıyor.",
                        str(path.relative_to(root)),
                    )
                )
            else:
                seen_ids[rid] = str(path.relative_to(root))

    return findings


def _union_find_components(records: list[dict]) -> list[list[dict]]:
    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    indexes: dict[tuple[str, str], int] = {}
    for idx, record in enumerate(records):
        metadata = record["metadata"]
        for field in ("subject_group_id", "exam_family", "question_family"):
            value = metadata.get(field)
            if not value:
                continue
            key = (field, str(value))
            if key in indexes:
                union(idx, indexes[key])
            else:
                indexes[key] = idx

    groups: dict[int, list[dict]] = defaultdict(list)
    for idx, record in enumerate(records):
        groups[find(idx)].append(record)
    return list(groups.values())


def _stable_unit(value: str, seed: str) -> float:
    digest = hashlib.sha256(f"{seed}:{value}".encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], "big")
    return integer / float(2**64)


def assign_splits(
    root: Path,
    *,
    train_ratio: float = 0.8,
    validation_ratio: float = 0.1,
    seed: str = "tde-v1",
) -> dict[str, list[str]]:
    if not (0 < train_ratio < 1):
        raise ValueError("train_ratio 0 ile 1 arasında olmalıdır.")
    if not (0 <= validation_ratio < 1):
        raise ValueError("validation_ratio 0 ile 1 arasında olmalıdır.")
    if train_ratio + validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio 1'den küçük olmalıdır.")

    loaded = load_records(root)
    eligible: list[tuple[Path, dict]] = []
    for path, record in loaded:
        metadata = record.get("metadata", {})
        if metadata.get("status") != "teacher_verified":
            continue
        if metadata.get("pii_reviewed") is not True:
            continue
        if metadata.get("split") == "benchmark":
            continue
        eligible.append((path, record))

    records = [record for _, record in eligible]
    components = _union_find_components(records)
    assignments: dict[str, list[str]] = {name: [] for name in SUPPORTED_SPLITS}
    split_by_id: dict[str, str] = {}

    benchmark_keys: set[tuple[str, str]] = set()
    for _, record in loaded:
        metadata = record.get("metadata", {})
        if metadata.get("split") != "benchmark":
            continue
        for field in ("subject_group_id", "exam_family", "question_family"):
            value = metadata.get(field)
            if value:
                benchmark_keys.add((field, str(value)))

    for record in records:
        metadata = record["metadata"]
        collisions = [
            f"{field}={value}"
            for field in ("subject_group_id", "exam_family", "question_family")
            if (value := metadata.get(field)) and (field, str(value)) in benchmark_keys
        ]
        if collisions:
            raise ValueError(
                f"{record['id']} benchmark ailesiyle çakışıyor: {', '.join(collisions)}. "
                "Kayıt split edilmedi."
            )

    train_cut = train_ratio
    validation_cut = train_ratio + validation_ratio

    for component in components:
        existing = {
            str(record["metadata"].get("split"))
            for record in component
            if record["metadata"].get("split") in SUPPORTED_SPLITS
        }
        if len(existing) > 1:
            ids = ", ".join(sorted(record["id"] for record in component))
            raise ValueError(
                f"Bağlı kayıt grubunda mevcut split çakışması var ({ids}): {', '.join(sorted(existing))}"
            )

        if existing:
            split = next(iter(existing))
        else:
            signature = "|".join(sorted(record["id"] for record in component))
            value = _stable_unit(signature, seed)
            split = "train" if value < train_cut else "validation" if value < validation_cut else "test"

        for record in component:
            split_by_id[record["id"]] = split
            assignments[split].append(record["id"])

    for path, record in eligible:
        split = split_by_id[record["id"]]
        record["metadata"]["split"] = split
        dump_json(path, record)

    for split, ids in assignments.items():
        ids.sort()
        manifest = {
            "schema_version": "1.0",
            "split": split,
            "seed": seed,
            "grouping_rule": "connected components over subject_group_id OR exam_family OR question_family",
            "record_ids": ids,
        }
        dump_json(root / "dataset" / "splits" / split / "manifest.json", manifest)

    return assignments


def check_leakage(root: Path) -> list[Finding]:
    loaded = load_records(root)
    findings: list[Finding] = []
    by_field: dict[str, dict[str, set[str]]] = {
        field: defaultdict(set)
        for field in ("subject_group_id", "exam_family", "question_family")
    }

    for path, record in loaded:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        split = metadata.get("split")
        if split not in (*SUPPORTED_SPLITS, "benchmark"):
            continue
        for field in by_field:
            value = metadata.get(field)
            if value:
                by_field[field][str(value)].add(str(split))

    for field, values in by_field.items():
        for value, splits in sorted(values.items()):
            if len(splits) > 1:
                findings.append(
                    Finding(
                        "error",
                        "split_leakage",
                        f"{field}='{value}' birden fazla split içinde: {', '.join(sorted(splits))}",
                    )
                )
    return findings


def _sft_system_prompt() -> str:
    return (
        "Sen Türk Dili ve Edebiyatı dersinde rubriğe bağlı değerlendirme yapan bir puanlama modelisin. "
        "Yalnız verilen görev, rubrik, öğrenci cevabı ve gözlemleri kullan. Cevapta bulunmayan bilgiyi uydurma; "
        "rubrikte olmayan ölçüt ekleme. Kanıt yetersizse needs_review=true kullan. "
        "Çıktıyı yalnızca verilen gold_evaluation yapısına uygun JSON olarak üret."
    )


def export_sft(root: Path, *, split: str) -> tuple[Path, int]:
    if split not in SUPPORTED_SPLITS:
        raise ValueError(f"split şu değerlerden biri olmalıdır: {', '.join(SUPPORTED_SPLITS)}")

    rows: list[dict] = []
    for _, record in load_records(root):
        metadata = record["metadata"]
        if metadata.get("split") != split:
            continue
        if metadata.get("status") != "teacher_verified" or metadata.get("pii_reviewed") is not True:
            continue
        if record["gold_evaluation"].get("needs_review") is True:
            continue

        user_payload = {
            "task": record["task"],
            "rubric": record["rubric"],
            "student_response": record["student_response"],
        }
        assistant_payload = record["gold_evaluation"]
        rows.append(
            {
                "id": record["id"],
                "messages": [
                    {"role": "system", "content": _sft_system_prompt()},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":"))},
                    {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False, separators=(",", ":"))},
                ],
                "metadata": {
                    "modality": record["modality"],
                    "grade": record["grade"],
                    "schema_version": record["schema_version"],
                    "rubric_id": record["rubric"]["rubric_id"],
                },
            }
        )

    output = root / "exports" / "sft" / f"{split}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return output, len(rows)


def dataset_stats(root: Path) -> dict:
    stats: dict[str, object] = {
        "total_records": 0,
        "by_modality": defaultdict(int),
        "by_status": defaultdict(int),
        "by_split": defaultdict(int),
        "teacher_verified_and_pii_reviewed": 0,
        "needs_review": 0,
    }
    for _, record in load_records(root):
        stats["total_records"] += 1
        stats["by_modality"][record.get("modality", "<missing>")] += 1
        metadata = record.get("metadata", {})
        stats["by_status"][metadata.get("status", "<missing>")] += 1
        stats["by_split"][metadata.get("split") or "unassigned"] += 1
        if metadata.get("status") == "teacher_verified" and metadata.get("pii_reviewed") is True:
            stats["teacher_verified_and_pii_reviewed"] += 1
        if record.get("gold_evaluation", {}).get("needs_review") is True:
            stats["needs_review"] += 1

    stats["by_modality"] = dict(sorted(stats["by_modality"].items()))
    stats["by_status"] = dict(sorted(stats["by_status"].items()))
    stats["by_split"] = dict(sorted(stats["by_split"].items()))
    return stats


def next_record_id(root: Path, *, grade: int, modality: str) -> str:
    if modality not in SUPPORTED_MODALITIES:
        raise ValueError(f"Desteklenmeyen modality: {modality}")
    prefix = f"tde{grade:02d}-{modality}-"
    max_number = 0
    for path in (root / "dataset" / "records" / modality).glob(f"{prefix}*.json"):
        match = re.fullmatch(re.escape(prefix) + r"(\d{6})", path.stem)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"{prefix}{max_number + 1:06d}"


def create_draft_record(
    root: Path,
    *,
    grade: int,
    modality: str,
    task_prompt: str,
    criteria: list[dict],
    response_text: str,
    response_source: str,
    task_context: str | None = None,
    record_id: str | None = None,
) -> Path:
    record_id = record_id or next_record_id(root, grade=grade, modality=modality)
    max_score = sum(float(item["max_score"]) for item in criteria)
    rubric_id = f"{record_id}-rubric"

    criterion_results = [
        {
            "criterion_id": item["criterion_id"],
            "score": 0,
            "evidence": [],
            "justification": "Taslak: öğretmen puanlaması bekleniyor.",
        }
        for item in criteria
    ]

    record = {
        "id": record_id,
        "schema_version": "1.0",
        "modality": modality,
        "language": "tr",
        "grade": grade,
        "task": {
            "prompt": task_prompt,
            "context": task_context,
            "max_score": max_score,
        },
        "rubric": {
            "rubric_id": rubric_id,
            "version": "1.0",
            "criteria": criteria,
        },
        "student_response": {
            "text": response_text,
            "source": response_source,
            "observations": [],
        },
        "gold_evaluation": {
            "criterion_results": criterion_results,
            "total_score": 0,
            "max_score": max_score,
            "needs_review": True,
            "review_reason": "Taslak kayıt: öğretmen gold puanlaması bekleniyor.",
            "overall_feedback": "",
        },
        "metadata": {
            "status": "draft",
            "split": None,
            "created_at": __import__("datetime").date.today().isoformat(),
            "tags": [],
            "pii_reviewed": False,
            "subject_group_id": None,
            "exam_family": None,
            "question_family": None,
            "provenance": "real_anonymized",
        },
    }
    path = root / "dataset" / "records" / modality / f"{record_id}.json"
    if path.exists():
        raise FileExistsError(path)
    dump_json(path, record)
    return path
