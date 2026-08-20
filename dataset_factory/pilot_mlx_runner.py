from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .core import repo_root
from .prepare_mlx_pilot import prepare_mlx_pilot

MODEL_REPO = "mlx-community/Qwen3-4B-4bit"
MLX_LM_VERSION = "0.31.3"
EXPERIMENT_REL = Path("experiments/pilot-qwen3-4b-mlx")
REPORT_REL = Path("reports/pilot-qwen3-4b")
DEFAULT_ADAPTER_REL = EXPERIMENT_REL / "adapters"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hardware_guard() -> None:
    if platform.system() != "Darwin" or platform.machine().lower() not in {"arm64", "aarch64"}:
        raise RuntimeError("Bu deney MLX için Apple Silicon macOS üzerinde çalıştırılmalıdır.")


def _mlx_version_guard() -> None:
    try:
        installed = importlib.metadata.version("mlx-lm")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            f"mlx-lm kurulu değil. `python -m pip install -r {EXPERIMENT_REL / 'requirements-mlx.txt'}` çalıştırın."
        ) from exc
    if installed != MLX_LM_VERSION:
        raise RuntimeError(f"Bu baseline mlx-lm=={MLX_LM_VERSION} ile kilitlidir; kurulu sürüm: {installed}")


def _run(command: list[str], *, root: Path) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=root, check=True)


def _paths(root: Path) -> dict[str, Path]:
    experiment = root / EXPERIMENT_REL
    reports = root / REPORT_REL
    return {
        "experiment": experiment,
        "reports": reports,
        "data": experiment / "data",
        "config": experiment / "lora.yaml",
        "manifest": experiment / "experiment.json",
        "adapter": root / DEFAULT_ADAPTER_REL,
        "lock": reports / "CONFIG_LOCKED.json",
        "test_opened": reports / "FINAL_TEST_OPENED.json",
    }


def _adapter_files(adapter: Path) -> tuple[Path, Path]:
    config = adapter / "adapter_config.json"
    weights = adapter / "adapters.safetensors"
    missing = [str(path) for path in (config, weights) if not path.exists()]
    if missing:
        raise FileNotFoundError("Seçili adapter tamamlanmamış: " + ", ".join(missing))
    return config, weights


def build_lock_payload(root: Path, adapter: Path) -> dict:
    paths = _paths(root)
    adapter_config, adapter_weights = _adapter_files(adapter)
    validation_report = paths["reports"] / "qlora-validation.json"
    base_report = paths["reports"] / "base-validation.json"
    if not validation_report.exists():
        raise FileNotFoundError(f"Validation raporu yok: {validation_report}")
    if not base_report.exists():
        raise FileNotFoundError(f"Base validation raporu yok: {base_report}")

    return {
        "schema_version": "1.0",
        "experiment_id": "pilot-qwen3-4b-mlx-qlora-v1",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "model_repo": MODEL_REPO,
        "mlx_lm_version": MLX_LM_VERSION,
        "adapter_path": str(adapter.relative_to(root) if adapter.is_relative_to(root) else adapter),
        "hashes": {
            "experiment_json": _sha256(paths["manifest"]),
            "lora_yaml": _sha256(paths["config"]),
            "adapter_config_json": _sha256(adapter_config),
            "adapter_weights": _sha256(adapter_weights),
            "base_validation_report": _sha256(base_report),
            "qlora_validation_report": _sha256(validation_report),
        },
        "test_opened": False,
    }


def verify_lock(root: Path, lock: dict) -> Path:
    paths = _paths(root)
    if lock.get("model_repo") != MODEL_REPO or lock.get("mlx_lm_version") != MLX_LM_VERSION:
        raise RuntimeError("Lock model/runtime bilgisi baseline ile uyuşmuyor")
    adapter_text = lock.get("adapter_path")
    if not isinstance(adapter_text, str) or not adapter_text:
        raise RuntimeError("Lock adapter_path taşımıyor")
    adapter = Path(adapter_text)
    if not adapter.is_absolute():
        adapter = root / adapter
    adapter_config, adapter_weights = _adapter_files(adapter)
    base_report = paths["reports"] / "base-validation.json"
    validation_report = paths["reports"] / "qlora-validation.json"
    current = {
        "experiment_json": _sha256(paths["manifest"]),
        "lora_yaml": _sha256(paths["config"]),
        "adapter_config_json": _sha256(adapter_config),
        "adapter_weights": _sha256(adapter_weights),
        "base_validation_report": _sha256(base_report),
        "qlora_validation_report": _sha256(validation_report),
    }
    expected = lock.get("hashes")
    if current != expected:
        changed = sorted(key for key in current if not isinstance(expected, dict) or current[key] != expected.get(key))
        raise RuntimeError("Configuration lock bozulmuş; değişen girdiler: " + ", ".join(changed))
    return adapter


