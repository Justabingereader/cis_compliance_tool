"""Connect Device panel. Calls stage1_collector; stores config in session state."""

import streamlit as st

from stage1_collector import cisco, junos, pfsense


def render() -> None:
    st.header("Connect Device")

    vendor = st.selectbox("Vendor", options=["pfsense", "cisco", "junos"])
    host = st.text_input("Host / IP address")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Connect and Collect Config"):
        try:
            with st.spinner(f"Connecting to {host}..."):
                if vendor == "cisco":
                    config_text = cisco.collect(host, username, password)
                elif vendor == "junos":
                    config_text = junos.collect(host, username, password)
                else:
                    config_text = pfsense.collect(host, username, password)
        except Exception as exc:
            st.error(f"Connection failed: {exc}")
        else:
            st.session_state.config_text = config_text
            st.session_state.connected_vendor = vendor
            st.session_state.connected_host = host
            st.success(f"Connected to {host} ({vendor}) — config collected.")

    if st.session_state.config_text is not None:
        with st.expander(
            f"Raw collected config — {st.session_state.connected_vendor} "
            f"({st.session_state.connected_host})"
        ):
            st.code(st.session_state.config_text, language="text")