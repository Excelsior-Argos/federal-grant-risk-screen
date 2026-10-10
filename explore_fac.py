"""Print real sample rows from the three FAC tables we plan to load.

Run:  .venv\\Scripts\\python explore_fac.py

Nothing is saved. This is only for looking at the data before designing the schema.
"""
import json
import os
import sys

import requests
from dotenv import load_dotenv

API = "https://api.fac.gov"

sys.stdout.reconfigure(encoding="utf-8")  # auditors use curly quotes; Windows consoles choke on them otherwise
load_dotenv()
KEY = os.getenv("FAC_API_KEY")
if not KEY:
    sys.exit("FAC_API_KEY is not set. Copy .env.example to .env and paste your key in.")


def get(table, **filters):
    """Ask the FAC API for rows from one table.

    Filters use the API's syntax: column="operator.value", e.g. audit_year="eq.2023".
    """
    response = requests.get(f"{API}/{table}", headers={"X-Api-Key": KEY}, params=filters, timeout=60)
    response.raise_for_status()
    return response.json()


def show(title, row):
    print(f"\n===== {title} =====")
    print(json.dumps(row, indent=2, ensure_ascii=False))


# 1. One row per audit. This is the only table we can filter by state.
audits = get("general", auditee_state="eq.VA", entity_type="eq.local", audit_year="eq.2023", limit=100)
show(f"general: 1 of {len(audits)} Virginia local audits fetched", audits[0])

# 2. Findings have no state column, so we ask for them by the audits' report_ids.
report_ids = ",".join(a["report_id"] for a in audits)
findings = get("findings", report_id=f"in.({report_ids})", limit=5)
show("findings: one row per finding per award", findings[0])

# 3. The auditor's written text for that same audit.
texts = get("findings_text", report_id=f"eq.{findings[0]['report_id']}")
sample = dict(texts[0], finding_text=texts[0]["finding_text"][:600] + " ...[cut]")
show(f"findings_text: 1 of {len(texts)} for report {findings[0]['report_id']}", sample)

# What to notice before designing the schema.
print("\n===== Compare the three tables =====")
for name, row in [("general", audits[0]), ("findings", findings[0]), ("findings_text", texts[0])]:
    print(f"{name}: {len(row)} columns")
    print("   columns mentioning 'state':", [c for c in row if "state" in c] or "none")
    print("   columns mentioning 'ref':  ", [c for c in row if "ref" in c] or "none")
