"""Stage 2: CIS benchmark control loader."""

import json
from pathlib import Path

CONTROLS_DIR = Path(__file__).resolve().parent / "controls"

_VENDOR_FILES = {
    "cisco": "ios_output_l1.json",
    "junos": "junos_output_l1.json",
    "pfsense": "pfsense_output_l1.json",
}


def load_controls(vendor: str) -> list[dict]:
    """Load the CIS Level 1 controls for a vendor (pfsense | cisco | junos)."""
    path = CONTROLS_DIR / _VENDOR_FILES[vendor]
    with open(path, encoding="utf-8") as f:
        return json.load(f)
