"""Shared by the page, the AI layer and the MCP server: database access and FAC lookups."""
import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()

# Compliance requirement codes from the federal Compliance Supplement (2 CFR 200, Appendix XI).
REQUIREMENTS = {
    "A": "Activities allowed or unallowed",
    "B": "Allowable costs",
    "C": "Cash management",
    "D": "Davis-Bacon Act",
    "E": "Eligibility",
    "F": "Equipment and real property",
    "G": "Matching, level of effort, earmarking",
    "H": "Period of performance",
    "I": "Procurement, suspension and debarment",
    "J": "Program income",
    "K": "Real property acquisition and relocation",
    "L": "Reporting",
    "M": "Subrecipient monitoring",
    "N": "Special tests and provisions",
    "P": "Other",
}


def source_url(report_id):
    """The public FAC page for one audit, where the full report can be downloaded."""
    return f"https://app.fac.gov/dissemination/summary/{report_id}"


def requirement_names(codes):
    """'AB' -> ['Activities allowed or unallowed', 'Allowable costs']."""
    return sorted({REQUIREMENTS.get(code, code) for code in codes or ""})


def query(sql, params=None):
    """Run one SQL statement and return its rows as a list of dictionaries."""
    with psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None, row_factory=dict_row) as conn:
        cursor = conn.execute(sql, params)
        return cursor.fetchall() if cursor.description else []


def find_localities(text):
    """Find localities whose latest name contains every word typed, e.g. 'Fairfax County'.

    Names change spelling between years, so we match on each entity's latest name and
    return its EIN, which is what ties its audits together.
    """
    words = [word for word in text.replace(",", " ").split() if word.lower() not in ("of", "the")]
    return query("""
        select auditee_ein, auditee_name from (
            select distinct on (auditee_ein) auditee_ein, auditee_name
            from audits order by auditee_ein, audit_year desc, fac_accepted_date desc
        ) latest
        where auditee_name ilike all(%s)
        order by auditee_name
    """, ([f"%{word}%" for word in words],))
