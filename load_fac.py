"""Load Virginia local-government audits, programs and findings from the FAC into Postgres.

Run:  .venv/Scripts/python load_fac.py

Every run rebuilds the six data tables from scratch, so it is safe to run again.
"""
import os
import sys
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv

from common import agency_of

API = "https://api.fac.gov"
PAGE = 5000  # rows per request
PLACEHOLDER = "GSA_MIGRATION"  # what the FAC puts in fields the old Census system never collected

load_dotenv()
KEY = os.getenv("FAC_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
if not KEY or not DATABASE_URL:
    sys.exit("FAC_API_KEY and DATABASE_URL must both be set in .env")


# ---------- 1. Extract: ask the FAC API for rows ----------

def get_all(table, **filters):
    """Fetch every matching row from one FAC table, a page at a time."""
    rows, offset = [], 0
    while True:
        response = requests.get(f"{API}/{table}", headers={"X-Api-Key": KEY},
                                params=dict(filters, limit=PAGE, offset=offset), timeout=120)
        response.raise_for_status()
        page = response.json()
        rows += page
        if len(page) < PAGE:
            return rows
        offset += PAGE


def get_for_audits(table, report_ids, order):
    """Fetch rows from a table that has no state column, 100 audits at a time."""
    rows = []
    for start in range(0, len(report_ids), 100):
        chunk = ",".join(report_ids[start:start + 100])
        rows += get_all(table, report_id=f"in.({chunk})", order=order)
    return rows


# ---------- 2. Transform: turn the API's text into clean values ----------

def yes_no(value):
    """'Yes'/'Y' -> True, 'No'/'N' -> False, anything else -> empty."""
    return {"Yes": True, "Y": True, "No": False, "N": False}.get(value)


def clean(value):
    """Blank strings and the migration placeholder become empty."""
    return None if value in ("", PLACEHOLDER, "N/A") else value


def unique(rows):
    """Drop rows that are exact copies of another row."""
    return list({tuple(row.items()): row for row in rows}.values())


def audit_row(r):
    return {
        "report_id": r["report_id"],
        "auditee_ein": r["auditee_ein"],
        "auditee_uei": clean(r["auditee_uei"]),
        "auditee_name": r["auditee_name"].strip(),
        "auditee_city": clean(r["auditee_city"]),
        "audit_year": int(r["audit_year"]),
        "fy_end_date": clean(r["fy_end_date"]),
        "fac_accepted_date": clean(r["fac_accepted_date"]),
        "audit_type": clean(r["audit_type"]),
        "total_amount_expended": r["total_amount_expended"],
        "gaap_results": clean(r["gaap_results"]),
        "is_going_concern_included": yes_no(r["is_going_concern_included"]),
        "is_internal_control_deficiency_disclosed": yes_no(r["is_internal_control_deficiency_disclosed"]),
        "is_internal_control_material_weakness_disclosed": yes_no(r["is_internal_control_material_weakness_disclosed"]),
        "is_material_noncompliance_disclosed": yes_no(r["is_material_noncompliance_disclosed"]),
        "is_low_risk_auditee": yes_no(r["is_low_risk_auditee"]),
        "auditor_firm_name": clean(r["auditor_firm_name"]),
        "data_source": r["data_source"],
    }


def finding_row(r):
    return {
        "report_id": r["report_id"],
        "award_reference": r["award_reference"],
        "reference_number": r["reference_number"],
        "type_requirement": clean(r["type_requirement"]),
        "is_modified_opinion": yes_no(r["is_modified_opinion"]),
        "is_other_matters": yes_no(r["is_other_matters"]),
        "is_material_weakness": yes_no(r["is_material_weakness"]),
        "is_significant_deficiency": yes_no(r["is_significant_deficiency"]),
        "is_other_findings": yes_no(r["is_other_findings"]),
        "is_questioned_costs": yes_no(r["is_questioned_costs"]),
        "is_repeat_finding": yes_no(r["is_repeat_finding"]),
        "prior_finding_ref_numbers": clean(r["prior_finding_ref_numbers"]),
    }


def finding_text_row(r):
    return {
        "report_id": r["report_id"],
        "reference_number": r["finding_ref_number"],  # renamed to match the findings table
        "finding_text": clean(r["finding_text"].strip()),
        "contains_chart_or_table": yes_no(r["contains_chart_or_table"]),
    }


def award_row(r):
    return {
        "report_id": r["report_id"],
        "award_reference": r["award_reference"],
        "aln": f"{r['federal_agency_prefix']}.{r['federal_award_extension']}",
        "federal_program_name": clean(" ".join(r["federal_program_name"].split())),
        "amount_expended": r["amount_expended"],
        "is_major": yes_no(r["is_major"]),
        "is_direct": yes_no(r["is_direct"]),
        "audit_report_type": clean(r["audit_report_type"]),
        "findings_count": r["findings_count"],
    }


def passthrough_row(r):
    name = " ".join(r["passthrough_name"].split())
    return {
        "report_id": r["report_id"],
        "award_reference": r["award_reference"],
        "passthrough_name": name,
        "agency": agency_of(name),  # which Virginia state agency this is, if we can tell
    }


def corrective_action_row(r):
    return {
        "report_id": r["report_id"],
        "reference_number": r["finding_ref_number"],  # renamed to match the findings table
        "planned_action": clean(r["planned_action"].strip()),
    }


# ---------- 3. Load: write the rows into Postgres ----------

def insert(cursor, table, rows):
    """Write rows with COPY, Postgres's bulk loader. It is far faster than one insert per row."""
    columns = list(rows[0])
    with cursor.copy(f"copy {table} ({', '.join(columns)}) from stdin") as copy:
        for row in rows:
            copy.write_row([row[c] for c in columns])


print("Fetching Virginia local audits from the FAC ...")
raw_audits = get_all("general", auditee_state="eq.VA", entity_type="eq.local", order="report_id")
report_ids = [r["report_id"] for r in raw_audits]
print(f"  {len(raw_audits)} audits. Fetching their programs, findings and corrective actions ...")
raw_awards = get_for_audits("federal_awards", report_ids, order="report_id,award_reference")
raw_passthroughs = get_for_audits("passthrough", report_ids, order="report_id,award_reference,passthrough_name")
raw_findings = get_for_audits("findings", report_ids, order="report_id,award_reference,reference_number")
raw_texts = get_for_audits("findings_text", report_ids, order="report_id,finding_ref_number")
raw_actions = get_for_audits("corrective_action_plans", report_ids, order="report_id,finding_ref_number")

tables = [  # (table, rows as fetched, rows cleaned), in the order they must be loaded
    ("audits", raw_audits, unique([audit_row(r) for r in raw_audits])),
    ("awards", raw_awards, unique([award_row(r) for r in raw_awards])),
    ("passthroughs", raw_passthroughs, unique([passthrough_row(r) for r in raw_passthroughs if r["passthrough_name"].strip()])),
    ("findings", raw_findings, unique([finding_row(r) for r in raw_findings])),
    ("finding_texts", raw_texts, unique([finding_text_row(r) for r in raw_texts])),
    ("corrective_actions", raw_actions, unique([corrective_action_row(r) for r in raw_actions])),
]

# One transaction: the tables are replaced all at once or not at all.
with psycopg.connect(DATABASE_URL, prepare_threshold=None) as conn, conn.cursor() as cur:
    cur.execute(Path(__file__).with_name("schema.sql").read_text())
    for table, raw, rows in tables:
        insert(cur, table, rows)

    print("\nLoaded into Postgres:")
    for table, raw, rows in tables:
        in_db = cur.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"  {table:<19} {in_db:>6} rows   ({len(raw)} fetched, {len(raw) - len(rows)} blank or duplicate rows dropped)")
    recognised = cur.execute("select count(agency), count(*) from passthroughs").fetchone()
    print(f"  pass-through names matched to a Virginia state agency: {recognised[0]} of {recognised[1]}")
    years = cur.execute("select min(audit_year), max(audit_year), max(fac_accepted_date) from audits").fetchone()
    print(f"  audit years {years[0]} to {years[1]}; most recent audit accepted by the FAC on {years[2]}")
