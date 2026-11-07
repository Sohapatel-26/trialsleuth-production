"""app.py: the TrialSleuth screen.  Run with:  streamlit run app.py

Left:  the site coordinator's chat.
Right: what Hindsight recalled for the last question (the agent's "memory").
Sidebar: pick the site, switch memory of past rulings on/off, add a new Medical Monitor ruling.
"""
import json
from pathlib import Path

import streamlit as st

import agent
import memory

st.set_page_config(page_title="TrialSleuth AI", layout="wide")

SITES = ["Bangalore", "London", "Boston", "Madrid", "Singapore", "Sao Paulo"]
DEMO_RULING = json.loads((Path(__file__).parent / "data" / "demo_ruling.json").read_text(encoding="utf-8"))

if "chat" not in st.session_state:
    st.session_state.chat = []          # list of {"role", "content"}
    st.session_state.last = None        # last agent result, for the memory panel

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("TrialSleuth AI")
    st.caption("Trial ONC-301 · 6 hospital sites")
    site = st.selectbox("Your site", SITES)
    use_rulings = st.toggle("Use memory of past rulings", value=True,
                            help="Off = the agent only knows the protocol, like a normal document chatbot.")

    st.divider()
    st.subheader("Add Medical Monitor ruling")
    st.caption("Saved to Hindsight. Every site benefits immediately.")
    with st.form("ruling", clear_on_submit=False):
        c1, c2 = st.columns(2)
        case_id = c1.text_input("Case #", DEMO_RULING["case_id"])
        r_site = c2.selectbox("Site", SITES, index=SITES.index(DEMO_RULING["site"]))
        c3, c4 = st.columns(2)
        date = c3.text_input("Date", DEMO_RULING["date"])
        decision = c4.selectbox("Decision", ["Accepted", "Rejected"])
        topic = st.selectbox("Topic", ["lab-window", "temperature", "dosing", "storage", "ae-reporting", "withdrawal"])
        situation = st.text_area("Situation", DEMO_RULING["situation"])
        ruling = st.text_area("Ruling", DEMO_RULING["ruling"])
        reason = st.text_area("Reason", DEMO_RULING["reason"])
        if st.form_submit_button("Save ruling to memory"):
            with st.spinner("Retaining in Hindsight..."):
                try:
                    memory.save_ruling(dict(case_id=case_id, site=r_site, date=date, topic=topic,
                                            decision=decision, situation=situation, ruling=ruling, reason=reason))
                    st.success(f"Case #{case_id} saved. All sites can now use it.")
                except Exception as e:
                    st.error(f"Could not save: {e}")

# ---------------- Main: chat + memory panel ----------------
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader(f"Site coordinator · {site}")
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Describe the situation, e.g. 'Patient 202 missed the Day 14 PK draw by 4 hours...'")
    if question:
        st.session_state.chat.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Recalling protocol and precedents..."):
                try:
                    result = agent.answer(question, site, use_rulings=use_rulings)
                except Exception as e:
                    result = {"answer": f"Memory is unavailable right now: {e}", "memories": [], "chunks": {}}
            label = "" if use_rulings else "\n\n_Memory of past rulings was OFF: protocol only._"
            st.markdown(result["answer"] + label)
        st.session_state.chat.append({"role": "assistant", "content": result["answer"] + label})
        st.session_state.last = result

with right:
    st.subheader("Hindsight memory")
    st.caption("ON: protocol + rulings from all sites" if use_rulings else "OFF: protocol only")
    last = st.session_state.last
    if not last:
        st.info("Ask a question to see what the agent remembers.")
    else:
        records = agent.source_records(last["memories"], last["chunks"])
        rulings = [r for r in records if r.startswith("Medical Monitor ruling")]
        protocol = [r for r in records if not r.startswith("Medical Monitor ruling")]
        st.markdown(f"**{len(rulings)} past rulings · {len(protocol)} protocol sections recalled**")
        for r in rulings:
            head, _, body = r.partition(". Topic:")
            icon = "✅" if "Decision: Accepted" in r else "⛔"
            with st.expander(f"{icon} {head.replace('Medical Monitor ruling ', '')}", expanded=True):
                st.write("Topic:" + body)
        for p in protocol:
            with st.expander(f"📄 {p[:70]}...", expanded=False):
                st.write(p)
        if not records:  # fall back to the extracted facts
            for m in last["memories"]:
                st.write(f"- {m.text}")

    st.divider()
    if st.button("Patterns across sites (reflect)"):
        with st.spinner("Hindsight is reflecting on all rulings..."):
            try:
                st.markdown(memory.reflect(
                    "What patterns do you see across all sites in which deviations the Medical Monitor "
                    "accepted versus rejected? Give 3-5 rules a coordinator could follow, citing case numbers."))
            except Exception as e:
                st.error(f"Reflect failed: {e}")
