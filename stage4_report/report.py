"""Stage 4: persists each evaluation run to results/<run_id>/ and serves it back.

Layout per run (results/<run_id>/):
    metadata.json  — vendor, host, batch_id, status, timestamps
    config.txt     — raw device config, written at submit time
    results.json   — parsed LLM verdicts, written once the batch completes

The config is written first (at submit time); results.json joins it later
once the batch finishes, matching the async nature of the Stage 3 job.
"""

import io
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

CIS_CLASSES = ["COMPLIANT", "NON_COMPLIANT", "N/A"]


def _run_dir(run_id: str) -> Path:
    return RESULTS_DIR / run_id


def _metadata_path(run_id: str) -> Path:
    return _run_dir(run_id) / "metadata.json"


def _read_metadata(run_id: str) -> dict:
    return json.loads(_metadata_path(run_id).read_text(encoding="utf-8"))


def _write_metadata(run_id: str, metadata: dict) -> None:
    _metadata_path(run_id).write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def create_run(vendor: str, host: str, config_text: str, batch_id: str) -> str:
    """Create a new run folder and persist the raw config. Returns the run_id."""
    submitted_at = datetime.now(timezone.utc)
    run_id = f"{submitted_at:%Y%m%dT%H%M%SZ}_{vendor}_{batch_id}"

    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "config.txt").write_text(config_text, encoding="utf-8")
    _write_metadata(
        run_id,
        {
            "run_id": run_id,
            "vendor": vendor,
            "host": host,
            "batch_id": batch_id,
            "status": "pending",
            "submitted_at": submitted_at.isoformat(),
            "completed_at": None,
            "num_controls": None,
            "compliant_count": None,
            "non_compliant_count": None,
            "na_count": None,
            "percent_compliant": None,
            "automated_count": None,
            "manual_count": None,
        },
    )
    return run_id


def _compute_summary(results: list[dict]) -> dict:
    """Compliance score = COMPLIANT / (COMPLIANT + NON_COMPLIANT), N/A excluded from
    the denominator — a control that doesn't apply shouldn't count against the score."""
    compliant = sum(1 for r in results if r["verdict"] == "COMPLIANT")
    non_compliant = sum(1 for r in results if r["verdict"] == "NON_COMPLIANT")
    na = sum(1 for r in results if r["verdict"] == "N/A")
    scored = compliant + non_compliant
    return {
        "compliant_count": compliant,
        "non_compliant_count": non_compliant,
        "na_count": na,
        "percent_compliant": round(compliant / scored * 100, 1) if scored else None,
        "automated_count": sum(1 for r in results if r.get("automated") is True),
        "manual_count": sum(1 for r in results if r.get("automated") is False),
    }


