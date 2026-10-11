"""The lookup page: pick a Virginia locality, see what its auditors found.

Run:  .venv\\Scripts\\python -m streamlit run app.py
"""
import streamlit as st

import common

# Each visitor's click reruns this file, so remember query results for an hour.
query = st.cache_data(ttl=3600)(common.query)


def opinion(gaap_results):
    """'unmodified_opinion,qualified_opinion' -> 'Unmodified, Qualified'."""
    if not gaap_results:
        return ""
    return ", ".join(part.replace("_opinion", "").replace("_", " ").capitalize() for part in gaap_results.split(","))


st.set_page_config(page_title="Subrecipient Risk Screen", layout="wide")
st.title("Subrecipient Risk Screen")

totals = query("""
    select (select count(*) from audits) as audits,
           (select count(distinct auditee_ein) from audits) as localities,
           (select count(*) from (select distinct report_id, reference_number from findings) f) as findings,
           (select min(audit_year) from audits) as first_year,
           (select max(audit_year) from audits) as last_year,
           (select max(loaded_at)::date from audits) as loaded_on
""")[0]
st.caption(
    f"Single-audit results for Virginia local governments, from the Federal Audit Clearinghouse. "
    f"{totals['audits']:,} audits of {totals['localities']} entities, audit years {totals['first_year']} to "
    f"{totals['last_year']}, {totals['findings']} findings. Data loaded {totals['loaded_on']}."
)

# An entity's name changes spelling from year to year, so we identify it by EIN and show its latest name.
localities = query("""
    select distinct on (auditee_ein) auditee_ein, auditee_name, auditee_city
    from audits
    order by auditee_ein, audit_year desc, fac_accepted_date desc
""")
localities.sort(key=lambda row: row["auditee_name"].lower())
chosen = st.selectbox(
    "Locality",
    localities,
    index=None,
    placeholder="Type a name, for example Fairfax",
    format_func=lambda row: f"{row['auditee_name']} ({(row['auditee_city'] or '').title()})",
)
if not chosen:
    st.stop()

audits = query("""
    select a.*, (select count(distinct reference_number) from findings f where f.report_id = a.report_id) as finding_count
    from audits a
    where a.auditee_ein = %s
    order by a.audit_year desc, a.fac_accepted_date desc
""", (chosen["auditee_ein"],))

# One row per finding. A finding can touch several awards, so a flag is on if it is on for any of them.
findings = query("""
    select f.report_id, f.reference_number,
           count(*) as awards,
           string_agg(distinct f.type_requirement, '') as type_requirement,
           bool_or(f.is_material_weakness) as is_material_weakness,
           bool_or(f.is_significant_deficiency) as is_significant_deficiency,
           bool_or(f.is_modified_opinion) as is_modified_opinion,
           bool_or(f.is_repeat_finding) as is_repeat_finding,
           bool_or(f.is_questioned_costs) as is_questioned_costs,
           max(f.prior_finding_ref_numbers) as prior_finding_ref_numbers,
           t.finding_text
    from findings f
    join audits a using (report_id)
    left join finding_texts t using (report_id, reference_number)
    where a.auditee_ein = %s
    group by f.report_id, f.reference_number, t.finding_text
    order by f.report_id, f.reference_number
""", (chosen["auditee_ein"],))

st.header(chosen["auditee_name"])
latest = audits[0]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Audits on file", len(audits))
col2.metric(f"Federal spending, {latest['audit_year']}", f"${latest['total_amount_expended']:,.0f}")
col3.metric("Findings, all years", len(findings))
col4.metric("Repeat findings", sum(1 for f in findings if f["is_repeat_finding"]))

# The risk sheet is shown only once a person has approved it. Drafts stay out of sight.
st.subheader("Risk sheet")
# Not cached, so an approval shows up straight away.
approved = common.query("""
    select * from risk_sheets
    where auditee_ein = %s and status = 'approved'
    order by reviewed_at desc limit 1
""", (chosen["auditee_ein"],)) if common.query("select to_regclass('risk_sheets') is not null as ready")[0]["ready"] else []
if not approved:
    st.caption("No approved risk sheet yet. The findings below are the source material a reviewer would use.")
