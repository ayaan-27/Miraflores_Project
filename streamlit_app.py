from __future__ import annotations

import re
from uuid import uuid4

import pandas as pd
import streamlit as st

from variance_workspace.data import CATALOG, SAMPLES, Workspace, parse_ledger, dollars
from variance_workspace.model import DATA_ROOT
from variance_workspace.runtime import get_service
from variance_workspace.exports import workpaper, journal_csv, review_json


def money(cents):
    return f"${cents / 100:,.2f}"


def execute(operation, label="Investigating"):
    with st.status(label, expanded=True) as status:
        def progress(update):
            for name, data in update.items():
                if name == "__interrupt__": continue
                for item in data.get("trace", []):
                    if item["title"] != "Evidence query completed": st.write(item["title"])
        try:
            operation(progress)
            status.update(label="Investigation complete", state="complete", expanded=False)
            st.rerun()
        except ValueError as error:
            status.update(label="Investigation stopped", state="error", expanded=False)
            st.error(str(error))


def render_sources(service, state):
    for identifier, source in state["analysis"]["sources"].items():
        label = source.get("filename", source.get("title", identifier))
        with st.expander(label):
            if source.get("rows") is not None:
                rows = [{"Date": r["date"], "Vendor": r["vendor"], "Description": r["description"], "Amount": money(r["amount_cents"]), "Document": r["document_id"]} for r in source["rows"]]
                st.dataframe(rows, hide_index=True, width="stretch")
            else:
                st.dataframe([{"Field": key, "Value": fact["value"], "Page": fact["page"], "Source quote": fact["quote"]} for key, fact in source["fields"].items()], hide_index=True, width="stretch")
                st.download_button("Download PDF", service.workspace.pdf(identifier), source["filename"], "application/pdf", key="source_"+identifier, on_click="ignore")
                if st.checkbox("Preview", key="preview_"+identifier):
                    st.pdf(service.workspace.pdf(identifier), height=500, key="pdf_"+identifier, alt=label)


def render_review(service, state):
    if state["status"] == "awaiting_review":
        st.subheader("Review", divider="gray")
        with st.form("review_"+state["id"]+"_"+str(state["round"])):
            reviewer = st.text_input("Reviewer", value=st.session_state.get("last_reviewer", ""), key="reviewer_name")
            note = st.text_area("Review note", key="review_note", height=90)
            cols = st.columns(3)
            approve = cols[0].form_submit_button("Approve workpaper", type="primary", disabled=not state["analysis"]["approval_allowed"])
            request = cols[1].form_submit_button("Request evidence", disabled=not state["analysis"].get("missing_document_id") or state["round"] >= 3)
            hold = cols[2].form_submit_button("Record hold")
        if approve or request or hold:
            action = "approve" if approve else "request_evidence" if request else "hold"
            st.session_state["last_reviewer"] = reviewer
            execute(lambda callback: service.review(state["id"], {"action": action, "reviewer": reviewer, "note": note}, callback), "Saving review")
    elif state["status"] == "awaiting_evidence":
        st.subheader("Additional evidence", divider="gray")
        expected = state["analysis"]["missing_document_id"]
        driver = state["analysis"]["driver"]
        st.text_area("Request draft", f"Please provide {expected} supporting {driver['document_id']} from {driver['vendor']}. Include the service dates, agreed amount, and authorization. This request has not been sent.", height=100, key="request_"+state["id"]+str(state["round"]))
        with st.form("evidence_"+state["id"]+str(state["round"])):
            upload = st.file_uploader("Supporting PDF", type=["pdf"], help="Use sample documents only. Maximum 2 MB.", key="evidence_file")
            add = st.form_submit_button("Add evidence", type="primary")
        if add:
            if upload is None: st.error("Choose a supporting PDF first.")
            else: execute(lambda callback: service.reply(state["id"], upload.getvalue(), upload.name, callback))
        sample = CATALOG["documents"].get(expected)
        if sample and not sample["available"]:
            col1, col2 = st.columns([1, 2])
            col1.download_button("Sample agreement", (SAMPLES / sample["file"]).read_bytes(), sample["file"], "application/pdf", on_click="ignore")
            if col2.button("Use sample agreement", key="sample_agreement"):
                execute(lambda callback: service.reply(state["id"], (SAMPLES / sample["file"]).read_bytes(), sample["file"], callback))


