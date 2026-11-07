# TrialSleuth AI

**A clinical trial assistant that remembers every Medical Monitor ruling, at every hospital, so the next site gets a consistent, precedent-backed answer.**

In a global clinical trial, 50+ hospitals follow the same protocol, but day-to-day gray areas (a blood draw 4 hours late, a shipment that got warm) are ruled on one case at a time by the Central Medical Monitor. A ruling made for London never reaches Bangalore. Sites drop patients they didn't need to, destroy drug they could have kept, and make inconsistent decisions that auditors flag as protocol drift.

TrialSleuth gives every site a shared memory of those rulings, built on [Hindsight](https://github.com/vectorize-io/hindsight).

## How Hindsight memory is used

| Hindsight call | What TrialSleuth does with it | Where |
| --- | --- | --- |
| `create_bank` | One memory bank per trial (`trial-onc-301`), with a retain mission telling Hindsight to keep case numbers, limits and decisions exact | `memory.ensure_bank` |
| `retain` | Stores each protocol section (tag `protocol`) and every Medical Monitor ruling (tags `ruling`, `site:<name>`, `topic:<topic>`, with the ruling date as its timestamp) | `memory.save_protocol_section`, `memory.save_ruling` |
| `recall` | On every coordinator question, recalls the relevant protocol rules **and rulings from all sites**. With memory switched off it filters to `protocol` only, which is the "normal document chatbot" baseline | `memory.recall` |
| `reflect` | "Patterns across sites" button: Hindsight reasons over all rulings and summarises which kinds of deviation get accepted or rejected | `memory.reflect` |

New rulings added in the app are retained immediately, so the agent's next answer, at any site, already uses them.

**Before vs after memory:**
- *Protocol only:* "Day 14 draw 4 hours late (window is plus or minus 2 hours) = protocol deviation, escalate."
- *With memory:* "Likely acceptable under precedent: Case #412 (London) accepted up to 6 hours for documented equipment failure. Note Case #426 (Singapore) rejected 9 hours. Send to the Central Medical Monitor for sign-off."
- *Look-alike case:* "Patient forgot the appointment" does **not** match #412; the agent cites Case #301 (Madrid, rejected) instead.

TrialSleuth only **recommends**. The human Medical Monitor always makes the decision.

## Architecture

```
Site coordinator (Streamlit chat)
        |
        v
   agent.py  --recall-->  Hindsight Cloud memory bank (protocol + rulings from all sites)
        |                        ^
        v                        | retain (seed_data.py, "Add ruling" form)
   Groq LLM (gpt-oss-120b)       |
        |                  Medical Monitor rulings
        v
 Recommendation + cited case numbers  -->  Medical Monitor sign-off
```

## Project files

| File | Job |
| --- | --- |
| `app.py` | Streamlit screen: chat on the left, recalled memories on the right, "Add ruling" form in the sidebar |
| `agent.py` | Recalls memories, asks Groq for a recommendation that cites case numbers |
| `memory.py` | All Hindsight calls: bank, retain, recall, reflect |
| `seed_data.py` | Loads the protocol and 17 past rulings (run once) |
| `data/protocol.md` | Fictional trial protocol ONC-301 |
| `data/rulings.json` | 17 fictional Medical Monitor rulings across 6 sites |
| `data/demo_ruling.json` | Case #412, added live during the demo |

All trial data is fictional and made up for demonstration.

## Run it

Needs Python 3.10+, a [Hindsight Cloud](https://ui.hindsight.vectorize.io) API key and a [Groq](https://console.groq.com) API key.

```powershell
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy env.example .env          # Mac/Linux: cp env.example .env   then fill in your keys
python seed_data.py            # once: loads protocol + rulings into Hindsight
python agent.py                # optional terminal test: memory OFF vs ON
streamlit run app.py
```

## Demo script

1. Site **Bangalore**, memory toggle **OFF**. Ask: *"Patient 202 missed the Day 14 PK draw by 4 hours because the lab centrifuge broke. Do we drop the patient?"* The agent is strict: protocol deviation.
2. In the sidebar, save the London ruling **Case #412** (pre-filled).
3. Toggle memory **ON** and ask the same question. The agent cites #412, and the right panel shows the London ruling it recalled.
4. Ask: *"Patient 215 missed the Day 14 PK draw by 4 hours because they forgot the appointment."* The agent says #412 does not apply and cites #301.
5. Click **Patterns across sites** to show `reflect`. It takes 10 to 30 seconds because Hindsight reasons over every ruling, so say so while it runs.

Case #412 is intentionally left out of `seed_data.py`, and Case #301 must stay in `rulings.json`: steps 1 to 4 depend on both.

**Rerunning the demo from scratch:** once #412 is saved, it stays in memory. To start fresh, set `HINDSIGHT_BANK` in `.env` to a new name (for example `trial-onc-301-v2`) and run `python seed_data.py` again. Each seed run uses Hindsight credit.

## Limitations

- **Recall can miss or mismatch.** If a question is worded very differently from a ruling, the right precedent may not be recalled, or a near-miss may be. That is why the right panel shows exactly which rulings were used.
- **Conflicting or reversed rulings.** The agent sees rulings with their dates but has no formal way to mark one ruling as replacing another. A real system would need ruling versions.
- **Not a validated system.** A real trial tool would need an audit trail, user sign-in, and GxP validation before use. TrialSleuth only recommends; the Medical Monitor decides.
- **Fictional data.** The protocol and rulings are invented for demonstration.

## Learn more

- [Hindsight on GitHub](https://github.com/vectorize-io/hindsight)
- [Hindsight documentation](https://hindsight.vectorize.io/)
- [What is agent memory?](https://vectorize.io/what-is-agent-memory)