else:
    risk_sheet = approved[0]
    sheet = risk_sheet["sheet"]
    rating = risk_sheet["final_rating"]
    colour = {"high": "red", "medium": "orange", "low": "green"}.get(rating, "gray")
    st.markdown(f"### :{colour}[{rating.replace('_', ' ').capitalize()}]")
    st.write(sheet["summary"])
    for reason in sheet["reasons"]:
        st.markdown(f"**{reason['reason']}**")
        st.markdown(f"> {reason['quote']}")
        st.caption(f"Finding {reason['reference_number']}, audit year {reason['audit_year']}")
    if sheet["next_checks"]:
        st.markdown("**Check next**")
        for check in sheet["next_checks"]:
            st.markdown(f"- {check}")
    drafted_by = f"Drafted by AI ({risk_sheet['model']})" if risk_sheet["model"] else "Drafted by rule, with no AI call"
    changed = (f" The reviewer changed the draft rating from {risk_sheet['rating'].replace('_', ' ')}."
               if risk_sheet["rating"] != rating else "")
    st.caption(f"{drafted_by}. Approved by {risk_sheet['reviewer']} on {risk_sheet['reviewed_at']:%Y-%m-%d}.{changed}"
               + (f" Reviewer note: {risk_sheet['reviewer_note']}" if risk_sheet["reviewer_note"] else ""))

st.subheader("Audits")
st.dataframe(
    [
        {
            "Audit year": a["audit_year"],
            "Fiscal year end": a["fy_end_date"],
            "Federal spending": a["total_amount_expended"],
            "Opinion on financial statements": opinion(a["gaap_results"]),
            "Material weakness disclosed": a["is_internal_control_material_weakness_disclosed"],
            "Material noncompliance disclosed": a["is_material_noncompliance_disclosed"],
            "Low-risk auditee": a["is_low_risk_auditee"],
            "Findings": a["finding_count"],
            "Source audit": common.source_url(a["report_id"]),
        }
        for a in audits
    ],
    column_config={
        "Audit year": st.column_config.NumberColumn(format="%d"),
        "Federal spending": st.column_config.NumberColumn(format="dollar"),
        "Source audit": st.column_config.LinkColumn(display_text="Open on fac.gov"),
    },
    hide_index=True,
)

st.subheader("Findings")
shown = False
for audit in audits:
    audit_findings = [f for f in findings if f["report_id"] == audit["report_id"]]
    link = common.source_url(audit["report_id"])

    if not audit_findings:
        # The findings table only lists findings on federal awards. A weakness in the
        # financial statements shows up only as a flag on the audit itself.
        if audit["is_internal_control_material_weakness_disclosed"]:
            shown = True
            st.markdown(f"#### Audit year {audit['audit_year']}")
            st.warning(
                "The auditor disclosed a material weakness in internal control over financial reporting. "
                "It is not tied to a federal award, so the FAC lists no finding details for it. "
                f"[Read the audit report]({link})."
            )
        continue

    shown = True
    st.markdown(f"#### Audit year {audit['audit_year']}")
    st.markdown(f"[Source audit on fac.gov]({link})")
    for f in audit_findings:
        with st.container(border=True):
            badges = [
                ":red-badge[Material weakness]" if f["is_material_weakness"] else "",
                ":red-badge[Modified opinion]" if f["is_modified_opinion"] else "",
                ":orange-badge[Significant deficiency]" if f["is_significant_deficiency"] else "",
                ":violet-badge[Repeat finding]" if f["is_repeat_finding"] else "",
                ":blue-badge[Questioned costs]" if f["is_questioned_costs"] else "",
            ]
            st.markdown(f"**Finding {f['reference_number']}** " + " ".join(b for b in badges if b))
            requirements = common.requirement_names(f["type_requirement"])
            details = [f"Federal awards affected: {f['awards']}"]
            if requirements:
                details.append("Requirement: " + "; ".join(requirements))
            if f["prior_finding_ref_numbers"]:
                details.append(f"Prior-year finding: {f['prior_finding_ref_numbers']}")
            st.caption(" | ".join(details))
            if f["finding_text"]:
                st.text(f["finding_text"])
            else:
                st.info("The FAC holds no finding text for this audit. Read the audit report at the link above.")

if not shown:
    st.success("No findings on file for this entity in any year loaded.")
