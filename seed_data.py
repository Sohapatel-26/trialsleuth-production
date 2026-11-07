"""seed_data.py: load human-body knowledge and past drug outcomes into Hindsight. Run once.

    python seed_data.py

PC-702 (data/demo_new_result.json) is deliberately NOT loaded here: you add it live in
the app with "Teach the agent a new result", so judges watch the next review change.
"""
import json
from pathlib import Path

import memory

DATA = Path(__file__).parent / "data"


def main():
    memory.ensure_bank()
    print(f"Memory bank: {memory.BANK}")
    for k in json.loads((DATA / "human_body.json").read_text(encoding="utf-8")):
        memory.save_body_fact(k)
        print(f"  saved body knowledge: {k['id']} ({k['system']})")
    past = json.loads((DATA / "past_compounds.json").read_text(encoding="utf-8"))
    for p in past:
        memory.save_past_drug(p)
        print(f"  saved past drug: {p['id']} {p['compound']}")
    print(f"Done: body knowledge + {len(past)} past drug outcomes.")


if __name__ == "__main__":
    main()
