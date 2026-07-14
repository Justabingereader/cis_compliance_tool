"""Stage 3: LLM evaluation via the OpenAI Batch API.

One request per CIS control is submitted as a batch job (async, up to 24h).
Callers submit a batch, poll its status, then retrieve parsed verdicts once
it completes.
"""

import json
import tempfile
from pathlib import Path

from openai import OpenAI

import config
from stage2_benchmarks.loader import load_controls
from stage3_llm_eval.prompts import SYSTEM_PROMPT, build_user_prompt

MODEL = "gpt-5.6-terra"

_client = OpenAI(api_key=config.OPENAI_API_KEY)

VERDICT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "cis_verdict",
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["COMPLIANT", "NON_COMPLIANT", "N/A"]},
                "reasoning": {"type": "string"},
            },
            "required": ["verdict", "reasoning"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


def submit_batch(vendor: str, config_text: str) -> str:
    """Build one request per CIS control, upload as a batch job, return its batch_id."""
    controls = load_controls(vendor)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for control in controls:
            body = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(config_text, control)},
                ],
                "response_format": VERDICT_SCHEMA,
                "temperature": 0,
            }
            line = {
                "custom_id": control["control_id"],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": body,
            }
            f.write(json.dumps(line) + "\n")
        batch_file_path = Path(f.name)

    try:
        with open(batch_file_path, "rb") as fh:
            uploaded = _client.files.create(file=fh, purpose="batch")
        batch = _client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"vendor": vendor},
        )
    finally:
        batch_file_path.unlink(missing_ok=True)

    return batch.id


def check_batch_status(batch_id: str) -> dict:
    """Return the current status of a submitted batch."""
    batch = _client.batches.retrieve(batch_id)
    counts = batch.request_counts
    return {
        "status": batch.status,
        "completed": counts.completed if counts else 0,
        "failed": counts.failed if counts else 0,
        "total": counts.total if counts else 0,
    }


def retrieve_results(batch_id: str) -> list[dict]:
    """Fetch and parse a completed batch's results into verdict dicts."""
    batch = _client.batches.retrieve(batch_id)
    if batch.status != "completed" or not batch.output_file_id:
        raise RuntimeError(f"Batch {batch_id} is not completed yet (status={batch.status}).")

    vendor = batch.metadata.get("vendor") if batch.metadata else None
    automated_by_id = {c["control_id"]: c["automated"] for c in load_controls(vendor)} if vendor else {}

    content = _client.files.content(batch.output_file_id).text
    results = []
    for line in content.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        message_content = entry["response"]["body"]["choices"][0]["message"]["content"]
        parsed = json.loads(message_content)
        results.append(
            {
                "control_id": entry["custom_id"],
                "verdict": parsed["verdict"],
                "reasoning": parsed["reasoning"],
                "automated": automated_by_id.get(entry["custom_id"]),
            }
        )
    return results
