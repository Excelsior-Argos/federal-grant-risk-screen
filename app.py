"""The lookup page: pick a state agency and a Virginia locality, see what its auditors found.

Run:  .venv/Scripts/python -m streamlit run app.py
"""
from datetime import date

import streamlit as st

import common
import risk

# Each visitor's click reruns this file, so remember results for an hour.
query = st.cache_data(ttl=3600)(common.query)
gather_evidence = st.cache_data(ttl=3600)(risk.gather_evidence)
agency_worklist = st.cache_data(ttl=3600)(risk.agency_worklist)


def opinion(gaap_results):
    """'unmodified_opinion,qualified_opinion' -> 'Unmodified, Qualified'."""
    if not gaap_results:
        return ""
    return ", ".join(part.replace("_opinion", "").replace("_", " ").capitalize() for part in gaap_results.split(","))


def yes_no(value):
    return "Yes" if value else "No"


st.set_page_config(page_title="Federal Grant Risk Screen", layout="wide")
st.title("Federal Grant Risk Screen")

totals = query("""
    select (select count(*) from audits) as audits,
           (select count(distinct auditee_ein) from audits) as localities,
           (select count(*) from (select distinct report_id, reference_number from findings) f) as findings,
           (select min(audit_year) from audits) as first_year,
           (select max(audit_year) from audits) as last_year,
           (select max(loaded_at)::date from audits) as loaded_on
""")[0]
window = f"{totals['last_year'] - risk.WINDOW_YEARS + 1} to {totals['last_year']}"
st.caption(
    f"Single-audit results for Virginia local governments, from the Federal Audit Clearinghouse. "
    f"{totals['audits']:,} audits of {totals['localities']} entities, audit years {totals['first_year']} to "
    f"{totals['last_year']}, {totals['findings']} findings. Data loaded {totals['loaded_on']}."
)

# ---------- Step 1: whose subrecipients? ----------
# A monitor works for one state agency and is answerable for the money that agency passed down.
agencies = [row["agency"] for row in query("""
    select p.agency from passthroughs p join audits a using (report_id)
    where p.agency is not null and a.audit_year >= %s
    group by 1 order by count(distinct a.auditee_ein) desc
""", (totals["last_year"] - risk.WINDOW_YEARS + 1,))]
# Open on DCJS, so a first-time visitor sees a real worklist straight away. "All agencies" shows everyone.
DEFAULT_AGENCY = "Department of Criminal Justice Services"
ALL = "All agencies"
choices = [ALL] + agencies
choice = st.selectbox("View as a state agency", choices,
                      index=choices.index(DEFAULT_AGENCY) if DEFAULT_AGENCY in choices else 0)
agency = None if choice == ALL else choice

# An entity's name changes spelling from year to year, so we identify it by EIN and show its latest name.
localities = query("""
    select distinct on (auditee_ein) auditee_ein, auditee_name, auditee_city
    from audits
    order by auditee_ein, audit_year desc, fac_accepted_date desc
""")

