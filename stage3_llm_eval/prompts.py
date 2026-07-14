"""Stage 3 prompt templates. Full raw config + one verbatim CIS control -> verdict."""

SYSTEM_PROMPT = (
    "You are a network security compliance auditor. You are given a device's "
    "full raw configuration and the verbatim text of one CIS Benchmark control. "
    "Decide whether the configuration is COMPLIANT, NON_COMPLIANT, or N/A "
    "(the control's feature is not applicable or not present) with that control. "
    "Base your verdict only on the configuration text and the control text provided. "
    "Respond with a verdict and one line of reasoning."
)


def build_user_prompt(config_text: str, control: dict) -> str:
    return (
        f"CIS Control {control['control_id']}: {control['title']}\n\n"
        f"{control['raw_text']}\n\n"
        f"--- Device Configuration ---\n{config_text}"
    )
