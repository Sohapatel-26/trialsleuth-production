"""app.py: the TrialSleuth screen.  Run with:  streamlit run app.py

Left:   the drug candidate a company submits before its human trial, and the agent's risk report.
Right:  what Hindsight recalled (past drug outcomes, body knowledge, earlier reviews).
Sidebar: memory on/off for the before/after demo, and "Teach the agent a new result".
"""
import html
import json
import re
from pathlib import Path

import streamlit as st

import agent
import memory

st.set_page_config(page_title="TrialSleuth AI", page_icon="🧬", layout="wide")

DATA = Path(__file__).parent / "data"
DEMO = json.loads((DATA / "demo_candidate.json").read_text(encoding="utf-8"))
NEW_RESULT = json.loads((DATA / "demo_new_result.json").read_text(encoding="utf-8"))

if "result" not in st.session_state:
    st.session_state.result = None
    st.session_state.history = []   # dicts: name, memory_on, level
    st.session_state.learned = []   # IDs taught this session

# ---------------- Styles ----------------
st.markdown("""
<style>
.block-container {padding-top: 3.2rem; max-width: 1280px;}
.hero {background: linear-gradient(120deg, #E9DFFF 0%, #FFDDE8 50%, #D7F5EA 100%);
       color: #2E2A3D; border: 1px solid #E7DDF7; border-radius: 18px; padding: 26px 30px; margin-bottom: 18px;}
.hero h1 {color: #3B2F63; font-size: 2.0rem; margin: 0 0 6px 0; padding: 0;}
.hero p {color: #4B4466; margin: 0; font-size: 1.0rem; max-width: 820px;}
.hero .flow {margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap;}
.hero .flow span {background: rgba(255,255,255,0.65); border: 1px solid rgba(142,124,195,0.35);
       border-radius: 999px; padding: 4px 12px; font-size: 0.82rem; color: #4B3F7A;}
.stat {background: #fff; border: 1px solid #EDE6F7; box-shadow: 0 2px 10px rgba(142,124,195,0.08); border-radius: 14px; padding: 14px 16px;}
.stat .n {font-size: 1.6rem; font-weight: 700; color: #6B5BA8; line-height: 1.1;}
.stat .l {font-size: 0.8rem; color: #7A7391; margin-top: 2px;}
.badge {border-radius: 14px; padding: 16px 20px; margin: 6px 0 14px 0; font-weight: 600; font-size: 1.05rem;}
.badge small {display: block; font-weight: 400; font-size: 0.85rem; margin-top: 4px; opacity: 0.85;}
.badge.high {background: #FFE4E8; color: #A3324A; border: 1px solid #FFC9D3;}
.badge.medium {background: #FFF1DC; color: #9A5B13; border: 1px solid #FFDDB0;}
.badge.low {background: #DDF6EC; color: #1F6B52; border: 1px solid #B8EBD6;}
.badge.none {background: #F1EEF8; color: #4B4466; border: 1px solid #DED6EF;}
.mem {background: #fff; border: 1px solid #EDE6F7; border-left: 5px solid #CFC6E6;
      border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; font-size: 0.88rem; color: #4B4466; box-shadow: 0 2px 8px rgba(142,124,195,0.06);}
.mem.past {border-left-color: #F7A8B8;} .mem.body {border-left-color: #9ED8F0;} .mem.review {border-left-color: #C9B6F2;}
.mem .top {display: flex; gap: 6px; align-items: center; margin-bottom: 6px; flex-wrap: wrap;}
.chip {font-size: 0.72rem; font-weight: 600; border-radius: 999px; padding: 2px 9px; background: #F3EEFB; color: #4B4466;}
.chip.cited {background: #CDEFE0; color: #1F6B52;}
.chip.new {background: #E3D8FB; color: #5B3FA8;}
.section {font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em; color: #8E7CC3;
          text-transform: uppercase; margin: 6px 0 8px 0;}
.empty {background: #fff; border: 1px dashed #D9CEF0; border-radius: 14px; padding: 22px; color: #7A7391; text-align: center;}
[data-testid="stForm"] {background: #fff; border-radius: 16px; border: 1px solid #EDE6F7; box-shadow: 0 2px 12px rgba(142,124,195,0.07);}
[data-testid="stSidebar"] {background: #F6F1FD;}
.stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {background: linear-gradient(90deg, #B9A7EC, #F4A9C0); color: #2E2A3D; border: none; font-weight: 600;}
[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] p {color: #2E2A3D; font-weight: 600;}
</style>
""", unsafe_allow_html=True)


