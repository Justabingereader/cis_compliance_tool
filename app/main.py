import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app import connect_device, run_evaluation, view_history

# Page config — must be the first Streamlit call in the script

st.set_page_config(
    page_title="CIS Benchmark Compliance Tool",
    layout="wide",
)



# Session state — the ONLY data that survives Streamlit's rerun-on-interaction

def init_session_state() -> None:
    defaults = {
        "config_text": None,        # raw device config (str) from Stage 1
        "connected_vendor": None,   # "pfsense" | "cisco" | "junos"
        "connected_host": None,     # for display only
        "results": [],              # list of verdict dicts from Stage 3
        "batch_id": None,           # OpenAI Batch API job id, Stage 3
        "run_id": None,             # results/<run_id> folder for the current run, Stage 4
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()



# Sidebar navigation

st.sidebar.title("CIS Compliance Tool")

page = st.sidebar.radio(
    "Navigate",
    options=["Connect Device", "Run Evaluation", "History"],
)

# Connection status indicator, visible on every page
st.sidebar.divider()
if st.session_state.connected_vendor:
    st.sidebar.success(
        f"Connected: {st.session_state.connected_vendor} "
        f"({st.session_state.connected_host})"
    )
else:
    st.sidebar.info("No device connected")



# Routing — each panel is a render() function in its own module

if page == "Connect Device":
    connect_device.render()
elif page == "Run Evaluation":
    run_evaluation.render()
elif page == "History":
    view_history.render()