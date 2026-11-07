"""memory.py: everything that talks to Hindsight.

TrialSleuth keeps ONE memory bank per clinical trial. Two kinds of memories go in it:
  - protocol sections (the trial's fixed rules), tagged "protocol"
  - Medical Monitor rulings from every hospital site, tagged "ruling", "site:<name>", "topic:<topic>"

Because rulings from all sites live in the same bank, a question asked at one site
can recall a precedent that was set at another site. That is the whole idea.
"""
import os

from dotenv import load_dotenv
from hindsight_client import Hindsight

load_dotenv()

BANK = os.getenv("HINDSIGHT_BANK", "trial-onc-301")

_client = None


def client() -> Hindsight:
    """Create the Hindsight client once and reuse it."""
    global _client
    if _client is None:
        url = os.getenv("HINDSIGHT_URL")
        key = os.getenv("HINDSIGHT_API_KEY")
        if not url or not key:
            raise RuntimeError("Set HINDSIGHT_URL and HINDSIGHT_API_KEY in your .env file.")
        _client = Hindsight(base_url=url, api_key=key)
    return _client


def ensure_bank() -> None:
    """Create the trial's memory bank (safe to call more than once)."""
    client().create_bank(
        bank_id=BANK,
        retain_mission=(
            "This bank holds a clinical trial protocol and Central Medical Monitor rulings. "
            "Always keep case numbers, site names, time limits, temperatures and the decision "
            "(accepted or rejected) exactly as written."
        ),
    )


def ruling_text(r: dict) -> str:
    """Turn one ruling into a single readable memory."""
    return (
        f"Medical Monitor ruling Case #{r['case_id']} ({r['site']} site, {r['date']}). "
        f"Topic: {r['topic']}. Decision: {r['decision']}. "
        f"Situation: {r['situation']} Ruling: {r['ruling']} Reason: {r['reason']}"
    )


def save_protocol_section(title: str, text: str) -> None:
    client().retain(
        bank_id=BANK,
        content=f"Protocol ONC-301, {title}: {text}",
        context="clinical trial protocol section",
        document_id=f"protocol-{title.split('.')[0].strip().lower().replace(' ', '-')}",
        tags=["protocol"],
        timestamp="unset",  # the protocol is a standing rule, not an event
    )


def save_ruling(r: dict) -> None:
    """RETAIN: store a Medical Monitor ruling so every site can learn from it."""
    client().retain(
        bank_id=BANK,
        content=ruling_text(r),
        context=f"Central Medical Monitor ruling for the {r['site']} site",
        document_id=f"ruling-{r['case_id']}",
        metadata={"case_id": str(r["case_id"]), "site": r["site"], "decision": r["decision"]},
        tags=["ruling", f"site:{r['site'].lower()}", f"topic:{r['topic']}"],
        timestamp=r["date"],
    )


def recall(question: str, use_rulings: bool = True) -> list:
    """RECALL: find the protocol rules (and, if allowed, past rulings) relevant to a question.

    use_rulings=False is the "no memory" mode for the demo: the agent only sees the
    protocol, like a normal document chatbot.
    """
    kwargs = {"bank_id": BANK, "query": question, "max_tokens": 3000, "include_chunks": True}
    if not use_rulings:
        kwargs.update(tags=["protocol"], tags_match="any_strict")
    response = client().recall(**kwargs)
    return list(response.results or []), (response.chunks or {})


def reflect(question: str) -> str:
    """REFLECT: ask Hindsight to reason across all stored rulings (for patterns across sites)."""
    response = client().reflect(bank_id=BANK, query=question, tags=["ruling"], tags_match="any_strict")
    return response.text