if agency:
    worklist = agency_worklist(agency)
    st.subheader(f"{agency}: subrecipients, audit years {window}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Subrecipients", len(worklist))
    col2.metric("Latest audit filed late", sum(1 for w in worklist if w["late"]))
    col3.metric("Next audit overdue", sum(1 for w in worklist if w["next_audit_overdue"]))
    col4.metric("Findings on this agency's money", sum(1 for w in worklist if w["own_findings"]))

    # The short list a monitor acts on first: who has findings on this agency's money, and what kind.
    flagged = sorted((w for w in worklist if w["own_findings"]), key=lambda w: (-w["vdem_points"], -w["own_findings"]))
    st.markdown(f"**The {len(flagged)} subrecipients with findings on this agency's money in their last two audits.** "
                "Tick a row to open that locality below.")
    picked = st.dataframe(
        [
            {
                "Locality": w["name"],
                "Findings": w["own_findings"],
                "Finding numbers": ", ".join(sorted(f["reference_number"] for f in w["findings"])),
                "Material weakness or modified opinion": sum(1 for f in w["findings"]
                                                             if f["is_material_weakness"] or f["is_modified_opinion"]),
                "Repeat": sum(1 for f in w["findings"] if f["is_repeat_finding"]),
                "Questioned costs": sum(1 for f in w["findings"] if f["is_questioned_costs"]),
                "Programs": "; ".join(sorted({p.title() for f in w["findings"] for p in (f["programs"] or "").split("; ") if p})),
                "Latest audit filed late": w["late"],
                "Management decision due": w["decision_due"],
            }
            for w in flagged
        ],
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"flagged-{agency}",
    )
    picked_ein = flagged[picked.selection.rows[0]]["ein"] if picked.selection.rows else None
    st.caption(
        "A finding is listed here when the auditor attached it to a grant line that names this agency as the "
        "source. A locality can get the same program from more than one source, and the auditor then attaches "
        "the finding to every line of that program. So read each finding to confirm it concerns this agency's part."
    )

    st.markdown(f"**All {len(worklist)} subrecipients**")
    st.dataframe(
        [
            {
                "Locality": w["name"],
                "Latest audit year": w["audit_year"],
                "Months to file": w["months_after_year_end"],
                "Filed late": w["late"],
                "Agency's money in that audit": w["own_spending"],
                "Findings on agency's money, 2 years": w["own_findings"],
                "Management decision due": w["decision_due"],
                "VDEM form: audit points": w["vdem_points"],
                "DCJS form: audit points": w["dcjs_points"],
                "NC matrix: audit row": w["nc_level"],
            }
            for w in sorted(worklist, key=lambda w: (-w["own_findings"], -w["vdem_points"], -w["dcjs_points"],
                                                     -w["months_after_year_end"]))
        ],
        column_config={
            "Latest audit year": st.column_config.NumberColumn(format="%d"),
            "Agency's money in that audit": st.column_config.NumberColumn(format="dollar"),
        },
        hide_index=True,
    )
    st.caption(
        "A subrecipient here is a local entity whose audit lists money passed down by this agency. An audit is due "
        "nine months after the fiscal year ends (2 CFR 200.512). The agency owes a written management decision on "
        "each finding on its own money within six months of the clearinghouse accepting the audit (2 CFR 200.521); "
        "the FAC cannot say whether one was issued. The last three columns apply the audit rows of three "
        "real risk forms: Virginia VDEM's financial risk assessment (which gives 35 points, its high-risk line, "
        "for a finding on the agency's own grant), Virginia DCJS's Grant Monitoring Risk Assessment and North "
        "Carolina DHHS's county subrecipient matrix. They are the audit part only; a full assessment has other rows."
    )
    subrecipients = {w["ein"] for w in worklist}
    localities = [row for row in localities if row["auditee_ein"] in subrecipients]
else:
    picked_ein = None

