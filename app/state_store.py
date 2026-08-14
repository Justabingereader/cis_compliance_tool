"""Persists session state to disk so it survives a full browser page refresh.

Streamlit's st.session_state lives only in memory per browser session — a
hard refresh starts a brand new session and wipes it. This mirrors the keys
that matter (connection + run tracking) to a local JSON file, so
init_session_state() can restore them on the next load.
"""

import json
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / ".streamlit_session.json"

PERSISTED_KEYS = [
    "config_text",
    "connected_vendor",
    "connected_host",
    "batch_id",
    "run_id",
    "results",
]


def load() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save(state: dict) -> None:
    snapshot = {key: state[key] for key in PERSISTED_KEYS if key in state}
    STATE_FILE.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
