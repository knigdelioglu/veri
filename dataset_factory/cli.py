from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    SUPPORTED_MODALITIES,
    assign_splits,
    check_leakage,
    create_draft_record,
    dataset_stats,
    dump_json,
    load_json,
    repo_root,
    validate_dataset,
)
from .production import (
    HARD_CASE_TYPES,
    QUALITY_LEVELS,
    export_sft_curated,
    next_batch_plan,
    production_findings,
    production_report,
)


def _ask(prompt: str, *, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else (default or "")


def _ask_float(prompt: str) -> float:
    while True:
        raw = _ask(prompt)
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            print("Sayısal bir değer girin.")
            continue
        if value <= 0:
            print("Değer 0'dan büyük olmalıdır.")
            continue
        return value


def _ask_bool(prompt: str, *, default: bool = False) -> bool:
    default_text = "e" if default else "h"
    while True:
        raw = _ask(f"{prompt} (e/h)", default=default_text).lower()
        if raw in {"e", "evet", "y", "yes"}:
            return True
        if raw in {"h", "hayır", "hayir", "n", "no"}:
            return False
        print("e veya h girin.")


def _new_wizard(root: Path) -> int:
    print("Yeni canonical kayıt sihirbazı")
    modality = _ask("Sınav türü (written/speaking/listening)", default="written")
    if modality not in SUPPORTED_MODALITIES:
        print(f"Hata: modality şu değerlerden biri olmalı: {', '.join(sorted(SUPPORTED_MODALITIES))}", file=sys.stderr)
        return 2

    try:
        grade = int(_ask("Sınıf", default="11"))
    except ValueError:
        print("Hata: sınıf sayısal olmalıdır.", file=sys.stderr)
        return 2
    if grade not in {9, 10, 11, 12}:
        print("Hata: sınıf 9-12 arasında olmalıdır.", file=sys.stderr)
        return 2

    task_id = _ask("Exact task_id (aynı soru için tüm cevaplarda aynı)")
    if not task_id:
        print("Hata: task_id zorunludur.", file=sys.stderr)
        return 2

    exam_family = _ask("exam_family (aynı sınav/form ailesi)") or None
    question_family = _ask("question_family (yakın soru varyantları)") or None
    subject_group_id = _ask("Anonim subject_group_id (yoksa boş)") or None

    task_prompt = _ask("Soru/görev")
    task_context = _ask("Gerekli bağlam (yoksa boş bırakın)") or None
    response_text = _ask("Öğrenci cevabı / doğrulanmış transkript")

    default_source = "verified_stt" if modality == "speaking" else "teacher_corrected"
    source = _ask("Cevap kaynağı (manual/teacher_corrected/verified_ocr/verified_stt)", default=default_source)

    quality = _ask(
        "Cevap profili (full_correct/high_partial/mid_partial/low_partial/incorrect/blank_irrelevant/borderline)",
        default="mid_partial",
    )
    if quality not in QUALITY_LEVELS:
        print(f"Hata: response_quality şu değerlerden biri olmalı: {', '.join(QUALITY_LEVELS)}", file=sys.stderr)
        return 2

    hard_raw = _ask("Hard-case türleri (virgülle, yoksa boş)")
    hard_cases = [item.strip() for item in hard_raw.split(",") if item.strip()]
    invalid_hard = sorted(set(hard_cases) - set(HARD_CASE_TYPES))
    if invalid_hard:
        print(f"Hata: desteklenmeyen hard-case türleri: {', '.join(invalid_hard)}", file=sys.stderr)
        print(f"Desteklenenler: {', '.join(HARD_CASE_TYPES)}", file=sys.stderr)
        return 2
    adversarial = _ask_bool("Adversarial örnek mi?", default="prompt_injection" in hard_cases)

    try:
        criterion_count = int(_ask("Rubrik ölçüt sayısı", default="1"))
    except ValueError:
        print("Hata: ölçüt sayısı sayısal olmalıdır.", file=sys.stderr)
        return 2
    if criterion_count < 1:
        print("Hata: en az bir ölçüt gerekir.", file=sys.stderr)
        return 2

    criteria: list[dict] = []
    for index in range(1, criterion_count + 1):
        print(f"\nÖlçüt {index}/{criterion_count}")
        criterion_id = _ask("criterion_id", default=f"criterion_{index}")
        name = _ask("Ad")
        description = _ask("Açıklama")
        max_score = _ask_float("Maksimum puan")
        evidence_raw = _ask(
            "Kanıt kaynakları (virgülle: response_text,task_context,audio_delivery,teacher_observation)",
            default="response_text",
        )
        evidence_sources = [item.strip() for item in evidence_raw.split(",") if item.strip()]
        zero_desc = _ask("0 puan çıpası", default="Ölçüt karşılanmıyor.")
        max_desc = _ask(f"{max_score:g} puan çıpası", default="Ölçüt tam olarak karşılanıyor.")
        criteria.append({"criterion_id": criterion_id, "name": name, "description": description, "max_score": max_score, "scoring_anchors": [{"score": 0, "description": zero_desc}, {"score": max_score, "description": max_desc}], "evidence_sources": evidence_sources})

    path = create_draft_record(root, grade=grade, modality=modality, task_prompt=task_prompt, task_context=task_context, criteria=criteria, response_text=response_text, response_source=source)
    record = load_json(path)
    record["task"]["task_id"] = task_id
    record["metadata"].update({"subject_group_id": subject_group_id, "exam_family": exam_family, "question_family": question_family, "response_quality": quality, "hard_case_types": hard_cases, "adversarial": adversarial, "review_count": 0, "adjudicated": False})
    dump_json(path, record)
    print(f"Oluşturuldu: {path.relative_to(root)}")
    print("Kayıt draft durumunda. Gold puanlama ve anonimlik kontrolünden sonra review_count güncellenmeli; teacher_verified olmadan export edilmez.")
    return 0


def _print_findings(findings) -> None:
    if not findings:
        print("PASS — sorun bulunamadı.")
        return
    for finding in findings:
        print(finding.render())


def _error_count(findings) -> int:
    return sum(item.level == "error" for item in findings)


def cmd_validate(args: argparse.Namespace, root: Path) -> int:
    findings = validate_dataset(root, include_examples=args.include_examples)
    _print_findings(findings)
    errors = _error_count(findings)
    warnings = sum(item.level == "warning" for item in findings)
    print(f"\nSonuç: {errors} error, {warnings} warning")
    return 1 if errors else 0


def cmd_leakage(args: argparse.Namespace, root: Path) -> int:
    findings = check_leakage(root)
    _print_findings(findings)
    return 1 if _error_count(findings) else 0


def cmd_check(args: argparse.Namespace, root: Path) -> int:
    findings = validate_dataset(root, include_examples=args.include_examples)
    findings.extend(production_findings(root))
    findings.extend(check_leakage(root))
    _print_findings(findings)
    errors = _error_count(findings)
    warnings = sum(item.level == "warning" for item in findings)
    print(f"\nSonuç: {errors} error, {warnings} warning")
    return 1 if errors else 0


def cmd_split(args: argparse.Namespace, root: Path) -> int:
    production = production_findings(root)
    errors = [item for item in production if item.level == "error"]
    if errors:
        _print_findings(errors)
        print("Split iptal edildi: önce üretim profili hatalarını düzeltin.", file=sys.stderr)
        return 1
    assignments = assign_splits(root, train_ratio=args.train, validation_ratio=args.validation, seed=args.seed)
    for split, ids in assignments.items():
        print(f"{split:10} {len(ids):5} kayıt")
    findings = check_leakage(root)
    if findings:
        _print_findings(findings)
        return 1
    print("Leakage kontrolü: PASS")
    return 0


def cmd_export_sft(args: argparse.Namespace, root: Path) -> int:
    findings = validate_dataset(root)
    findings.extend(production_findings(root))
    errors = [item for item in findings if item.level == "error"]
    if errors:
        _print_findings(errors)
        print("Export iptal edildi: önce veri/üretim profili hatalarını düzeltin.", file=sys.stderr)
        return 1
    leakage = check_leakage(root)
    if leakage:
        _print_findings(leakage)
        print("Export iptal edildi: split leakage bulundu.", file=sys.stderr)
        return 1
    targets = ("train", "validation", "test") if args.split == "all" else (args.split,)
    for split in targets:
        output, count = export_sft_curated(root, split=split)
        print(f"{split:10} {count:5} örnek -> {output.relative_to(root)}")
    return 0


def cmd_stats(args: argparse.Namespace, root: Path) -> int:
    print(json.dumps(dataset_stats(root), ensure_ascii=False, indent=2))
    return 0


def _render_distribution(title: str, values: dict) -> None:
    print(f"\n{title}")
    for key, item in values.items():
        print(f"  {key:18} actual={item['actual']:5} target={item['target']:5} gap={item['gap']:5}")


def cmd_quota(args: argparse.Namespace, root: Path) -> int:
    report = production_report(root, phase=args.phase)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"Üretim fazı: {report['phase']}")
    print(f"Teacher-verified veri: {report['verified_records']} / {report['target_records']} (kalan {report['remaining_to_phase_target']})")
    _render_distribution("Modalite", report["by_modality"])
    _render_distribution("Sınıf", report["by_grade"])
    _render_distribution("Cevap profili", report["by_response_quality"])
    print("\nÖzel örnek oranları")
    for key, item in report["target_ranges"].items():
        print(f"  {key:18} {item['rate'] * 100:6.2f}%  hedef={item['target_min'] * 100:.0f}–{item['target_max'] * 100:.0f}%  {item['status']}")
    print("\nSoru kapsaması")
    exact = report["coverage"]["exact_tasks"]
    family = report["coverage"]["question_families"]
    print(f"  exact task       unique={exact['unique']} avg={exact['average_answers']:.1f} below_min={exact['below_min']} in_range={exact['in_range']} above_max={exact['above_max']}")
    print(f"  question family  unique={family['unique']} avg={family['average_answers']:.1f} below_min={family['below_min']} in_range={family['in_range']} above_max={family['above_max']}")
    print(f"  faz hedef family: {report['coverage']['target_question_families']}")
    if report["unclassified_verified_records"]:
        print(f"\nUYARI: {report['unclassified_verified_records']} teacher_verified kayıt response_quality sınıfı taşımıyor.")
    return 0


