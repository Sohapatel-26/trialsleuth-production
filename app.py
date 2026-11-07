"""app.py: the TrialSleuth screen.  Run with:  streamlit run app.py

Left:   the drug candidate a company submits before its human trial, and the agent's risk report.
Right:  what Hindsight recalled (body knowledge, past drug outcomes, earlier reviews).
Sidebar: memory on/off for the before/after demo, and "Teach the agent a new result".
"""
import json
from pathlib import Path

import streamlit as st

import agent
import memory

st.set_page_config(page_title="TrialSleuth AI", layout="wide")

DATA = Path(__file__).parent / "data"
DEMO = json.loads((DATA / "demo_candidate.json").read_text(encoding="utf-8"))
NEW_RESULT = json.loads((DATA / "demo_new_result.json").read_text(encoding="utf-8"))

if "result" not in st.session_state:
    st.session_state.result = None
    st.session_state.history = []   # (candidate name, memory on/off, risk line)

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("TrialSleuth AI")
    st.caption("Pre-trial drug safety review with memory")
    use_memory = st.toggle("Use Hindsight memory", value=True,
                           help="Off = a plain AI with no memory of body knowledge or past drugs.")

    st.divider()
    st.subheader("Teach the agent a new result")
    st.caption("A lab or trial result from any drug. Every later review is checked against it.")
    with st.form("teach"):
        t1, t2 = st.columns(2)
        rid = t1.text_input("ID", NEW_RESULT["id"])
        rdate = t2.text_input("Date", NEW_RESULT["date"])
        compound = st.text_input("Compound", NEW_RESULT["compound"])
        rclass = st.text_input("Drug class", NEW_RESULT["drug_class"])
        features = st.text_input("Features", NEW_RESULT["features"])
        outcome = st.text_area("What happened", NEW_RESULT["outcome"])
        change = st.text_area("Change that worked", NEW_RESULT["change_that_worked"])
        if st.form_submit_button("Save result to memory"):
            with st.spinner("Retaining in Hindsight..."):
                try:
                    memory.save_past_drug(dict(id=rid, date=rdate, compound=compound, drug_class=rclass,
                                               features=features, outcome=outcome, change_that_worked=change))
                    st.success(f"{rid} saved. Review the drug again to see it used.")
                except Exception as e:
                    st.error(f"Could not save: {e}")

# ---------------- Main ----------------
st.title("Check a drug before any human takes it")
st.caption("A company submits its drug candidate before the human trial. TrialSleuth checks it against "
           "remembered human-body knowledge and the outcomes of past drugs, flags risks by body system, "
           "and suggests changes. It does not declare a drug safe; experts make the final call.")

left, right = st.columns([3, 2], gap="large")

with left:
    with st.form("candidate"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Drug name", DEMO["name"])
        drug_class = c2.text_input("Drug class", DEMO["drug_class"])
        composition = st.text_area("Composition (active ingredient, structure, excipients)", DEMO["composition"])
        dose = st.text_input("Dose and route", DEMO["dose"])
        patients = st.text_area("Patients in the trial", DEMO["patients"], height=68)
        trial_design = st.text_input("Trial design", DEMO["trial_design"])
        other_medicines = st.text_input("Other medicines allowed", DEMO["other_medicines"])
        known_lab_data = st.text_area("Known lab and animal data", DEMO["known_lab_data"], height=68)
        submitted = st.form_submit_button("Review before human trial", type="primary")

    if submitted:
        candidate = dict(name=name, drug_class=drug_class, composition=composition, dose=dose, patients=patients,
                         trial_design=trial_design, other_medicines=other_medicines, known_lab_data=known_lab_data)
        with st.spinner("Recalling body knowledge and past drug outcomes..." if use_memory else "Reviewing without memory..."):
            try:
                st.session_state.result = agent.review(candidate, use_memory=use_memory)
            except Exception as e:
                st.session_state.result = {"answer": f"Memory is unavailable right now: {e}", "memories": [], "chunks": {}}
        st.session_state.result["memory_on"] = use_memory
        risk = next((l for l in st.session_state.result["answer"].splitlines() if "Risk level" in l), "")
        st.session_state.history.append((name, use_memory, risk.replace("**", "")))

    res = st.session_state.result
    if res:
        st.subheader("Safety review" + ("" if res.get("memory_on") else " (memory OFF)"))
        st.markdown(res["answer"])

    if st.session_state.history:
        with st.expander(f"Reviews this session ({len(st.session_state.history)})"):
            for i, (n, mem, risk) in enumerate(st.session_state.history, start=1):
                st.write(f"{i}. {n} · memory {'ON' if mem else 'OFF'} · {risk}")

with right:
    st.subheader("Hindsight memory")
    res = st.session_state.result
    if not res:
        st.info("Review a drug to see what the agent remembers.")
    elif not res.get("memory_on"):
        st.warning("Memory was OFF for this review: the AI had no body knowledge or past drug outcomes.")
    else:
        records = agent.source_records(res["memories"], res["chunks"])
        groups = [
            ("Past drug outcomes", "💊", [r for r in records if r.startswith("Past drug outcome")]),
            ("Human body knowledge", "🫀", [r for r in records if r.startswith("Human body knowledge")]),
            ("Earlier reviews", "🗂️", [r for r in records if r.startswith("Earlier TrialSleuth review")]),
        ]
        st.markdown(f"**{len(records)} memories recalled**")
        for title, icon, items in groups:
            if items:
                st.markdown(f"**{title}**")
                for r in items:
                    head = r.split(":")[0]
                    with st.expander(f"{icon} {head}", expanded=(title == "Past drug outcomes")):
                        st.write(r)
        if not records:
            for m in res["memories"]:
                st.write(f"- {m.text}")

    st.divider()
    if st.button("What has the agent learned? (reflect)"):
        with st.spinner("Hindsight is reflecting on everything it remembers (10 to 30 seconds)..."):
            try:
                st.markdown(memory.reflect(
                    "Across all past drug outcomes and reviews, what are the 3 to 5 most important lessons for "
                    "making a new drug candidate safer before its first human trial? Cite the IDs."))
            except Exception as e:
                st.error(f"Reflect failed: {e}")
