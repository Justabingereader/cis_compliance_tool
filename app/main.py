import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app import connect_device, run_evaluation, state_store, view_history
from stage3_llm_eval import evaluate
from stage4_report import report

# Page config — must be the first Streamlit call in the script

st.set_page_config(
    page_title="CIS Benchmark Compliance Tool",
    layout="wide",
)



# Session state — restored from disk (state_store) on a fresh browser
# session/refresh, since st.session_state alone doesn't survive a page reload.

def init_session_state() -> None:
    persisted = state_store.load()
    defaults = {
        "config_text": persisted.get("config_text"),        # raw device config (str), Stage 1
        "connected_vendor": persisted.get("connected_vendor"),  # "pfsense" | "cisco" | "junos"
        "connected_host": persisted.get("connected_host"),   # for display only
        "results": persisted.get("results", []),              # list of verdict dicts, Stage 3
        "batch_id": persisted.get("batch_id"),                # OpenAI Batch API job id, Stage 3
        "run_id": persisted.get("run_id"),                    # results/<run_id> folder, Stage 4
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()



# Sidebar navigation

st.sidebar.title("CIS Compliance Tool")

# Instantiated before the Refresh button so it's always "touched" on every
# rerun (including the one that calls st.rerun() below) — otherwise Streamlit
# can drop its remembered selection and snap back to the first option.
page = st.sidebar.radio(
    "Navigate",
    options=["Connect Device", "Run Evaluation", "History"],
    key="nav_page",
)

if st.sidebar.button("🔄 Refresh"):
    persisted = state_store.load()
    for key, value in persisted.items():
        st.session_state[key] = value

    if st.session_state.batch_id and not st.session_state.results:
        try:
            status = evaluate.check_batch_status(st.session_state.batch_id)
            if status["status"] == "completed":
                results = evaluate.retrieve_results(st.session_state.batch_id)
                report.save_results(st.session_state.run_id, results)
                st.session_state.results = results
        except Exception as exc:
            st.sidebar.warning(f"Could not refresh batch status: {exc}")

    st.rerun()

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



# Persist current state to disk on every rerun, so a page refresh (which
# wipes st.session_state entirely) can restore from here on next load.
state_store.save(dict(st.session_state))