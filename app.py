import streamlit as st
from triage import triage_ticket

st.set_page_config(page_title="Ticket Triage", layout="wide")
st.title("Support Ticket Triage and Missing-Info Detector")

examples = {
    "(write my own)": ("", ""),
    "Good L3 ticket": ("Desktop app crashes when opening a large file",
        "The app crashes with a segfault as soon as I open a file bigger than 2 GB.\nOS: Ubuntu 22.04\nVersion: 2.3.1\nSteps to reproduce:\n1. launch the app\n2. open big.csv\n3. the window closes\n```\nSegmentation fault (core dumped)\n```"),
    "L3 with missing details": ("Database deadlock in nightly pipeline",
        "The nightly job hits a deadlock sometimes and the load never finishes."),
    "Vague serious ticket": ("App crashes", "It crashes sometimes, please fix."),
    "How-to question": ("Change theme color", "How do I change the theme color of the dashboard?"),
    "Production outage": ("Outage", "Production is down, all users affected. Deployment pipeline failed after the release."),
    "Empty ticket": ("", ""),
    "One word": ("broken", ""),
    "Out of domain": ("Pizza order", "I want to order a large pizza with extra cheese for delivery tonight."),
}

choice = st.selectbox("Load an example", list(examples.keys()))
title = st.text_input("Ticket title", value=examples[choice][0], key="title_" + choice)
body = st.text_area("Ticket body", value=examples[choice][1], height=200, key="body_" + choice)

if st.button("Triage this ticket"):
    r = triage_ticket(title, body)

    if r["status"] == "Needs Clarification":
        st.warning("Status: Needs Clarification")
    else:
        st.success("Status: " + r["status"])

    if r["team"] is not None:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Team", r["team"])
        col2.metric("Priority", r["priority"])
        col3.metric("Level", r["level"])
        col4.metric("Top team probability", r["team_confidence"])

        st.write("Why this priority:", r["priority_reason"])
        st.write("Why this level:", r["level_reason"])
        st.write("Team check:", r["team_status"], "| options:", ", ".join(r["team_options"]) or "none",
                 "| closest past ticket similarity:", r["closest_similarity"])

    if r["reasons"]:
        st.subheader("Review notes")
        for reason in r["reasons"]:
            st.write("- " + reason)

    if r["checklist"]:
        st.subheader("Ask the reporter for")
        for item in r["checklist"]:
            st.checkbox(item, value=False, key=item)

    if r["similar"]:
        st.subheader("Most similar past tickets")
        for t in r["similar"]:
            st.write("- " + str(t))