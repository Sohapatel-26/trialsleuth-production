"""agent.py: reviews a drug candidate before any human is dosed.

Hindsight recalls the relevant human-body knowledge, past drug outcomes and earlier
reviews. The language model (Groq) writes a risk report that cites them by ID and
suggests changes to the drug or the trial plan. It never declares a drug safe:
it narrows the risks before people are exposed, and experts make the final call.
"""
import os
import re
import time

from dotenv import load_dotenv
from groq import Groq

import memory

load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# Used if the main model refuses the request (too large or rate limited on the free tier).
FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile")
MAX_RECORDS = 12        # source records sent to the model
MAX_RECORD_CHARS = 700  # each record is cut to this length

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
    """Send each stored record once (not facts + records), capped so the prompt stays small."""
    records = source_records(results, chunks) or [m.text for m in results]
    if not records:
        return "(no memories found)"
    records = records[:MAX_RECORDS]
    return "\n".join(f"- {t[:MAX_RECORD_CHARS]}" for t in records)


def candidate_query(c: dict) -> str:
    return (f"Safety risks for {c['name']}, a {c['drug_class']}. Composition: {c['composition']}. "
            f"Dose: {c['dose']}. Patients: {c['patients']}. Design: {c['trial_design']}. "
            f"Other medicines: {c['other_medicines']}. Lab data: {c['known_lab_data']}.")


def _summary(report: str) -> str:
    """Short version of a report, kept in memory so later reviews can refer back to it."""
    lines = [l for l in report.splitlines() if l.strip()]
    return " ".join(lines[:6])[:800]


def _describe(e: Exception) -> str:
    code = getattr(e, "status_code", None)
    msg = str(getattr(e, "message", "") or e)[:200]
    return f"{type(e).__name__} {code}: {msg}" if code else f"{type(e).__name__}: {msg}"


def _call(groq, model, messages) -> str:
    extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}
    reply = groq.chat.completions.create(
        model=model, temperature=0.2, max_tokens=2500, messages=messages, **extra,
    )
    text = reply.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()  # qwen models think out loud


def _ask(messages) -> str:
    """Main model; on a rate limit wait and retry once; then try the fallback model."""
    groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
    try:
        return _call(groq, MODEL, messages)
    except Exception as e:
        code = getattr(e, "status_code", None)
        if code not in (413, 429, 500, 502, 503) or not FALLBACK_MODEL:
            raise
        print(f"[TrialSleuth] {MODEL} failed ({_describe(e)}), retrying")
        if code == 429:
            time.sleep(8)
            try:
                return _call(groq, MODEL, messages)
            except Exception as e2:
                print(f"[TrialSleuth] retry failed ({_describe(e2)}), using {FALLBACK_MODEL}")
        return _call(groq, FALLBACK_MODEL, messages)


def review(candidate: dict, use_memory: bool = True, remember: bool = True) -> dict:
    """use_memory=False is the "no memory" baseline for the demo: a plain chatbot with no history."""
    if use_memory:
        results, chunks = memory.recall(candidate_query(candidate))
    else:
        results, chunks = [], {}
    submission = "\n".join(f"- {k}: {v}" for k, v in candidate.items())
    prompt = f"DRUG CANDIDATE:\n{submission}\n\nMEMORIES:\n{_format_memories(results, chunks)}"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    try:
        text = _ask(messages)
    except Exception as e:  # network, rate limit, bad key...
        return {"answer": f"Sorry, the language model is unavailable right now ({_describe(e)}). "
                          "Wait a minute and try again.",
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
