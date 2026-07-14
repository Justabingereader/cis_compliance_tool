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
import zipfile
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


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
        runs.append(metadata)
    return sorted(runs, key=lambda m: m["submitted_at"], reverse=True)


def get_metadata(run_id: str) -> dict:
    return _read_metadata(run_id)


def get_config(run_id: str) -> str:
    return (_run_dir(run_id) / "config.txt").read_text(encoding="utf-8")


def get_results(run_id: str) -> list[dict]:
    results_path = _run_dir(run_id) / "results.json"
    if not results_path.exists():
        return []
    return json.loads(results_path.read_text(encoding="utf-8"))


def zip_run(run_id: str) -> bytes:
    """Zip the entire run folder in-memory for a one-click folder download."""
    run_dir = _run_dir(run_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in run_dir.iterdir():
            zf.write(file_path, arcname=f"{run_id}/{file_path.name}")
    return buffer.getvalue()