def cmd_next_batch(args: argparse.Namespace, root: Path) -> int:
    plan = next_batch_plan(root, phase=args.phase, count=args.count)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    print(f"Sonraki üretim paketi — faz={plan['phase']} boyut={plan['batch_size']}")
    for section in ("modality", "grade", "response_quality"):
        print(f"\n{section}")
        for key, value in plan[section].items():
            print(f"  {key:18} {value:4}")
    print("\nMinimum özel örnekler")
    for key, value in plan["minimum_special_cases"].items():
        print(f"  {key:18} {value:4}")
    print(f"\n{plan['note']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="veri", description="TDE rubrik notlandırma veri seti üretim ve kalite aracı")
    parser.add_argument("--root", type=Path, help="Repo kökü; varsayılan olarak otomatik bulunur.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("new", help="Etkileşimli yeni draft canonical kayıt oluştur.")
    validate = sub.add_parser("validate", help="JSON Schema ve semantic invariant kontrollerini çalıştır.")
    validate.add_argument("--include-examples", action="store_true")
    sub.add_parser("leakage", help="Train/validation/test/benchmark sızıntısını kontrol et.")
    check = sub.add_parser("check", help="Validate + production profile + leakage kontrollerini çalıştır.")
    check.add_argument("--include-examples", action="store_true")
    split = sub.add_parser("split", help="Teacher-verified kayıtları grup-bilinçli olarak ayır.")
    split.add_argument("--train", type=float, default=0.8, help="Train oranı (varsayılan 0.8)")
    split.add_argument("--validation", type=float, default=0.1, help="Validation oranı (varsayılan 0.1)")
    split.add_argument("--seed", default="tde-v1", help="Deterministik split seed'i")
    export = sub.add_parser("export-sft", help="Curated Chat/messages JSONL SFT exportu üret.")
    export.add_argument("--split", choices=["train", "validation", "test", "all"], default="all")
    sub.add_parser("stats", help="Temel veri seti sayaçlarını göster.")
    quota = sub.add_parser("quota", help="Veri üretim hedeflerine göre eksikleri raporla.")
    quota.add_argument("--phase", choices=["pilot", "iteration_1", "iteration_2", "v1"], default=None)
    quota.add_argument("--json", action="store_true")
    next_batch = sub.add_parser("next-batch", help="Sonraki veri üretim paketinin kota dağılımını öner.")
    next_batch.add_argument("--phase", choices=["pilot", "iteration_1", "iteration_2", "v1"], default=None)
    next_batch.add_argument("--count", type=int, default=100)
    next_batch.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve() if args.root else repo_root()
    except FileNotFoundError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 2
    handlers = {"new": lambda args, root: _new_wizard(root), "validate": cmd_validate, "leakage": cmd_leakage, "check": cmd_check, "split": cmd_split, "export-sft": cmd_export_sft, "stats": cmd_stats, "quota": cmd_quota, "next-batch": cmd_next_batch}
    try:
        return handlers[args.command](args, root)
    except (ValueError, FileExistsError, OSError) as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
