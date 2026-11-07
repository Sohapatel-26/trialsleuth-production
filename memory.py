"""memory.py: everything that talks to Hindsight.

TrialSleuth keeps ONE memory bank that grows over time. Three kinds of memories go in it:
  - human-body knowledge (how organs handle drugs), tagged "body"
  - outcomes of past drugs: what went wrong and the change that fixed it, tagged "past-drug"
  - every review the agent has written, tagged "review", so it remembers candidates it has seen

Each new lab or trial result is retained straight away, so the next review is
checked against it. That is how the agent gets better with every drug it sees.
"""
import asyncio
import os

from dotenv import load_dotenv
from hindsight_client import Hindsight

load_dotenv()

BANK = os.getenv("HINDSIGHT_BANK", "drug-safety-memory")


def _run(work):
    """Run one Hindsight call with a fresh client and its own event loop.

    Streamlit re-runs the script on different threads, and the Hindsight client's
    network session is tied to the event loop it was created on. Reusing one client
    across reruns fails with "Event loop is closed", so each call gets its own.
    """
    url = os.getenv("HINDSIGHT_URL")
    key = os.getenv("HINDSIGHT_API_KEY")
    if not url or not key:
        raise RuntimeError("Set HINDSIGHT_URL and HINDSIGHT_API_KEY in your .env file.")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = Hindsight(base_url=url, api_key=key)
    try:
        return work(client)
    finally:
        client.close()
        loop.close()
        asyncio.set_event_loop(None)


def ensure_bank() -> None:
    """Create the memory bank (safe to call more than once)."""
    _run(lambda c: c.create_bank(
        bank_id=BANK,
        retain_mission=(
            "This bank holds human-body pharmacology knowledge and outcomes of past drug trials. "
            "Always keep IDs (HB-.., PC-..), compound names, doses, percentages and the change "
            "that worked exactly as written."
        ),
    ))


# ---------- RETAIN ----------

def body_text(k: dict) -> str:
    return f"Human body knowledge {k['id']} ({k['system']}): {k['fact']}"


def past_drug_text(p: dict) -> str:
    return (
        f"Past drug outcome {p['id']}: {p['compound']} ({p['drug_class']}, {p['date']}). "
        f"Features: {p['features']}. What happened: {p['outcome']} "
        f"Change that worked: {p['change_that_worked']}"
    )


def save_body_fact(k: dict) -> None:
    _run(lambda c: c.retain(
        bank_id=BANK, content=body_text(k), context="human body pharmacology knowledge",
        document_id=f"body-{k['id']}", tags=["body", f"system:{k['system'].lower()}"],
        timestamp="unset",  # standing knowledge, not an event
    ))


def save_past_drug(p: dict) -> None:
    """Remember what happened with a drug, and what change fixed it."""
    _run(lambda c: c.retain(
        bank_id=BANK, content=past_drug_text(p), context=f"outcome of drug {p['compound']}",
        document_id=f"past-{p['id']}", metadata={"id": p["id"], "compound": p["compound"]},
        tags=["past-drug", f"class:{p['drug_class'].lower()}"], timestamp=p["date"],
    ))


def save_review(name: str, summary: str) -> None:
    """Remember a review the agent wrote, so later reviews can refer back to it."""
    _run(lambda c: c.retain(
        bank_id=BANK, content=f"Earlier TrialSleuth review of candidate {name}: {summary}",
        context=f"previous safety review of {name}", tags=["review", f"candidate:{name.lower()}"],
    ))


# ---------- RECALL / REFLECT ----------

def recall(query: str) -> tuple:
    """Find the body knowledge, past drug outcomes and earlier reviews relevant to a candidate."""
    response = _run(lambda c: c.recall(
        bank_id=BANK, query=query, max_tokens=5000, include_chunks=True,
    ))
    return list(response.results or []), (response.chunks or {})


def reflect(question: str) -> str:
    """Ask Hindsight to reason across everything it has learned."""
    return _run(lambda c: c.reflect(bank_id=BANK, query=question)).text
