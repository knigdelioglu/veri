from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from .core import dump_json, load_records, repo_root
from .production import SUPPORTED_SPLITS, VERIFIED_STATUSES, _connected_components, _group_values


def _stable(value: str, seed: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{value}".encode("utf-8")).digest()[:8], "big")


def _component_stats(component: list[dict]) -> dict:
    return {
        "records": len(component),
        "modality": Counter(str(r["modality"]) for r in component),
        "grade": Counter(str(r["grade"]) for r in component),
        "quality": Counter(str(r["metadata"]["response_quality"]) for r in component),
        "needs_review": sum(r["gold_evaluation"].get("needs_review") is True for r in component),
        "hard_case": sum(bool(r["metadata"].get("hard_case_types")) for r in component),
        "adversarial": sum(r["metadata"].get("adversarial") is True for r in component),
    }


def _add_stats(target: dict, source: dict, sign: int = 1) -> None:
    target["records"] += sign * source["records"]
    for field in ("modality", "grade", "quality"):
        for key, value in source[field].items():
            target[field][key] += sign * value
    for field in ("needs_review", "hard_case", "adversarial"):
        target[field] += sign * source[field]


def _blank_stats() -> dict:
    return {
        "records": 0,
        "modality": Counter(),
        "grade": Counter(),
        "quality": Counter(),
        "needs_review": 0,
        "hard_case": 0,
        "adversarial": 0,
    }


def _targets(global_stats: dict, ratios: dict[str, float]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for split, ratio in ratios.items():
        row = _blank_stats()
        row["records"] = global_stats["records"] * ratio
        for field in ("modality", "grade", "quality"):
            row[field] = Counter({k: v * ratio for k, v in global_stats[field].items()})
        for field in ("needs_review", "hard_case", "adversarial"):
            row[field] = global_stats[field] * ratio
        result[split] = row
    return result


def _norm_sq(actual: float, target: float, floor: float = 1.0) -> float:
    scale = max(abs(target), floor)
    return ((actual - target) / scale) ** 2


def _cost(states: dict[str, dict], targets: dict[str, dict], global_stats: dict) -> float:
    cost = 0.0
    for split in SUPPORTED_SPLITS:
        state = states[split]
        target = targets[split]
        cost += 12.0 * _norm_sq(state["records"], target["records"], 20.0)
        for key in global_stats["modality"]:
            cost += 4.0 * _norm_sq(state["modality"][key], target["modality"][key], 5.0)
        for key in global_stats["grade"]:
            cost += 2.5 * _norm_sq(state["grade"][key], target["grade"][key], 5.0)
        for key in global_stats["quality"]:
            cost += 0.75 * _norm_sq(state["quality"][key], target["quality"][key], 2.0)
        for field in ("needs_review", "hard_case", "adversarial"):
            cost += 0.5 * _norm_sq(state[field], target[field], 1.0)

        # Evaluation splits should not collapse onto a single modality/grade when component
        # granularity permits broader coverage. Apply this to empty splits too; otherwise
        # leaving an evaluation split empty gets an artificial cost advantage.
        if split in {"validation", "test"}:
            missing_modalities = sum(state["modality"][key] == 0 for key in global_stats["modality"])
            missing_grades = sum(state["grade"][key] == 0 for key in global_stats["grade"])
            cost += 0.8 * missing_modalities + 0.3 * missing_grades
    return cost


def _signature(component: list[dict]) -> str:
    return "|".join(sorted(r["id"] for r in component))


def assign_balanced_splits(
    root: Path,
    *,
    train_ratio: float = 0.8,
    validation_ratio: float = 0.1,
    seed: str = "tde-v1",
    rebalance: bool = False,
) -> dict[str, list[str]]:
    if not (0 < train_ratio < 1):
        raise ValueError("train_ratio 0 ile 1 arasında olmalıdır.")
    if not (0 <= validation_ratio < 1):
        raise ValueError("validation_ratio 0 ile 1 arasında olmalıdır.")
    if train_ratio + validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio 1'den küçük olmalıdır.")

    loaded = load_records(root)
    eligible: list[tuple[Path, dict]] = []
    benchmark_keys: set[tuple[str, str]] = set()
    for _, record in loaded:
        if record.get("metadata", {}).get("split") == "benchmark":
            benchmark_keys.update(_group_values(record))

    for path, record in loaded:
        metadata = record.get("metadata", {})
        if metadata.get("status") not in VERIFIED_STATUSES or metadata.get("pii_reviewed") is not True:
            continue
        if metadata.get("split") == "benchmark":
            continue
        collisions = [f"{field}={value}" for field, value in _group_values(record) if (field, value) in benchmark_keys]
        if collisions:
            raise ValueError(f"{record['id']} benchmark ailesiyle çakışıyor: {', '.join(collisions)}")
        eligible.append((path, record))

    records = [record for _, record in eligible]
    components = _connected_components(records)
    ratios = {
        "train": train_ratio,
        "validation": validation_ratio,
        "test": 1.0 - train_ratio - validation_ratio,
    }
    global_stats = _component_stats(records)
    targets = _targets(global_stats, ratios)
    component_stats = [_component_stats(c) for c in components]
    assignment: list[str | None] = [None] * len(components)
    states = {split: _blank_stats() for split in SUPPORTED_SPLITS}
    locked_indices: set[int] = set()

    if not rebalance:
        for idx, component in enumerate(components):
            existing = {
                str(r.get("metadata", {}).get("split"))
                for r in component
                if r.get("metadata", {}).get("split") in SUPPORTED_SPLITS
            }
            if len(existing) > 1:
                ids = ", ".join(sorted(r["id"] for r in component))
                raise ValueError(f"Bağlı kayıt grubunda mevcut split çakışması var ({ids})")
            if existing:
                split = next(iter(existing))
                assignment[idx] = split
                locked_indices.add(idx)
                _add_stats(states[split], component_stats[idx])

    order = sorted(
        (idx for idx, split in enumerate(assignment) if split is None),
        key=lambda idx: (-component_stats[idx]["records"], _stable(_signature(components[idx]), seed)),
    )

    for idx in order:
        best: tuple[float, int, str] | None = None
        for split in SUPPORTED_SPLITS:
            _add_stats(states[split], component_stats[idx])
            score = _cost(states, targets, global_stats)
            _add_stats(states[split], component_stats[idx], -1)
            candidate = (score, _stable(f"{_signature(components[idx])}:{split}", seed), split)
            if best is None or candidate < best:
                best = candidate
        assert best is not None
        split = best[2]
        assignment[idx] = split
        _add_stats(states[split], component_stats[idx])

    # Deterministic local improvement is allowed only for components assigned in this call.
    # Existing split metadata is a freeze boundary when rebalance=False.
    improved = True
    while improved:
        improved = False
        baseline = _cost(states, targets, global_stats)
        best_move = None
        for idx, source in enumerate(assignment):
            assert source is not None
            if idx in locked_indices:
                continue
            for dest in SUPPORTED_SPLITS:
                if dest == source:
                    continue
                _add_stats(states[source], component_stats[idx], -1)
                _add_stats(states[dest], component_stats[idx])
                score = _cost(states, targets, global_stats)
                _add_stats(states[dest], component_stats[idx], -1)
                _add_stats(states[source], component_stats[idx])
                key = (score, _stable(f"move:{idx}:{source}:{dest}", seed), idx, dest)
                if score + 1e-12 < baseline and (best_move is None or key < best_move[0]):
                    best_move = (key, idx, source, dest)
        if best_move is not None:
            _, idx, source, dest = best_move
            _add_stats(states[source], component_stats[idx], -1)
            _add_stats(states[dest], component_stats[idx])
            assignment[idx] = dest
            improved = True
            continue

        baseline = _cost(states, targets, global_stats)
        best_swap = None
        for left in range(len(components)):
            if left in locked_indices:
                continue
            for right in range(left + 1, len(components)):
                if right in locked_indices:
                    continue
                a, b = assignment[left], assignment[right]
                assert a is not None and b is not None
                if a == b:
                    continue
                _add_stats(states[a], component_stats[left], -1)
                _add_stats(states[b], component_stats[right], -1)
                _add_stats(states[a], component_stats[right])
                _add_stats(states[b], component_stats[left])
                score = _cost(states, targets, global_stats)
                _add_stats(states[b], component_stats[left], -1)
                _add_stats(states[a], component_stats[right], -1)
                _add_stats(states[b], component_stats[right])
                _add_stats(states[a], component_stats[left])
                key = (score, _stable(f"swap:{left}:{right}", seed), left, right)
                if score + 1e-12 < baseline and (best_swap is None or key < best_swap[0]):
                    best_swap = (key, left, right, a, b)
        if best_swap is not None:
            _, left, right, a, b = best_swap
            _add_stats(states[a], component_stats[left], -1)
            _add_stats(states[b], component_stats[right], -1)
            _add_stats(states[a], component_stats[right])
            _add_stats(states[b], component_stats[left])
            assignment[left], assignment[right] = b, a
            improved = True

    split_by_id: dict[str, str] = {}
    assignments: dict[str, list[str]] = {name: [] for name in SUPPORTED_SPLITS}
    for idx, component in enumerate(components):
        split = assignment[idx]
        assert split is not None
        for record in component:
            split_by_id[record["id"]] = split
            assignments[split].append(record["id"])

    for path, record in eligible:
        record["metadata"]["split"] = split_by_id[record["id"]]
        dump_json(path, record)

    for split, ids in assignments.items():
        ids.sort()
        dump_json(
            root / "dataset" / "splits" / split / "manifest.json",
            {
                "schema_version": "1.0",
                "split": split,
                "seed": seed,
                "algorithm": "balanced-connected-components-v1",
                "requested_ratios": ratios,
                "grouping_rule": "connected components over task_id OR subject_group_id OR exam_family OR question_family",
                "record_ids": ids,
            },
        )
    return assignments


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic balanced group-aware dataset split")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--train", type=float, default=0.8)
    parser.add_argument("--validation", type=float, default=0.1)
    parser.add_argument("--seed", default="tde-v1")
    parser.add_argument("--rebalance", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else repo_root()
    result = assign_balanced_splits(root, train_ratio=args.train, validation_ratio=args.validation, seed=args.seed, rebalance=args.rebalance)
    for split in SUPPORTED_SPLITS:
        print(f"{split:10} {len(result[split]):5} kayıt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
