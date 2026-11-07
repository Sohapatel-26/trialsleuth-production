"""seed_data.py: load the protocol and past rulings into Hindsight. Run once.

    python seed_data.py

Case #412 (data/demo_ruling.json) is deliberately NOT loaded here: you add it live
during the demo with the "Add Medical Monitor ruling" form, so judges watch the agent learn.
"""
import json
import re
from pathlib import Path

import memory

DATA = Path(__file__).parent / "data"


def protocol_sections():
    text = (DATA / "protocol.md").read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    intro = parts[0].replace("# ", "").strip()
    yield "Overview", intro
    for part in parts[1:]:
        title, _, body = part.partition("\n")
        yield title.strip(), body.strip()


def main():
    memory.ensure_bank()
    print(f"Memory bank: {memory.BANK}")
    for title, body in protocol_sections():
        memory.save_protocol_section(title, body)
        print(f"  saved protocol: {title}")
    rulings = json.loads((DATA / "rulings.json").read_text(encoding="utf-8"))
    for r in rulings:
        memory.save_ruling(r)
        print(f"  saved ruling: Case #{r['case_id']} ({r['site']}, {r['decision']})")
    print(f"Done: protocol + {len(rulings)} rulings.")


if __name__ == "__main__":
    main()