def save_results(run_id: str, results: list[dict]) -> None:
    """Write the completed batch's verdicts and compiled score into the run folder."""
    run_dir = _run_dir(run_id)
    (run_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    metadata = _read_metadata(run_id)
    metadata["status"] = "completed"
    metadata["completed_at"] = datetime.now(timezone.utc).isoformat()
    metadata["num_controls"] = len(results)
    metadata.update(_compute_summary(results))
    _write_metadata(run_id, metadata)


def list_runs() -> list[dict]:
    """List all runs, most recently submitted first."""
    if not RESULTS_DIR.exists():
        return []
    runs = []
    for metadata_path in RESULTS_DIR.glob("*/metadata.json"):
        run_id = metadata_path.parent.name
        metadata = _read_metadata(run_id)
        metadata["has_config"] = (metadata_path.parent / "config.txt").exists()
        metadata["has_results"] = (metadata_path.parent / "results.json").exists()
        metadata["has_metrics"] = (metadata_path.parent / "ground_truth_metrics.json").exists()
        runs.append(metadata)
    return sorted(runs, key=lambda m: m["submitted_at"], reverse=True)


def get_metadata(run_id: str) -> dict:
    return _read_metadata(run_id)


def delete_run(run_id: str) -> None:
    """Permanently remove a run and everything under results/<run_id>/ from
    disk. Unlike the rest of this module (which never deletes existing
    files), this is the one deliberate, explicit exception — a direct,
    user-initiated delete rather than an incidental side effect."""
    run_dir = _run_dir(run_id)
    if run_dir.exists():
        shutil.rmtree(run_dir)


def get_config(run_id: str) -> str:
    return (_run_dir(run_id) / "config.txt").read_text(encoding="utf-8")


def get_results(run_id: str) -> list[dict]:
    results_path = _run_dir(run_id) / "results.json"
    if not results_path.exists():
        return []
    return json.loads(results_path.read_text(encoding="utf-8"))


def _ground_truth_path(run_id: str) -> Path:
    return _run_dir(run_id) / "ground_truth.json"


def _metrics_path(run_id: str) -> Path:
    return _run_dir(run_id) / "ground_truth_metrics.json"


def get_ground_truth(run_id: str) -> dict:
    """Human-verified actual verdicts, keyed by control_id. Only controls the
    user has reviewed appear here — this is what makes real accuracy metrics
    possible, distinct from the LLM's own (unverified) verdict in results.json."""
    path = _ground_truth_path(run_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_metrics(run_id: str) -> dict | None:
    """Accuracy metrics as of the last save_metrics() call, or None if never
    computed (ground truth labeling isn't complete yet for this run)."""
    path = _metrics_path(run_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_ground_truth(run_id: str, ground_truth: dict) -> None:
    """Persist ground truth labels to disk, partial or complete. Safe to call
    on every edit — e.g. from the History page's data editor on each rerun —
    so labeling progress survives a page reload instead of living only in
    that browser session's memory."""
    cleaned = {control_id: verdict for control_id, verdict in ground_truth.items() if verdict}
    _ground_truth_path(run_id).write_text(json.dumps(cleaned, indent=2), encoding="utf-8")


def is_ground_truth_complete(run_id: str) -> bool:
    """True once every control in this run's results has a ground truth label."""
    results = get_results(run_id)
    if not results:
        return False
    ground_truth = get_ground_truth(run_id)
    return all(r["control_id"] in ground_truth for r in results)


def save_metrics(run_id: str) -> dict | None:
    """Compute and persist accuracy metrics, but only once ground truth is
    complete — a half-finished labeling pass would otherwise compute (and
    show) a misleadingly partial accuracy score."""
    if not is_ground_truth_complete(run_id):
        return None
    metrics = compute_accuracy_metrics(run_id)
    if metrics is not None:
        _metrics_path(run_id).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def compute_accuracy_metrics(run_id: str) -> dict | None:
    """Confusion matrix + macro precision/recall/F1 of LLM verdict vs. ground
    truth, restricted to controls with a recorded ground truth label. Returns
    None if nothing has been labeled yet.

    precision = TP / (TP + FP), recall = TP / (TP + FN), per class, then
    macro-averaged over classes that actually appear in the ground truth
    (a class with zero labeled instances doesn't get counted in the average).
    """
    ground_truth = get_ground_truth(run_id)
    if not ground_truth:
        return None

    verdict_by_id = {r["control_id"]: r["verdict"] for r in get_results(run_id)}
    pairs = [
        (actual, verdict_by_id[control_id])
        for control_id, actual in ground_truth.items()
        if control_id in verdict_by_id
    ]
    if not pairs:
        return None

    matrix = {actual: {predicted: 0 for predicted in CIS_CLASSES} for actual in CIS_CLASSES}
    for actual, predicted in pairs:
        matrix[actual][predicted] += 1

    total = len(pairs)
    correct = sum(matrix[c][c] for c in CIS_CLASSES)

    per_class = {}
    precisions, recalls, f1s = [], [], []
    for c in CIS_CLASSES:
        tp = matrix[c][c]
        fp = sum(matrix[a][c] for a in CIS_CLASSES if a != c)
        fn = sum(matrix[c][p] for p in CIS_CLASSES if p != c)
        support = sum(matrix[c].values())

        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / (tp + fn) if (tp + fn) > 0 else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and (precision + recall) > 0
            else None
        )

        per_class[c] = {
            "precision": round(precision, 3) if precision is not None else None,
            "recall": round(recall, 3) if recall is not None else None,
            "f1": round(f1, 3) if f1 is not None else None,
            "support": support,
        }
        if support > 0:
            if precision is not None:
                precisions.append(precision)
            if recall is not None:
                recalls.append(recall)
            if f1 is not None:
                f1s.append(f1)

    return {
        "n_labeled": total,
        "accuracy": round(correct / total, 3),
        "confusion_matrix": matrix,
        "per_class": per_class,
        "macro_precision": round(sum(precisions) / len(precisions), 3) if precisions else None,
        "macro_recall": round(sum(recalls) / len(recalls), 3) if recalls else None,
        "macro_f1": round(sum(f1s) / len(f1s), 3) if f1s else None,
    }


def _display_name(run_id: str) -> str:
    """run_id, prefixed with its label if one was assigned (see History page
    labeling) — falls back to the bare run_id for runs that never got one."""
    label = _read_metadata(run_id).get("label")
    return f"{label}_{run_id}" if label else run_id


def zip_run(run_id: str) -> bytes:
    """Zip the entire run folder in-memory for a one-click folder download."""
    run_dir = _run_dir(run_id)
    arc_root = _display_name(run_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in run_dir.iterdir():
            zf.write(file_path, arcname=f"{arc_root}/{file_path.name}")
    return buffer.getvalue()


def zip_all_runs() -> bytes:
    """Zip every run's folder into one combined archive, each named with its
    label (or run_id if unlabeled), for a single one-click bulk download."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for run_dir in sorted(RESULTS_DIR.iterdir()):
            if not (run_dir / "metadata.json").exists():
                continue
            run_id = run_dir.name
            arc_root = _display_name(run_id)
            for file_path in run_dir.iterdir():
                zf.write(file_path, arcname=f"{arc_root}/{file_path.name}")
    return buffer.getvalue()
