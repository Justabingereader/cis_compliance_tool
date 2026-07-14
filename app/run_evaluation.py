"""Run Evaluation panel. Submits and tracks a Stage 3 OpenAI Batch API job."""

import streamlit as st

from stage3_llm_eval import evaluate
from stage4_report import report


def render() -> None:
    st.header("Run Evaluation")

    if st.session_state.config_text is None:
        st.info("Connect a device first — no config loaded.")
        return

    st.write(f"Config loaded from: {st.session_state.connected_host}")

    if st.session_state.batch_id is None:
        if st.button("Submit Evaluation Batch"):
            vendor = st.session_state.connected_vendor
            host = st.session_state.connected_host
            config_text = st.session_state.config_text
            try:
                with st.spinner("Submitting batch job..."):
                    batch_id = evaluate.submit_batch(vendor, config_text)
                    run_id = report.create_run(vendor, host, config_text, batch_id)
            except Exception as exc:
                st.error(f"Batch submission failed: {exc}")
            else:
                st.session_state.batch_id = batch_id
                st.session_state.run_id = run_id
                st.success(f"Batch submitted: {batch_id}")
        return

    st.write(f"Batch ID: `{st.session_state.batch_id}`")

    if st.button("Check Status"):
        try:
            status = evaluate.check_batch_status(st.session_state.batch_id)
        except Exception as exc:
            st.error(f"Status check failed: {exc}")
        else:
            st.write(
                f"Status: **{status['status']}** — "
                f"{status['completed']}/{status['total']} completed, "
                f"{status['failed']} failed"
            )
            if status["status"] == "completed":
                try:
                    results = evaluate.retrieve_results(st.session_state.batch_id)
                    report.save_results(st.session_state.run_id, results)
                except Exception as exc:
                    st.error(f"Failed to retrieve results: {exc}")
                else:
                    st.session_state.results = results
                    st.success(f"{len(results)} verdicts retrieved and saved to results/.")

    if st.session_state.results:
        st.subheader("Results")
        st.dataframe(st.session_state.results, use_container_width=True)

    if st.button("Start New Evaluation"):
        st.session_state.batch_id = None
        st.session_state.run_id = None
        st.session_state.results = []