def stat(col, number, label):
    col.markdown(f'<div class="stat"><div class="n">{number}</div><div class="l">{label}</div></div>',
                 unsafe_allow_html=True)


def split_risk(report: str):
    """Pull the 'Risk level' line out of the report so it can be shown as a coloured badge."""
    m = re.search(r"\*\*Risk level:\*\*\s*(.+)", report)
    if not m:
        return None, report
    level = m.group(1).strip()
    return level, report.replace(m.group(0), "", 1).strip()


def badge(level, memory_on):
    if level is None:
        st.markdown('<div class="badge none">Review finished</div>', unsafe_allow_html=True)
        return
    kind = "high" if level.lower().startswith("high") else "medium" if level.lower().startswith("medium") else "low"
    icon = {"high": "⛔", "medium": "⚠️", "low": "✅"}[kind]
    note = "Based on Hindsight memory" if memory_on else "Memory OFF: plain AI with no history"
    st.markdown(f'<div class="badge {kind}">{icon} Risk level: {html.escape(level)}<small>{note}</small></div>',
                unsafe_allow_html=True)


def memory_card(text, kind, report):
    ident = re.search(r"\b(PC-\d+|HB-\d+)\b", text)
    ident = ident.group(1) if ident else None
    title = text.split(":")[0]
    chips = []
    if ident and report and ident in report:
        chips.append('<span class="chip cited">Cited in report</span>')
    if ident and ident in st.session_state.learned:
        chips.append('<span class="chip new">Learned this session</span>')
    body = text[len(title) + 1:].strip() if ":" in text else text
    st.markdown(
        f'<div class="mem {kind}"><div class="top"><b>{html.escape(title)}</b>{"".join(chips)}</div>'
        f'{html.escape(body)}</div>', unsafe_allow_html=True)


# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### 🧬 TrialSleuth AI")
    st.caption("Pre-trial drug safety review with memory")
    use_memory = st.toggle("Use Hindsight memory", value=True,
                           help="Off = a plain AI with no memory of body knowledge or past drugs.")
    st.caption("🟢 Memory ON: recalls body knowledge, past drugs and earlier reviews" if use_memory
               else "⚪ Memory OFF: the before-memory baseline")

    st.divider()
    st.markdown("**Teach the agent a new result**")
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
        if st.form_submit_button("Save result to memory", use_container_width=True):
            with st.spinner("Retaining in Hindsight..."):
                try:
                    memory.save_past_drug(dict(id=rid, date=rdate, compound=compound, drug_class=rclass,
                                               features=features, outcome=outcome, change_that_worked=change))
                    st.session_state.learned.append(rid)
                    st.success(f"{rid} saved. Review the drug again to see it used.")
                except Exception as e:
                    st.error(f"Could not save: {e}")

    st.divider()
    st.markdown("**How it works**")
    st.caption("1. A company submits a drug before its human trial.\n\n"
               "2. Hindsight **recalls** body knowledge, similar past drugs and earlier reviews.\n\n"
               "3. The agent writes a risk report citing each memory.\n\n"
               "4. New results are **retained**, so the next review is smarter.")

# ---------------- Header ----------------
st.markdown("""
<div class="hero">
  <h1>Check a drug before any human takes it</h1>
  <p>TrialSleuth reviews a drug candidate against everything it remembers about the human body and past drugs,
  flags risks by body system, and suggests changes before the first person is dosed.
  It never declares a drug safe; experts make the final call.</p>
  <div class="flow"><span>① Submit candidate</span><span>② Recall memory</span>
  <span>③ Risk report</span><span>④ Learn from new results</span></div>
</div>
""", unsafe_allow_html=True)

res = st.session_state.result
records = agent.source_records(res["memories"], res["chunks"]) if res else []
past = [r for r in records if r.startswith("Past drug outcome")]
body = [r for r in records if r.startswith("Human body knowledge")]
reviews = [r for r in records if r.startswith("Earlier TrialSleuth review")]

