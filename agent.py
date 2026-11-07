"""agent.py: reviews a drug candidate before any human is dosed.

Hindsight recalls the relevant human-body knowledge, past drug outcomes and earlier
reviews. The language model (Groq) writes a risk report that cites them by ID and
suggests changes to the drug or the trial plan. It never declares a drug safe:
it narrows the risks before people are exposed, and experts make the final call.
"""
import os
import re

from dotenv import load_dotenv
from groq import Groq

import memory

load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are TrialSleuth, a pre-trial drug safety reviewer.
A pharmaceutical company submits a drug candidate BEFORE its human trial: composition, dose,
patients, trial design, other medicines and known lab data.
You get MEMORIES: human-body knowledge (IDs HB-..), outcomes of past drugs (IDs PC-..), and
earlier reviews you wrote.

Rules:
- Use ONLY the memories given, and cite the ID of every memory you rely on.
- A past drug outcome applies only if it shares the drug class or a named feature
  (for example aniline group, basic amine, CYP3A4 cleared, polysorbate 80).
- Never say the drug is safe or will work. You flag known risks so they can be fixed before anyone is dosed.
- Be concrete: name the part of the submission and the exact change (dose, excluded patients,
  banned medicines, a test to run, a formulation change).

Answer in this exact format (Markdown):
**Risk level:** one of "High - changes needed before human dosing", "Medium - changes recommended", "Low - no known risks found in memory"
**Risks by body system:** a short table with columns System | Risk | Why (IDs).
**Suggested changes to make the drug and trial safer:** a numbered list, each with the supporting ID(s).
**Tests to run before dosing:** a short list.
**Limits of this review:** 1-2 sentences on what memory cannot tell us.
"""


def source_records(results, chunks) -> list:
    """The original stored records behind the recalled facts (one per stored memory)."""
    seen, records = set(), []
    for m in results:
        if m.chunk_id and m.chunk_id in chunks and m.chunk_id not in seen:
            seen.add(m.chunk_id)
            records.append(chunks[m.chunk_id].text)
    return records


def _format_memories(results, chunks) -> str:
    facts = [f"- {m.text}" for m in results]
    records = [f"- {t}" for t in source_records(results, chunks)]
    if not facts:
        return "(no memories found)"
    out = "Recalled facts:\n" + "\n".join(facts)
    if records:
        out += "\n\nFull source records:\n" + "\n".join(records)
    return out


def candidate_query(c: dict) -> str:
    return (f"Safety risks for {c['name']}, a {c['drug_class']}. Composition: {c['composition']}. "
            f"Dose: {c['dose']}. Patients: {c['patients']}. Design: {c['trial_design']}. "
            f"Other medicines: {c['other_medicines']}. Lab data: {c['known_lab_data']}.")


def _summary(report: str) -> str:
    """Short version of a report, kept in memory so later reviews can refer back to it."""
    lines = [l for l in report.splitlines() if l.strip()]
    return " ".join(lines[:6])[:800]


def review(candidate: dict, use_memory: bool = True, remember: bool = True) -> dict:
    """use_memory=False is the "no memory" baseline for the demo: a plain chatbot with no history."""
    if use_memory:
        results, chunks = memory.recall(candidate_query(candidate))
    else:
        results, chunks = [], {}
    submission = "\n".join(f"- {k}: {v}" for k, v in candidate.items())
    prompt = f"DRUG CANDIDATE:\n{submission}\n\nMEMORIES:\n{_format_memories(results, chunks)}"
    groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
    try:
        reply = groq.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        )
        text = reply.choices[0].message.content or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()  # qwen models think out loud
    except Exception as e:  # network, rate limit, bad key...
        return {"answer": f"Sorry, the language model is unavailable right now ({type(e).__name__}). Try again in a moment.",
                "memories": results, "chunks": chunks}
    if remember and use_memory:
        try:
            memory.save_review(candidate["name"], _summary(text))
        except Exception:
            pass  # the report is still shown even if saving the summary fails
    return {"answer": text, "memories": results, "chunks": chunks}


if __name__ == "__main__":
    # Quick terminal test: python agent.py
    import json
    from pathlib import Path
    demo = json.loads((Path(__file__).parent / "data" / "demo_candidate.json").read_text(encoding="utf-8"))
    print(review(demo, remember=False)["answer"])
