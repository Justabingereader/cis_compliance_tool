"""Run Evaluation panel. Calls stage2 loader + stage3 evaluation loop."""

import streamlit as st


def render() -> None:
    st.header("Run Evaluation")

    if st.session_state.config_text is None:
        st.info("Connect a device first — no config loaded.")
        return

    st.write(f"Config loaded from: {st.session_state.connected_host}")