# ---------- Step 2: one locality ----------
localities.sort(key=lambda row: row["auditee_name"].lower())
# A row ticked in the short list above opens that locality here.
picked_index = next((i for i, row in enumerate(localities) if row["auditee_ein"] == picked_ein), None)
chosen = st.selectbox(
    "Locality",
    localities,
    index=picked_index,
    placeholder="Type a name, for example Fairfax",
    format_func=lambda row: f"{row['auditee_name']} ({(row['auditee_city'] or '').title()})",
    key=f"locality-{agency}-{picked_ein}",
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
           count(distinct f.award_reference) as awards,
           string_agg(distinct f.type_requirement, '') as type_requirement,
           bool_or(f.is_material_weakness) as is_material_weakness,
           bool_or(f.is_significant_deficiency) as is_significant_deficiency,
           bool_or(f.is_modified_opinion) as is_modified_opinion,
           bool_or(f.is_repeat_finding) as is_repeat_finding,
           bool_or(f.is_questioned_costs) as is_questioned_costs,
           max(f.prior_finding_ref_numbers) as prior_finding_ref_numbers,
           string_agg(distinct w.aln || ' ' || w.federal_program_name, '; ') as programs,
           array_remove(array_agg(distinct p.agency), null) as agencies,
           t.finding_text, c.planned_action
    from findings f
    join audits a using (report_id)
    left join awards w using (report_id, award_reference)
    left join passthroughs p using (report_id, award_reference)
    left join finding_texts t using (report_id, reference_number)
    left join corrective_actions c using (report_id, reference_number)
    where a.auditee_ein = %s
    group by f.report_id, f.reference_number, t.finding_text, c.planned_action
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

# ---------- The audit review: what a real agency risk form asks about the audit ----------
st.subheader("Audit review" + (f" for the {agency}" if agency else ""))
review = risk.audit_review(gather_evidence(chosen["auditee_ein"]), agency)
if not review["audit_on_file"]:
    st.error(f"No single audit is on file for audit years {window}. Find out whether one was required.")
else:
    whose = "this agency's" if agency else "any"
    left, right = st.columns(2)
    with left:
        st.markdown("**Is the audit on file and on time?**")
        timing = (f"Fiscal year ended {review['fiscal_year_end']}. Accepted by the clearinghouse on "
                  f"{review['accepted_by_fac']}, {review['months_after_year_end']} months later. ")
        if review["late"]:
            st.warning(timing + "That is late: an audit is due within nine months.")
        else:
            st.success(timing + "That is on time.")
        if review["next_audit_overdue"]:
            st.warning(f"The newest audit on file is for {review['audit_year']}. The audit for the year after it "
                       "is overdue: it was due nine months after that year ended.")
        if agency and review["decision_due"]:
            verb = "was" if review["decision_due"] < date.today() else "is"
            st.info(f"The {review['audit_year']} audit has findings on this agency's money. A written management "
                    f"decision on each {verb} due by {review['decision_due']} (2 CFR 200.521).")
        st.markdown("**What did the auditor conclude?**")
        st.markdown(
            f"- Opinion on the financial statements: {review['opinion_financial_statements'] or 'not recorded'}\n"
            f"- Opinion on major federal programs: {review['opinion_major_programs'] or 'no major program'}\n"
            f"- Low-risk auditee: {yes_no(review['low_risk_auditee'])}\n"
            f"- Material weakness in financial reporting: {yes_no(review['statement_material_weakness'])}\n"
            f"- Going-concern doubt: {yes_no(review['going_concern'])}\n"
            f"- Findings in the last two audit years: {review['findings_two_years']}, of which "
            f"{len(review['own_findings'])} on {whose} money"
        )
    with right:
        st.markdown("**How this fills in three real risk forms**")
        st.dataframe(
            [{"Form": "Virginia VDEM financial risk assessment", "Row": row, "Answer": answer, "Points": points}
             for row, answer, points in risk.vdem_form_rows(review)]
            + [{"Form": "Virginia DCJS risk assessment", "Row": row, "Answer": answer, "Points": points}
               for row, answer, points in risk.dcjs_form_rows(review)]
            + [{"Form": "North Carolina DHHS county matrix", "Row": "Single Audit",
                "Answer": f"{risk.nc_matrix_row(review)[0]} risk: {risk.nc_matrix_row(review)[1]}",
                "Points": risk.nc_matrix_row(review)[2]}],
            hide_index=True,
        )
        st.caption(
            "Worked out by code from the audit data, with no AI. These are the audit rows only. The other rows "
            "of each form, such as late reports, site visits and staff turnover, need the agency's own records. "
            + ("" if agency else "Pick a state agency above to answer for that agency's programs."))
    if agency:
        st.markdown(f"**Programs in the {review['audit_year']} audit funded through this agency**")
        if review["own_programs"]:
            st.dataframe(
                [{"Program number": w["aln"], "Program": w["federal_program_name"], "Spent": w["amount_expended"],
                  "Audited as a major program": w["is_major"],
                  "Opinion": {"U": "Unmodified", "Q": "Qualified", "A": "Adverse", "D": "Disclaimer"}.get(w["audit_report_type"], "")}
                 for w in review["own_programs"]],
                column_config={"Spent": st.column_config.NumberColumn(format="dollar")},
                hide_index=True,
            )
        else:
            st.caption("None. This agency's money appears in an earlier audit in the window, not the latest one.")

st.subheader("Audits")
st.dataframe(
    [
        {
            "Audit year": a["audit_year"],
            "Fiscal year end": a["fy_end_date"],
            "Accepted by clearinghouse": a["fac_accepted_date"],
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
                ":green-badge[On this agency's money]" if agency and agency in f["agencies"] else "",
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
            if f["programs"]:
                st.caption(f"Programs: {f['programs']}. Passed through: "
                           f"{'; '.join(f['agencies']) or 'no Virginia state agency recognised'}.")
            if f["finding_text"]:
                st.text(f["finding_text"])
            else:
                st.info("The FAC holds no finding text for this audit. Read the audit report at the link above.")
            if f["planned_action"]:
                with st.expander("The locality's corrective action plan (its own words, not the auditor's)"):
                    st.text(f["planned_action"])

if not shown:
    st.success("No findings on file for this entity in any year loaded.")
