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
    export_sft,
    repo_root,
    validate_dataset,
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

    task_prompt = _ask("Soru/görev")
    task_context = _ask("Gerekli bağlam (yoksa boş bırakın)") or None
    response_text = _ask("Öğrenci cevabı / doğrulanmış transkript")

    default_source = "verified_stt" if modality == "speaking" else "teacher_corrected"
    source = _ask("Cevap kaynağı (manual/teacher_corrected/verified_ocr/verified_stt)", default=default_source)

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
        evidence_default = "response_text"
        evidence_raw = _ask(
            "Kanıt kaynakları (virgülle: response_text,task_context,audio_delivery,teacher_observation)",
            default=evidence_default,
        )
        evidence_sources = [item.strip() for item in evidence_raw.split(",") if item.strip()]
        zero_desc = _ask("0 puan çıpası", default="Ölçüt karşılanmıyor.")
        max_desc = _ask(f"{max_score:g} puan çıpası", default="Ölçüt tam olarak karşılanıyor.")
        criteria.append(
            {
                "criterion_id": criterion_id,
                "name": name,
                "description": description,
                "max_score": max_score,
                "scoring_anchors": [
                    {"score": 0, "description": zero_desc},
                    {"score": max_score, "description": max_desc},
                ],
                "evidence_sources": evidence_sources,
            }
        )

    path = create_draft_record(
        root,
        grade=grade,
        modality=modality,
        task_prompt=task_prompt,
        task_context=task_context,
        criteria=criteria,
        response_text=response_text,
        response_source=source,
    )
    print(f"Oluşturuldu: {path.relative_to(root)}")
    print("Kayıt draft durumunda. Gold puanlama, anonimlik kontrolü ve teacher_verified onayı tamamlanmadan export edilmez.")
    return 0


def _print_findings(findings) -> None:
    if not findings:
        print("PASS — sorun bulunamadı.")
        return
    for finding in findings:
        print(finding.render())


def cmd_validate(args: argparse.Namespace, root: Path) -> int:
    findings = validate_dataset(root, include_examples=args.include_examples)
    _print_findings(findings)
    errors = sum(item.level == "error" for item in findings)
    warnings = sum(item.level == "warning" for item in findings)
    print(f"\nSonuç: {errors} error, {warnings} warning")
    return 1 if errors else 0


def cmd_leakage(args: argparse.Namespace, root: Path) -> int:
    findings = check_leakage(root)
    _print_findings(findings)
    return 1 if any(item.level == "error" for item in findings) else 0


def cmd_check(args: argparse.Namespace, root: Path) -> int:
    findings = validate_dataset(root, include_examples=args.include_examples)
    findings.extend(check_leakage(root))
    _print_findings(findings)
    errors = sum(item.level == "error" for item in findings)
    warnings = sum(item.level == "warning" for item in findings)
    print(f"\nSonuç: {errors} error, {warnings} warning")
    return 1 if errors else 0


def cmd_split(args: argparse.Namespace, root: Path) -> int:
    assignments = assign_splits(
        root,
        train_ratio=args.train,
        validation_ratio=args.validation,
        seed=args.seed,
    )
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
    errors = [item for item in findings if item.level == "error"]
    if errors:
        _print_findings(errors)
        print("Export iptal edildi: önce veri hatalarını düzeltin.", file=sys.stderr)
        return 1

    leakage = check_leakage(root)
    if leakage:
        _print_findings(leakage)
        print("Export iptal edildi: split leakage bulundu.", file=sys.stderr)
        return 1

    targets = ("train", "validation", "test") if args.split == "all" else (args.split,)
    for split in targets:
        output, count = export_sft(root, split=split)
        print(f"{split:10} {count:5} örnek -> {output.relative_to(root)}")
    return 0


def cmd_stats(args: argparse.Namespace, root: Path) -> int:
    print(json.dumps(dataset_stats(root), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veri",
        description="TDE rubrik notlandırma veri seti üretim ve kalite aracı",
    )
    parser.add_argument("--root", type=Path, help="Repo kökü; varsayılan olarak otomatik bulunur.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("new", help="Etkileşimli yeni draft canonical kayıt oluştur.")

    validate = sub.add_parser("validate", help="JSON Schema ve semantic invariant kontrollerini çalıştır.")
    validate.add_argument("--include-examples", action="store_true")

    sub.add_parser("leakage", help="Train/validation/test/benchmark sızıntısını kontrol et.")

    check = sub.add_parser("check", help="Validate + leakage kontrollerini tek komutta çalıştır.")
    check.add_argument("--include-examples", action="store_true")

    split = sub.add_parser("split", help="Teacher-verified kayıtları grup-bilinçli olarak ayır.")
    split.add_argument("--train", type=float, default=0.8, help="Train oranı (varsayılan 0.8)")
    split.add_argument("--validation", type=float, default=0.1, help="Validation oranı (varsayılan 0.1)")
    split.add_argument("--seed", default="tde-v1", help="Deterministik split seed'i")

    export = sub.add_parser("export-sft", help="Chat/messages JSONL SFT exportu üret.")
    export.add_argument("--split", choices=["train", "validation", "test", "all"], default="all")

    sub.add_parser("stats", help="Veri seti sayaçlarını göster.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve() if args.root else repo_root()
    except FileNotFoundError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 2

    handlers = {
        "new": lambda args, root: _new_wizard(root),
        "validate": cmd_validate,
        "leakage": cmd_leakage,
        "check": cmd_check,
        "split": cmd_split,
        "export-sft": cmd_export_sft,
        "stats": cmd_stats,
    }
    try:
        return handlers[args.command](args, root)
    except (ValueError, FileExistsError, OSError) as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
