"""MCP server: lets an AI agent look up Virginia audit findings through two tools.

Run:  .venv\\Scripts\\python mcp_server.py

It talks over stdin/stdout, so it is normally started by an MCP client (Claude Desktop,
Claude Code, a LangGraph agent), not by hand. Both tools only read from the database.
"""
from mcp.server.mcpserver import MCPServer

from common import find_localities, query, requirement_names, source_url

server = MCPServer(
    "subrecipient-risk-screen",
    instructions="Single-audit findings for Virginia local governments, from the Federal Audit Clearinghouse. "
                 "Findings are what auditors reported; they are evidence for a risk assessment, not a rating.",
)


def _finding(row):
    """Shape one database row the same way for both tools."""
    return {
        "locality": row["auditee_name"],
        "audit_year": row["audit_year"],
        "reference_number": row["reference_number"],
        "material_weakness": row["is_material_weakness"],
        "significant_deficiency": row["is_significant_deficiency"],
        "repeat_finding": row["is_repeat_finding"],
        "questioned_costs": row["is_questioned_costs"],
        "requirements": requirement_names(row["type_requirement"]),
        "source_audit": source_url(row["report_id"]),
    }


# One row per finding, with flags combined across the awards it touches.
FINDINGS = """
    select a.auditee_name, a.audit_year, f.report_id, f.reference_number,
           string_agg(distinct f.type_requirement, '') as type_requirement,
           bool_or(f.is_material_weakness) as is_material_weakness,
           bool_or(f.is_significant_deficiency) as is_significant_deficiency,
           bool_or(f.is_repeat_finding) as is_repeat_finding,
           bool_or(f.is_questioned_costs) as is_questioned_costs,
           t.finding_text
    from findings f
    join audits a using (report_id)
    left join finding_texts t using (report_id, reference_number)
"""


@server.tool()
def get_locality_findings(locality: str) -> dict:
    """Get every audit finding on file for one Virginia locality, newest first.

    Args:
        locality: The locality's name or part of it, for example "Fairfax County" or "Roanoke".
    """
    matches = find_localities(locality)
    if not matches:
        return {"error": f"No Virginia locality matches '{locality}'."}
    if len(matches) > 1:
        return {"error": "More than one locality matches. Ask again with one of these names.",
                "matches": [m["auditee_name"] for m in matches[:25]]}

    rows = query(FINDINGS + """
        where a.auditee_ein = %s
        group by a.auditee_name, a.audit_year, f.report_id, f.reference_number, t.finding_text
        order by a.audit_year desc, f.reference_number
    """, (matches[0]["auditee_ein"],))
    years = query("select min(audit_year) as first, max(audit_year) as last, count(*) as audits "
                  "from audits where auditee_ein = %s", (matches[0]["auditee_ein"],))[0]
    return {
        "locality": matches[0]["auditee_name"],
        "audits_on_file": years["audits"],
        "audit_years": f"{years['first']} to {years['last']}",
        "findings": [dict(_finding(row), finding_text=row["finding_text"] or "(no text on file)") for row in rows],
        "note": "Only findings on federal awards are listed. An audit can disclose a financial-statement "
                "weakness that does not appear here.",
    }


@server.tool()
def search_findings(topic: str, limit: int = 10) -> list[dict]:
    """Search the text of all findings by topic and return the best matches with a short excerpt.

    Args:
        topic: Words to look for, for example "procurement", "subrecipient monitoring" or "bank reconciliation".
        limit: How many findings to return, 25 at most.
    """
    # Postgres full-text search: match on word stems, rank by relevance, cut an excerpt around the match.
    rows = query("""
        select matched.*,
               ts_headline('english', matched.finding_text, websearch_to_tsquery('english', %(topic)s),
                           'MaxWords=45, MinWords=20, StartSel="", StopSel=""') as excerpt
        from (""" + FINDINGS + """
            where to_tsvector('english', t.finding_text) @@ websearch_to_tsquery('english', %(topic)s)
            group by a.auditee_name, a.audit_year, f.report_id, f.reference_number, t.finding_text
        ) matched
        order by ts_rank(to_tsvector('english', matched.finding_text), websearch_to_tsquery('english', %(topic)s)) desc,
                 matched.audit_year desc
        limit %(limit)s
    """, {"topic": topic, "limit": max(1, min(limit, 25))})
    return [dict(_finding(row), excerpt=" ".join(row["excerpt"].split())) for row in rows]


if __name__ == "__main__":
    server.run()
