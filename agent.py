"""agent.py: turns a coordinator's question + recalled memories into a recommendation.

The language model (Groq) only sees what Hindsight recalled. It must cite case numbers
and it never approves anything itself: the human Medical Monitor signs off.
"""
import os
import re

from dotenv import load_dotenv
from groq import Groq

import memory

load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are TrialSleuth, an assistant for clinical trial site coordinators on trial ONC-301.
A coordinator describes a protocol gray area. You get MEMORIES recalled from the trial's memory:
protocol rules and, sometimes, past Central Medical Monitor rulings from any hospital site.

Rules:
- Use ONLY the memories given. If they do not cover the case, say so.
- You never approve or reject anything. You RECOMMEND; the Central Medical Monitor decides.
- A past ruling only applies if the CAUSE and the SIZE of the deviation match its conditions
  (for example "equipment failure, up to 6 hours"). If the cause or size differs, say clearly
  that the precedent does not apply and why. Patient-caused or site-staffing delays are not
  the same as equipment failure or severe weather.
- Always name the case numbers (Case #NNN) and sites you relied on.

Answer in this exact format (Markdown):
**Recommendation:** one of "Likely acceptable under precedent", "Protocol deviation - escalate", or "Not enough information"
**Why:** 2-4 short sentences.
**Precedents used:** Case numbers with site, or "None - protocol only".
**Next step:** what the coordinator should log or do, ending with "Send to the Central Medical Monitor for sign-off."
"""


def source_records(results, chunks) -> list:
    """The original stored records (whole rulings / protocol sections) behind the recalled facts."""
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


def answer(question: str, site: str, use_rulings: bool = True) -> dict:
    results, chunks = memory.recall(question, use_rulings=use_rulings)
    prompt = (
        f"Coordinator at the {site} site asks:\n{question}\n\n"
        f"MEMORIES:\n{_format_memories(results, chunks)}"
    )
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
        text = f"Sorry, the language model is unavailable right now ({type(e).__name__}). Try again in a moment."
    return {"answer": text, "memories": results, "chunks": chunks}


if __name__ == "__main__":
    # Quick terminal test: python agent.py
    q = "Patient 202 missed the Day 14 PK blood draw by 4 hours because the lab centrifuge broke. Do we drop the patient?"
    for mode in (False, True):
        print(f"\n=== Memory of past rulings: {'ON' if mode else 'OFF'} ===")
        print(answer(q, "Bangalore", use_rulings=mode)["answer"])
