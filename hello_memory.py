"""hello_memory.py: save a few facts to Hindsight, then ask for them back.

Run it twice. The second run shows the memory survived, because it lives
in Hindsight Cloud and not in this script.
"""
import os
import sys

from dotenv import load_dotenv
from hindsight_client import Hindsight

load_dotenv()  # reads the keys from the .env file next to this script

url = os.getenv("HINDSIGHT_URL")
key = os.getenv("HINDSIGHT_API_KEY")
if not url or not key:
    sys.exit("Missing HINDSIGHT_URL or HINDSIGHT_API_KEY in your .env file.")

BANK = "hello-memory"  # a "bank" is one agent's memory, like a notebook

client = Hindsight(base_url=url, api_key=key)

# 1. Make sure the bank exists (safe to run again, it just updates it).
client.create_bank(bank_id=BANK)
print(f"Using memory bank: {BANK}\n")

# 2. RETAIN: save some facts. Hindsight reads the text and pulls out facts.
if "--skip-save" not in sys.argv:
    facts = [
        "Priya is a customer at Acme Corp. She uses the Pro plan.",
        "Priya reported that CSV export fails on files over 10 MB.",
        "Priya prefers short answers and gets annoyed by long emails.",
    ]
    for fact in facts:
        client.retain(bank_id=BANK, content=fact)
        print(f"Saved: {fact}")
    print()

# 3. RECALL: ask a question and get back the memories that match.
question = "What problem did Priya have, and how should I reply to her?"
print(f"Question: {question}")
response = client.recall(bank_id=BANK, query=question)

if not response.results:
    print("No memories found yet. Wait a few seconds and run again.")
for i, memory in enumerate(response.results, start=1):
    print(f"  {i}. {memory.text}")

client.close()