s1, s2, s3, s4 = st.columns(4)
stat(s1, len(records) if res else "–", "Memories recalled")
stat(s2, len(past) if res else "–", "Similar past drugs")
stat(s3, len(st.session_state.history), "Reviews this session")
stat(s4, len(st.session_state.learned), "Results learned this session")
st.write("")

left, right = st.columns([3, 2], gap="large")

# ---------------- Candidate form + report ----------------
with left:
    st.markdown('<div class="section">Drug candidate</div>', unsafe_allow_html=True)
    with st.form("candidate"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Drug name", DEMO["name"])
        drug_class = c2.text_input("Drug class", DEMO["drug_class"])
        composition = st.text_area("Composition (active ingredient, structure, excipients)", DEMO["composition"])
        c3, c4 = st.columns(2)
        dose = c3.text_input("Dose and route", DEMO["dose"])
        trial_design = c4.text_input("Trial design", DEMO["trial_design"])
        patients = st.text_area("Patients in the trial", DEMO["patients"], height=68)
        c5, c6 = st.columns(2)
        other_medicines = c5.text_input("Other medicines allowed", DEMO["other_medicines"])
        known_lab_data = c6.text_input("Known lab and animal data", DEMO["known_lab_data"])
        submitted = st.form_submit_button("🔬 Review before human trial", type="primary", use_container_width=True)

    if submitted:
        candidate = dict(name=name, drug_class=drug_class, composition=composition, dose=dose, patients=patients,
                         trial_design=trial_design, other_medicines=other_medicines, known_lab_data=known_lab_data)
        with st.spinner("Recalling body knowledge and past drug outcomes..." if use_memory else "Reviewing without memory..."):
            try:
                result = agent.review(candidate, use_memory=use_memory)
            except Exception as e:
                result = {"answer": f"Memory is unavailable right now: {e}", "memories": [], "chunks": {}}
        result["memory_on"] = use_memory
        result["level"], result["body"] = split_risk(result["answer"])
        st.session_state.result = result
        st.session_state.history.append({"name": name, "memory_on": use_memory, "level": result["level"] or "-"})
        st.rerun()  # refresh the stat cards and memory panel

    if res:
        st.markdown('<div class="section">Safety report</div>', unsafe_allow_html=True)
        badge(res.get("level"), res.get("memory_on"))
        with st.container(border=True):
            st.markdown(res.get("body", res["answer"]))

    if st.session_state.history:
        with st.expander(f"Review history ({len(st.session_state.history)})"):
            for i, h in enumerate(st.session_state.history, start=1):
                st.write(f"{i}. **{h['name']}** · memory {'ON' if h['memory_on'] else 'OFF'} · {h['level']}")

# ---------------- Memory panel ----------------
with right:
    st.markdown('<div class="section">Hindsight memory</div>', unsafe_allow_html=True)
    if not res:
        st.markdown('<div class="empty">Review a drug to see exactly what the agent remembered.</div>',
                    unsafe_allow_html=True)
    elif not res.get("memory_on"):
        st.markdown('<div class="empty">Memory was <b>OFF</b> for this review.<br>'
                    'The AI had no body knowledge, no past drugs and no earlier reviews.</div>',
                    unsafe_allow_html=True)
    else:
        report = res["answer"]
        for title, kind, items in (("Past drug outcomes", "past", past),
                                   ("Human body knowledge", "body", body),
                                   ("Earlier reviews", "review", reviews)):
            if items:
                st.markdown(f"**{title}** · {len(items)}")
                for r in items:
                    memory_card(r, kind, report)
        if not records:
            for m in res["memories"]:
                st.write(f"- {m.text}")

    st.write("")
    if st.button("🧠 What has the agent learned?", use_container_width=True):
        with st.spinner("Hindsight is reflecting on everything it remembers (10 to 30 seconds)..."):
            try:
                lessons = memory.reflect(
                    "Across all past drug outcomes and reviews, what are the 3 to 5 most important lessons for "
                    "making a new drug candidate safer before its first human trial? Cite the IDs.")
                with st.container(border=True):
                    st.markdown(lessons)
            except Exception as e:
                st.error(f"Reflect failed: {e}")
