"""History panel — browse, view, and download past evaluation runs from Stage 4."""

import json

import streamlit as st

from app.run_evaluation import sync_pending_runs
from stage4_report import report


@st.dialog("Raw Config", width="large")
def _view_config_dialog(run_id: str) -> None:
    st.code(report.get_config(run_id), language="text")


def _render_results_and_ground_truth(run_id: str) -> None:
    st.divider()
    st.write(
        "Mark each control's actual correct verdict below to build the accuracy "
        "table — edits save automatically as you go, so partial progress "
        "survives a page reload. Accuracy metrics appear once every control "
        "below is labeled."
    )

    results = report.get_results(run_id)

    # Seed the editor's rows from disk only once per run per session — passing
    # a freshly rebuilt list on every rerun (even with identical content)
    # fights with data_editor's own key-tracked edit state and makes a
    # just-made selection appear to revert until it's repeated.
    seed_key = f"gt_editor_seed_{run_id}"
    if seed_key not in st.session_state:
        ground_truth = report.get_ground_truth(run_id)
        st.session_state[seed_key] = [
            {
                "control_id": r["control_id"],
                "llm_verdict": r["verdict"],
                "automated": r.get("automated"),
                "reasoning": r["reasoning"],
                "ground_truth": ground_truth.get(r["control_id"], ""),
            }
            for r in results
        ]

    edited_rows = st.data_editor(
        st.session_state[seed_key],
        column_config={
            "control_id": st.column_config.TextColumn("Control", disabled=True),
            "llm_verdict": st.column_config.TextColumn("LLM Verdict", disabled=True),
            "automated": st.column_config.CheckboxColumn("Automated", disabled=True),
            "reasoning": st.column_config.TextColumn("Reasoning", disabled=True),
            "ground_truth": st.column_config.SelectboxColumn(
                "Ground Truth",
                options=["", *report.CIS_CLASSES],
                required=False,
            ),
        },
        use_container_width=True,
        hide_index=True,
        key=f"gt_editor_{run_id}",
    )

    report.save_ground_truth(
        run_id, {row["control_id"]: row["ground_truth"] for row in edited_rows}
    )

    labeled_count = sum(1 for row in edited_rows if row["ground_truth"])
    total_count = len(edited_rows)
    if labeled_count < total_count:
        st.info(
            f"{labeled_count}/{total_count} controls labeled and saved — "
            "finish labeling every control to see accuracy metrics."
        )
        return

    metrics = report.save_metrics(run_id)
    if metrics is None:
        return

    st.divider()
    st.subheader(f"Accuracy vs. Ground Truth ({metrics['n_labeled']} labeled)")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Accuracy", f"{metrics['accuracy'] * 100:.1f}%")
    m2.metric("Macro Precision", metrics["macro_precision"])
    m3.metric("Macro Recall", metrics["macro_recall"])
    m4.metric("Macro F1", metrics["macro_f1"])

    st.write("**Confusion Matrix** (rows = actual, columns = predicted)")
    cm = metrics["confusion_matrix"]
    cm_rows = [{"Actual \\ Predicted": actual, **cm[actual]} for actual in report.CIS_CLASSES]
    st.dataframe(cm_rows, use_container_width=True, hide_index=True)

    st.write("**Per-Class Metrics**")
    per_class_rows = [{"Class": c, **metrics["per_class"][c]} for c in report.CIS_CLASSES]
    st.dataframe(per_class_rows, use_container_width=True, hide_index=True)


def _render_run(run: dict) -> None:
    run_id = run["run_id"]
    status_emoji = {"pending": "⏳", "completed": "✅", "failed": "❌"}.get(run["status"], "•")

    score = run["percent_compliant"]
    label = run.get("label")
    display_id = f"{label}_{run_id}" if label else run_id
    title = f"{status_emoji} {display_id}"
    if score is not None:
        title += f" — {score}% compliant"

    check_col, expander_col = st.columns([1, 20])
    with check_col:
        st.checkbox(
            "Select for deletion",
            key=f"select_{run_id}",
            label_visibility="collapsed",
        )
    with expander_col:
        _render_run_details(run, title)


def _render_run_details(run: dict, title: str) -> None:
    run_id = run["run_id"]
    score = run["percent_compliant"]
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

        show_results_key = f"show_results_{run_id}"

        with view_col:
            if st.button("View Config", key=f"view_config_{run_id}"):
                _view_config_dialog(run_id)
            if st.button(
                "View Results", key=f"view_results_{run_id}", disabled=not run["has_results"]
            ):
                st.session_state[show_results_key] = not st.session_state.get(
                    show_results_key, False
                )

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
                ground_truth = report.get_ground_truth(run_id)
                if ground_truth:
                    st.download_button(
                        "Download Ground Truth",
                        data=json.dumps(ground_truth, indent=2),
                        file_name=f"{run_id}_ground_truth.json",
                        mime="application/json",
                        key=f"dl_gt_{run_id}",
                    )
                if run["has_metrics"]:
                    st.download_button(
                        "Download Ground Truth Metrics",
                        data=json.dumps(report.get_metrics(run_id), indent=2),
                        file_name=f"{run_id}_ground_truth_metrics.json",
                        mime="application/json",
                        key=f"dl_gt_metrics_{run_id}",
                    )
            label = run.get("label")
            zip_name = f"{label}_{run_id}.zip" if label else f"{run_id}.zip"
            st.download_button(
                "Download Folder (.zip)",
                data=report.zip_run(run_id),
                file_name=zip_name,
                mime="application/zip",
                key=f"dl_zip_{run_id}",
            )

        if st.session_state.get(show_results_key, False):
            _render_results_and_ground_truth(run_id)


def render() -> None:
    st.header("History")

    if sync_pending_runs():
        st.toast("A pending batch finished and was saved.", icon="✅")

    runs = report.list_runs()
    if not runs:
        st.info("No evaluation runs yet — submit one from Run Evaluation.")
        return

    st.download_button(
        "⬇️ Download All Runs (.zip)",
        data=report.zip_all_runs(),
        file_name="all_runs.zip",
        mime="application/zip",
        key="dl_all_runs_zip",
    )

    selected_ids = [r["run_id"] for r in runs if st.session_state.get(f"select_{r['run_id']}")]

    if st.button(
        f"🗑️ Delete Selected ({len(selected_ids)})",
        disabled=not selected_ids,
        key="delete_selected_btn",
    ):
        st.session_state["pending_delete_ids"] = selected_ids

    pending_ids = st.session_state.get("pending_delete_ids")
    if pending_ids:
        with st.container(border=True):
            st.warning(
                f"Permanently delete {len(pending_ids)} run(s)? This removes all "
                "files on disk (config, results, ground truth) and cannot be undone."
            )
            for run_id in pending_ids:
                st.write(f"- {run_id}")
            confirm_col, cancel_col = st.columns(2)
            if confirm_col.button("Confirm Delete", key="confirm_delete_btn", type="primary"):
                for run_id in pending_ids:
                    report.delete_run(run_id)
                    st.session_state.pop(f"select_{run_id}", None)
                st.session_state.pop("pending_delete_ids", None)
                st.success(f"Deleted {len(pending_ids)} run(s).")
                st.rerun()
            if cancel_col.button("Cancel", key="cancel_delete_btn"):
                st.session_state.pop("pending_delete_ids", None)
                st.rerun()

    st.divider()

    for run in runs:
        _render_run(run)