def prepare(root: Path) -> None:
    paths = _paths(root)
    manifest = prepare_mlx_pilot(root, paths["data"])
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def base_validation(root: Path) -> None:
    _hardware_guard()
    _mlx_version_guard()
    paths = _paths(root)
    paths["reports"].mkdir(parents=True, exist_ok=True)
    predictions = paths["reports"] / "base-validation-predictions.jsonl"
    report = paths["reports"] / "base-validation.json"
    _run([
        sys.executable,
        "-m",
        "dataset_factory.mlx_predict",
        "--split",
        "validation",
        "--model",
        MODEL_REPO,
        "--output",
        str(predictions),
    ], root=root)
    _run(["veri", "evaluate", str(predictions), "--split", "validation", "--output", str(report)], root=root)


def train(root: Path) -> None:
    _hardware_guard()
    _mlx_version_guard()
    paths = _paths(root)
    prepare(root)
    if (paths["reports"] / "FINAL_TEST_OPENED.json").exists():
        raise RuntimeError("Final test daha önce açılmış; aynı pilot üzerinde yeni training yasak.")
    _run([
        "mlx_lm.lora",
        "--config",
        str(paths["config"]),
        "--mask-prompt",
    ], root=root)


def tuned_validation(root: Path, adapter: Path) -> None:
    _hardware_guard()
    _mlx_version_guard()
    _adapter_files(adapter)
    paths = _paths(root)
    paths["reports"].mkdir(parents=True, exist_ok=True)
    predictions = paths["reports"] / "qlora-validation-predictions.jsonl"
    report = paths["reports"] / "qlora-validation.json"
    _run([
        sys.executable,
        "-m",
        "dataset_factory.mlx_predict",
        "--split",
        "validation",
        "--model",
        MODEL_REPO,
        "--adapter-path",
        str(adapter),
        "--output",
        str(predictions),
    ], root=root)
    _run(["veri", "evaluate", str(predictions), "--split", "validation", "--output", str(report)], root=root)


def lock_configuration(root: Path, adapter: Path) -> Path:
    paths = _paths(root)
    paths["reports"].mkdir(parents=True, exist_ok=True)
    if paths["test_opened"].exists():
        raise RuntimeError("Final test zaten açılmış; yeni lock oluşturulamaz.")
    payload = build_lock_payload(root, adapter)
    paths["lock"].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"LOCKED -> {paths['lock']}")
    return paths["lock"]


def final_test(root: Path) -> None:
    _hardware_guard()
    _mlx_version_guard()
    paths = _paths(root)
    if not paths["lock"].exists():
        raise RuntimeError("CONFIG_LOCKED.json yok; validation sonrası konfigürasyonu önce kilitleyin.")
    lock = json.loads(paths["lock"].read_text(encoding="utf-8"))
    adapter = verify_lock(root, lock)

    opened = {
        "schema_version": "1.0",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": lock["experiment_id"],
        "config_lock_sha256": _sha256(paths["lock"]),
        "rule": "Bu marker oluştuktan sonra aynı pilot test skoruna göre model/hyperparameter tuning yapılmaz.",
    }
    paths["test_opened"].write_text(json.dumps(opened, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    predictions = paths["reports"] / "final-test-predictions.jsonl"
    report = paths["reports"] / "final-test.json"
    _run([
        sys.executable,
        "-m",
        "dataset_factory.mlx_predict",
        "--split",
        "test",
        "--unlock-test",
        "--model",
        MODEL_REPO,
        "--adapter-path",
        str(adapter),
        "--output",
        str(predictions),
    ], root=root)
    _run(["veri", "evaluate", str(predictions), "--split", "test", "--output", str(report)], root=root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pilot Qwen3 4B MLX deneyini sealed-test protokolüyle çalıştır.")
    parser.add_argument("--root", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    sub.add_parser("base-validation")
    sub.add_parser("train")
    tuned = sub.add_parser("tuned-validation")
    tuned.add_argument("--adapter-path", type=Path, default=DEFAULT_ADAPTER_REL)
    lock = sub.add_parser("lock")
    lock.add_argument("--adapter-path", type=Path, default=DEFAULT_ADAPTER_REL)
    sub.add_parser("final-test")
    args = parser.parse_args(argv)

    root = args.root.resolve() if args.root else repo_root()
    if args.command == "prepare":
        prepare(root)
    elif args.command == "base-validation":
        base_validation(root)
    elif args.command == "train":
        train(root)
    elif args.command == "tuned-validation":
        adapter = args.adapter_path if args.adapter_path.is_absolute() else root / args.adapter_path
        tuned_validation(root, adapter)
    elif args.command == "lock":
        adapter = args.adapter_path if args.adapter_path.is_absolute() else root / args.adapter_path
        lock_configuration(root, adapter)
    elif args.command == "final-test":
        final_test(root)
    else:  # pragma: no cover
        parser.error("Bilinmeyen komut")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
