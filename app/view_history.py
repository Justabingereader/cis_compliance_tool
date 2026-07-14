"""History panel — browse, view, and download past evaluation runs from Stage 4."""

import json

import streamlit as st

from stage4_report import report


@st.dialog("Raw Config", width="large")
def _view_config_dialog(run_id: str) -> None:
    st.code(report.get_config(run_id), language="text")


@st.dialog("LLM Results", width="large")
def _view_results_dialog(run_id: str) -> None:
    metadata = report.get_metadata(run_id)
    if metadata["percent_compliant"] is not None:
        st.subheader(f"{metadata['percent_compliant']}% compliant")
        m1, m2, m3 = st.columns(3)
        m1.metric("Compliant", metadata["compliant_count"])
        m2.metric("Non-Compliant", metadata["non_compliant_count"])
        m3.metric("N/A", metadata["na_count"])
        a1, a2 = st.columns(2)
        a1.metric("Automated Controls", metadata["automated_count"])
        a2.metric("Manual Controls", metadata["manual_count"])
        st.divider()

    results = report.get_results(run_id)
    st.dataframe(results, use_container_width=True)


def _render_run(run: dict) -> None:
    run_id = run["run_id"]
    status_emoji = {"pending": "⏳", "completed": "✅", "failed": "❌"}.get(run["status"], "•")

    score = run["percent_compliant"]
    title = f"{status_emoji} {run_id}"
    if score is not None:
        title += f" — {score}% compliant"

    with st.expander(title):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Vendor:** {run['vendor']}")
            st.write(f"**Host:** {run['host']}")
            st.write(f"**Batch ID:** `{run['batch_id']}`")
        with col2:
            st.write(f"**Status:** {run['status']}")
            st.write(f"**Submitted:** {run['submitted_at']}")
            if run["num_controls"] is not None:
                st.write(f"**Controls evaluated:** {run['num_controls']}")

        if score is not None:
            st.divider()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Compliance Score", f"{score}%")
            m2.metric("Compliant", run["compliant_count"])
            m3.metric("Non-Compliant", run["non_compliant_count"])
            m4.metric("N/A", run["na_count"])
            a1, a2 = st.columns(2)
            a1.metric("Automated Controls", run["automated_count"])
            a2.metric("Manual Controls", run["manual_count"])

        st.divider()

        view_col, dl_col = st.columns(2)

        with view_col:
            if st.button("View Config", key=f"view_config_{run_id}"):
                _view_config_dialog(run_id)
            if st.button(
                "View Results", key=f"view_results_{run_id}", disabled=not run["has_results"]
            ):
                _view_results_dialog(run_id)

        with dl_col:
            st.download_button(
                "Download Config",
                data=report.get_config(run_id),
                file_name=f"{run_id}_config.txt",
                mime="text/plain",
                key=f"dl_config_{run_id}",
            )
            if run["has_results"]:
                st.download_button(
                    "Download Results",
                    data=json.dumps(report.get_results(run_id), indent=2),
                    file_name=f"{run_id}_results.json",
                    mime="application/json",
                    key=f"dl_results_{run_id}",
                )
                st.download_button(
                    "Download Report",
                    data=json.dumps(run, indent=2),
                    file_name=f"{run_id}_report.json",
                    mime="application/json",
                    key=f"dl_report_{run_id}",
                )
            st.download_button(
                "Download Folder (.zip)",
                data=report.zip_run(run_id),
                file_name=f"{run_id}.zip",
                mime="application/zip",
                key=f"dl_zip_{run_id}",
            )


def render() -> None:
    st.header("History")

    runs = report.list_runs()
    if not runs:
        st.info("No evaluation runs yet — submit one from Run Evaluation.")
        return

    for run in runs:
        _render_run(run)