def render_case(service, account):
    st.subheader(account["name"])
    cols = st.columns(3)
    cols[0].metric("September", money(account["previous_cents"]))
    cols[1].metric("October", money(account["current_cents"]))
    cols[2].metric("Change", money(account["change_cents"]))
    identifier = service.latest(account["code"])
    if not identifier:
        if st.button("Investigate", type="primary", key="investigate", disabled=not account["material"]):
            execute(lambda callback: service.start(account["code"], callback))
        if not account["material"]: st.caption("Below the review threshold.")
        return
    state = service.view(identifier)
    if state.get("error"):
        st.error(state["error"])
        if st.button("Retry investigation", key="retry"):
            execute(lambda callback: service.retry(identifier, callback))
        return
    analysis = state.get("analysis")
    if not analysis:
        st.info("This investigation has not reached a conclusion.")
        return
    summary, evidence, activity = st.tabs(["Findings", "Evidence", "Activity"])
    with summary:
        if state.get("completion"):
            if state["completion"]["outcome"] == "workpaper_approved": st.success("Workpaper approved")
            else: st.warning("Hold recorded")
        elif analysis["outcome"] == "evidence_needed": st.warning("Service dates or supporting evidence are missing.")
        elif analysis["outcome"] == "hold": st.warning("The findings need further investigation.")
        elif analysis["outcome"] == "adjustment_proposed": st.info("An adjustment is proposed for review.")
        else: st.success("The movement is supported by the supplied evidence.")
        if state.get("memo"): st.write(state["memo"]["summary"])
        for finding in analysis["findings"]:
            with st.expander(finding["name"], expanded=not finding["passed"]):
                st.write(finding["detail"])
                st.caption("Sources: " + ", ".join(finding["source_ids"]))
        if analysis["journal"]:
            st.subheader("Proposed adjustment")
            st.dataframe([{"Account": f"{r['account']} · {r['name']}", "Debit": dollars(r["debit_cents"]), "Credit": dollars(r["credit_cents"])} for r in analysis["journal"]], hide_index=True, width="stretch")
            st.caption(f"Balance after the proposed adjustment: {money(analysis['adjusted_cents'])}. Entries remain drafts.")
            with st.expander("Allocation schedule"):
                st.dataframe([{"Month": r["period"], "Expense": dollars(r["expense_cents"])} for r in analysis["allocation"]], hide_index=True, width="stretch")
        render_review(service, state)
        if state.get("history"):
            with st.expander("Review history"):
                for item in state["history"]:
                    st.write(f"**{item['reviewer']}** · {item['action'].replace('_', ' ')} · Round {item['round']}")
                    st.write(item["note"])
        st.divider()
        exports = st.columns(3)
        exports[0].download_button("Workpaper PDF", workpaper(state), "month-end-workpaper.pdf", "application/pdf", key="workpaper", on_click="ignore")
        exports[1].download_button("Journal CSV", journal_csv(state), "proposed-journal.csv", "text/csv", disabled=not bool(analysis["journal"]), key="journal", on_click="ignore")
        exports[2].download_button("Review record", review_json(state), "review-record.json", "application/json", key="record", on_click="ignore")
    with evidence: render_sources(service, state)
    with activity:
        for item in state.get("trace", []):
            with st.expander(item["title"]):
                st.caption(f"Step {item['stage']} · {item['at']}")
                st.json(item["data"], expanded=False)


def main():
    st.set_page_config(page_title="Month-end review", layout="wide", initial_sidebar_state="collapsed")
    st.markdown("""<style>
      .block-container {max-width:1240px;padding-top:2rem;padding-bottom:3rem}
      [data-testid="stToolbar"] {display:none}
      h1 {font-size:1.85rem!important;letter-spacing:-.035em}
      h2 {font-size:1.3rem!important;letter-spacing:-.02em}
      [data-testid="stMetricValue"] {font-size:1.65rem}
      div[data-testid="stForm"] {border-color:#e6eaf0;border-radius:10px}
      button {border-radius:7px!important}
    </style>""", unsafe_allow_html=True)
    key = str(st.query_params.get("w", ""))
    if not re.fullmatch(r"[a-f0-9]{32}", key):
        key = uuid4().hex
        st.query_params["w"] = key
    service = get_service(key)
    title, actions = st.columns([4, 1])
    with title:
        st.title("Month-end review")
        st.caption("October 2026 · Sample data")
    with actions:
        with st.popover("Import ledger"):
            st.download_button("Sample ledger", (SAMPLES / "ledger.csv").read_bytes(), "ledger.csv", "text/csv", on_click="ignore")
            with st.form("import_ledger"):
                ledger = st.file_uploader("Expense ledger CSV", type=["csv"], help="Use sample data only. Maximum 1 MB.", key="ledger_file")
                load = st.form_submit_button("Load ledger")
            if load:
                try:
                    if ledger is None: raise ValueError("Choose a ledger first.")
                    data = ledger.getvalue(); parse_ledger(data)
                    new_key = uuid4().hex
                    Workspace(DATA_ROOT / "workspaces" / new_key, data)
                    st.query_params["w"] = new_key
                    st.rerun()
                except ValueError as error: st.error(str(error))
    st.divider()
    left, right = st.columns([1, 3], gap="large")
    accounts = service.workspace.accounts()
    with left:
        st.markdown("#### Accounts")
        selected = st.radio("Account", [a["code"] for a in accounts], format_func=lambda code: CATALOG["accounts"][code], label_visibility="collapsed", key="account_choice")
        st.caption("Review threshold: $5,000 and 20%.")
    with right:
        render_case(service, next(a for a in accounts if a["code"] == selected))


if __name__ == "__main__":
    main()
