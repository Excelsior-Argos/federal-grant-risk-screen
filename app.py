"""Federal Grant Risk Screen: the page a state grants monitor uses.

Run:  .venv/Scripts/python -m streamlit run app.py

Two views. The worklist shows one agency's subrecipients and which need attention. A
locality view shows one subrecipient: its approved risk sheet, audit checks and findings.
"""
from datetime import date
from html import escape

import streamlit as st

import common
import risk

# Each visitor's click reruns this file, so remember results for an hour.
query = st.cache_data(ttl=3600)(common.query)
gather_evidence = st.cache_data(ttl=3600)(risk.gather_evidence)
agency_worklist = st.cache_data(ttl=3600)(risk.agency_worklist)

DEFAULT_AGENCY = "Department of Criminal Justice Services"
ALL = "All agencies"
SHORT = {  # the abbreviations Virginia agencies go by
    "Department of Criminal Justice Services": "DCJS",
    "Department of Social Services": "VDSS",
    "Department of Education": "VDOE",
    "Department of Emergency Management": "VDEM",
    "Department of Agriculture and Consumer Services": "VDACS",
    "Department of Motor Vehicles": "DMV",
    "Department of Housing and Community Development": "DHCD",
    "Department of Transportation": "VDOT",
    "Department of Health": "VDH",
    "Department of Behavioral Health and Developmental Services": "DBHDS",
    "Department of Rail and Public Transportation": "DRPT",
    "Department for Aging and Rehabilitative Services": "DARS",
    "Department of Environmental Quality": "DEQ",
}
OPINIONS = {"U": "Unmodified (clean)", "Q": "Qualified", "A": "Adverse", "D": "Disclaimer"}

st.set_page_config(page_title="Federal Grant Risk Screen", page_icon=":material/fact_check:", layout="wide")
st.html("""<style>
.block-container {padding-top: 3.6rem; max-width: 1180px;}
.kpi {border: 1px solid #E3E8EE; border-radius: 12px; padding: 14px 18px; background: #FFFFFF;}
.kpi .n {font-size: 30px; font-weight: 700; line-height: 1.15; color: #1C2430;}
.kpi .l {font-size: 13px; color: #5B6573; margin-top: 2px;}
.kpi.alert {border-color: #F5C2BD; background: #FFF8F7;}
.kpi.alert .n {color: #B42318;}
.pill {display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;
       margin: 0 6px 4px 0; white-space: nowrap;}
.pill.high {background: #FEE4E2; color: #B42318;}
.pill.medium {background: #FEF0C7; color: #B54708;}
.pill.low {background: #DCFAE6; color: #067647;}
.pill.grey {background: #F2F4F7; color: #475467;}
.pill.blue {background: #E7EEF6; color: #1F4E79;}
.quote {border-left: 3px solid #1F4E79; padding: 8px 14px; background: #F4F6F8; color: #344054;
        border-radius: 0 8px 8px 0; margin: 6px 0;}
.muted {color: #667085; font-size: 13px;}
.name {font-size: 17px; font-weight: 650; color: #1C2430;}
.big {font-size: 30px; font-weight: 750; color: #1C2430; margin: 4px 0 6px 0; line-height: 1.2;}
</style>""")


# ---------- small helpers ----------

def pill(text, kind="grey"):
    return f'<span class="pill {kind}">{escape(str(text))}</span>'


def rating_pill(rating):
    if not rating:
        return pill("Not rated yet")
    if rating == "no_basis":
        return pill("No findings to rate")
    return pill(f"{rating.capitalize()} risk", rating)


def kpi(number, label, alert=False):
    return f'<div class="kpi{" alert" if alert else ""}"><div class="n">{number}</div><div class="l">{escape(label)}</div></div>'


def short(agency):
    return SHORT.get(agency, agency)


def nice_date(value):
    """date(2027, 3, 8) -> 'Mar 8, 2027'."""
    return f"{value:%b} {value.day}, {value:%Y}" if value else ""


# Short names for the federal compliance areas an auditor records with each finding.
AREAS = {"A": "Allowed activities", "B": "Allowable costs", "C": "Cash management", "D": "Davis-Bacon wages",
         "E": "Eligibility", "F": "Equipment", "G": "Matching", "H": "Period of performance",
         "I": "Procurement", "J": "Program income", "K": "Real property", "L": "Reporting",
         "M": "Subrecipient monitoring", "N": "Special tests", "P": "Other requirements"}


def areas(codes):
    """'IL' -> 'Procurement, Reporting'."""
    return ", ".join(AREAS.get(code, code) for code in sorted(set(codes or ""))) or "Area not recorded"


def finding_headlines(findings, most=4):
    """The compliance areas a locality's findings fall in, most common first: 'Procurement · Reporting'."""
    counts = {}
    for f in findings:
        for code in set(f["requirements"] or ""):
            counts[code] = counts.get(code, 0) + 1
    names = [AREAS.get(code, code) for code, _ in sorted(counts.items(), key=lambda item: -item[1])]
    extra = f" and {len(names) - most} more" if len(names) > most else ""
    return ("Problems with: " + " · ".join(names[:most]) + extra) if names else ""


def open_locality(ein):
    st.query_params["locality"] = ein


def back_to_worklist():
    st.query_params.pop("locality", None)


def approved_sheets():
    """The latest approved risk sheet for each locality. Not cached, so an approval shows straight away."""
    if not common.query("select to_regclass('risk_sheets') is not null as ready")[0]["ready"]:
        return {}
    rows = common.query("""
        select distinct on (auditee_ein) * from risk_sheets
        where status = 'approved' order by auditee_ein, reviewed_at desc
    """)
    return {row["auditee_ein"]: row for row in rows}


# ---------- the side panel: whose subrecipients, and direct search ----------

totals = query("""
    select (select max(audit_year) from audits) as last_year, (select max(loaded_at)::date from audits) as loaded_on
""")[0]
first_year = totals["last_year"] - risk.WINDOW_YEARS + 1
agencies = [row["agency"] for row in query("""
    select p.agency from passthroughs p join audits a using (report_id)
    where p.agency is not null and a.audit_year >= %s
    group by 1 order by count(distinct a.auditee_ein) desc
""", (first_year,))]
choices = [ALL] + agencies
wanted = st.query_params.get("agency", DEFAULT_AGENCY)
localities = query("""
    select distinct on (auditee_ein) auditee_ein, auditee_name, auditee_city
    from audits order by auditee_ein, audit_year desc, fac_accepted_date desc
""")
names = {row["auditee_ein"]: row["auditee_name"] for row in localities}

with st.sidebar:
    st.markdown("### Federal Grant Risk Screen")
    choice = st.selectbox(
        "Your agency", choices, index=choices.index(wanted) if wanted in choices else 0,
        format_func=lambda a: a if a == ALL else
        f"{a.replace('Department of ', '').replace('Department for ', '')} ({short(a)})")
    if choice != wanted:
        st.query_params["agency"] = choice
        back_to_worklist()
        st.rerun()
    agency = None if choice == ALL else choice

    searched = st.selectbox(
        "Find a locality", sorted(localities, key=lambda r: r["auditee_name"].lower()), index=None,
        placeholder="Type a name", key=f"search-{st.query_params.get('locality')}",
        format_func=lambda r: f"{r['auditee_name']} ({(r['auditee_city'] or '').title()})")
    if searched:
        open_locality(searched["auditee_ein"])
        st.rerun()

    st.divider()
    st.caption(f"Virginia local governments' federal single audits from the Federal Audit Clearinghouse. "
               f"Audit years {first_year} to {totals['last_year']}. Data loaded {nice_date(totals['loaded_on'])}.")
    with st.expander("How to read this"):
        st.markdown(
            "- **Audit problem on your grants**: the auditor attached a finding to a program your agency funded.\n"
            "- **Serious**: a material weakness, or a problem big enough to change the auditor's opinion.\n"
            "- **Repeat**: the same problem was in last year's audit.\n"
            "- **Filed late**: an audit is due nine months after the fiscal year ends.\n"
            "- **Your written decision**: federal rules give you six months from the audit's filing to answer "
            "each finding on your grants (2 CFR 200.521).\n"
            "- **Risk rating**: drafted by AI from the auditor's labels and approved by a person.")

sheets = approved_sheets()
ein = st.query_params.get("locality")


# =====================================================================
# The worklist
# =====================================================================

def locality_card(card_ein, headline, w):
    sheet = sheets.get(card_ein)
    with st.container(border=True):
        left, right = st.columns([5, 1.3], vertical_alignment="center")
        with left:
            st.markdown(f'<div class="name">{escape(names.get(card_ein, card_ein))}</div>'
                        f'<div>{rating_pill(sheet["final_rating"] if sheet else None)}'
                        f'<span class="muted">{escape(headline)}</span></div>', unsafe_allow_html=True)
            if w and w["findings"]:
                st.markdown(f'<div style="margin-top:2px">{escape(finding_headlines(w["findings"]))}</div>',
                            unsafe_allow_html=True)
            if w and (w["decision_due"] or w["late"]):
                notes = []
                if w["decision_due"]:
                    verb = "was" if w["decision_due"] < date.today() else "is"
                    notes.append(f"Your written decision {verb} due {nice_date(w['decision_due'])}")
                if w["late"]:
                    notes.append(f"latest audit filed {w['months_after_year_end']} months after year end")
                st.markdown(f'<div class="muted">{escape(" · ".join(notes))}</div>', unsafe_allow_html=True)
        with right:
            st.button("Open", key=f"open-{card_ein}", on_click=open_locality, args=(card_ein,),
                      type="primary", width="stretch")


def worklist_view():
    st.markdown('<div class="big">Federal Grant Risk Screen</div>', unsafe_allow_html=True)
    if not agency:
        st.markdown('<p class="muted">Pick your agency on the left to see your subrecipients, '
                    'or find any locality by name.</p>', unsafe_allow_html=True)
        flagged = query("""
            select a.auditee_ein, count(distinct (f.report_id, f.reference_number)) as findings
            from findings f join audits a using (report_id)
            where a.audit_year >= %s group by 1 order by 2 desc
        """, (first_year,))
        st.subheader(f"{len(flagged)} localities with audit findings, {first_year} to {totals['last_year']}")
        for row in flagged:
            locality_card(row["auditee_ein"], f"{row['findings']} audit findings", None)
        return

    worklist = agency_worklist(agency)
    order = {"high": 0, "medium": 1, "low": 2}
    attention = sorted((w for w in worklist if w["own_findings"]),
                       key=lambda w: (order.get((sheets.get(w["ein"]) or {}).get("final_rating"), 3), -w["own_findings"]))

    st.markdown(f'<p class="muted">Which of your subrecipients need a closer look, based on their federal '
                f'single audits for {first_year} to {totals["last_year"]}.</p>', unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].markdown(kpi(len(worklist), f"subrecipients of {short(agency)}"), unsafe_allow_html=True)
    cols[1].markdown(kpi(len(attention), "have audit problems on your grants", alert=bool(attention)),
                     unsafe_allow_html=True)
    cols[2].markdown(kpi(sum(1 for w in worklist if w["late"]), "filed their latest audit late"),
                     unsafe_allow_html=True)
    cols[3].markdown(kpi(sum(1 for w in worklist if w["next_audit_overdue"]), "have an overdue audit"),
                     unsafe_allow_html=True)

    st.write("")
    st.subheader("Needs your attention")
    if not attention:
        st.success(f"No subrecipient of {short(agency)} has an audit finding on your grants in its last two audits.")
    for w in attention:
        serious = sum(1 for f in w["findings"] if f["is_material_weakness"] or f["is_modified_opinion"])
        repeat = sum(1 for f in w["findings"] if f["is_repeat_finding"])
        parts = [f"{w['own_findings']} audit problem{'s' if w['own_findings'] != 1 else ''} on your grants"]
        if serious:
            parts.append(f"{serious} serious")
        if repeat:
            parts.append(f"{repeat} repeat")
        locality_card(w["ein"], " · ".join(parts), w)

    st.write("")
    st.subheader("Late or missing audits")
    st.markdown('<p class="muted">No findings on your grants, but the latest audit arrived late or the next one is '
                'overdue. Select a row to open it.</p>', unsafe_allow_html=True)
    late = sorted((w for w in worklist if (w["late"] or w["next_audit_overdue"]) and not w["own_findings"]),
                  key=lambda w: (not w["next_audit_overdue"], -w["months_after_year_end"]))
    picked = st.dataframe(
        [{"Locality": w["name"], "Latest audit": w["audit_year"],
          "Filed": f"{w['months_after_year_end']} months after year end",
          "Next audit": "Overdue" if w["next_audit_overdue"] else "Not yet due"} for w in late],
        hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        column_config={"Latest audit": st.column_config.NumberColumn(format="%d")}, key=f"late-{agency}")
    if picked.selection.rows:
        open_locality(late[picked.selection.rows[0]]["ein"])
        st.rerun()

    with st.expander(f"All {len(worklist)} subrecipients of {short(agency)}"):
        everyone = sorted(worklist, key=lambda w: w["name"].lower())
        picked_all = st.dataframe(
            [{"Locality": w["name"], "Latest audit": w["audit_year"], "Filed late": w["late"],
              "Next audit overdue": w["next_audit_overdue"], "Problems on your grants": w["own_findings"]}
             for w in everyone],
            hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
            column_config={"Latest audit": st.column_config.NumberColumn(format="%d")}, key=f"all-{agency}")
        if picked_all.selection.rows:
            open_locality(everyone[picked_all.selection.rows[0]]["ein"])
            st.rerun()


# =====================================================================
# One locality
# =====================================================================

def check(ok, title, detail):
    icon = ":green[:material/check_circle:]" if ok else ":orange[:material/warning:]"
    st.markdown(f"{icon} **{title}**  \n<span class='muted'>{escape(detail)}</span>", unsafe_allow_html=True)


def locality_view():
    st.button(f"← Back to the {short(agency) + ' ' if agency else ''}worklist", on_click=back_to_worklist)
    evidence = gather_evidence(ein)
    review = risk.audit_review(evidence, agency)
    sheet = sheets.get(ein)
    whose = "your grants" if agency else "federal grants"

    st.markdown(f'<div class="big">{escape(names.get(ein, ein))}</div>', unsafe_allow_html=True)
    facts = [rating_pill(sheet["final_rating"] if sheet else None)]
    if review["audit_on_file"]:
        facts.append(pill(f"${review['federal_spending']:,.0f} federal spending in {review['audit_year']}", "blue"))
        if review["late"]:
            facts.append(pill("Latest audit filed late", "medium"))
        if review["next_audit_overdue"]:
            facts.append(pill("Next audit overdue", "medium"))
        if agency and review["own_findings"]:
            facts.append(pill(f"{len(review['own_findings'])} audit problems on your grants", "high"))
    st.markdown("".join(facts), unsafe_allow_html=True)

    findings = query("""
        select f.report_id, a.audit_year, f.reference_number,
               bool_or(f.is_material_weakness) as mw, bool_or(f.is_significant_deficiency) as sd,
               bool_or(f.is_modified_opinion) as mo, bool_or(f.is_repeat_finding) as repeat,
               bool_or(f.is_questioned_costs) as qc,
               string_agg(distinct f.type_requirement, '') as requirements,
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
        group by f.report_id, a.audit_year, f.reference_number, t.finding_text, c.planned_action
        order by a.audit_year desc, f.reference_number
    """, (ein,))
    recent = [f for f in findings if f["audit_year"] >= first_year]
    tabs = st.tabs(["Summary", "Audit checks", f"Findings ({len(recent)})", "Audit history"])

    # --- Summary: the approved risk sheet ---
    with tabs[0]:
        if sheet:
            body = sheet["sheet"]
            st.write(body["summary"])
            if body["reasons"]:
                st.markdown("**Why**")
                for reason in body["reasons"]:
                    report = next((f["report_id"] for f in findings if f["reference_number"] == reason["reference_number"]
                                   and f["audit_year"] == reason["audit_year"]), None)
                    source = f' · <a href="{common.source_url(report)}" target="_blank">source</a>' if report else ""
                    st.markdown(
                        f'{escape(reason["reason"])}<div class="quote">"{escape(reason["quote"])}"</div>'
                        f'<div class="muted">The auditor\'s words, finding {escape(reason["reference_number"])}, '
                        f'{reason["audit_year"]} audit{source}</div>', unsafe_allow_html=True)
                    st.write("")
            if body["next_checks"]:
                st.markdown("**What to check next**")
                for item in body["next_checks"]:
                    st.markdown(f"- {item}")
            drafted = f"Drafted by AI ({sheet['model']})" if sheet["model"] else "Written by fixed rules, with no AI"
            st.caption(f"{drafted}. Approved by {sheet['reviewer']} on {nice_date(sheet['reviewed_at'])}."
                       + (f" {sheet['reviewer_note']}" if sheet["reviewer_note"] else ""))
        elif not recent:
            st.success(f"No audit findings on {whose} for {first_year} to {totals['last_year']}. "
                       "On the state risk forms, that scores as the lowest audit risk.")
            if review["audit_on_file"] and review["statement_material_weakness"]:
                st.warning("The auditor did report a weakness in the financial statements. The clearinghouse "
                           "has no detail on it, so read the audit report.")
        else:
            st.info("No risk sheet has been approved for this locality yet. The findings are in the Findings tab.")

    # --- Audit checks: what the state risk form asks about the audit ---
    with tabs[1]:
        if not review["audit_on_file"]:
            st.error(f"No single audit is on file for {first_year} to {totals['last_year']}. "
                     "Find out whether one was required.")
        else:
            check(True, f"Audit on file for {review['audit_year']}",
                  f"Fiscal year ended {nice_date(review['fiscal_year_end'])}.")
            check(not review["late"], "Filed on time" if not review["late"] else "Filed late",
                  f"Accepted {nice_date(review['accepted_by_fac'])}, {review['months_after_year_end']} months after "
                  "year end. Audits are due within nine months.")
            check(not review["next_audit_overdue"],
                  "Next audit is overdue" if review["next_audit_overdue"] else "Next audit not yet due",
                  "The audit for the following year is due nine months after that year ends.")
            clean = review["opinion_financial_statements"] == "unmodified" and \
                review["opinion_major_programs"] in ("unmodified", None)
            check(clean, "Auditor's opinions" + ("" if clean else ": not clean"),
                  f"Financial statements: {review['opinion_financial_statements'] or 'not recorded'}. "
                  f"Major federal programs: {review['opinion_major_programs'] or 'none tested'}.")
            own = review["own_findings"]
            if not own:
                detail = "None in the last two audits."
            elif review["decision_due"]:
                verb = "was" if review["decision_due"] < date.today() else "is"
                detail = f"Your written decision on each {verb} due {nice_date(review['decision_due'])} (2 CFR 200.521)."
            else:
                detail = "They are in the earlier audit. Check that each was resolved."
            check(not own, f"Audit problems on {whose}: {len(own)}", detail)
            if agency and review["own_programs"]:
                st.markdown(f"**Your programs in the {review['audit_year']} audit**")
                st.dataframe([{"Program": f"{w['aln']} {(w['federal_program_name'] or '').title()}",
                               "Spent": w["amount_expended"],
                               "Tested in depth by the auditor": "Yes" if w["is_major"] else "No",
                               "Opinion": OPINIONS.get(w["audit_report_type"], "")} for w in review["own_programs"]],
                             hide_index=True, width="stretch",
                             column_config={"Spent": st.column_config.NumberColumn(format="dollar")})
            with st.expander("How this fills in the state risk forms"):
                st.dataframe(
                    [{"Form": "Virginia VDEM", "Row": r, "Answer": a, "Points": p} for r, a, p in risk.vdem_form_rows(review)]
                    + [{"Form": "Virginia DCJS", "Row": r, "Answer": a, "Points": p} for r, a, p in risk.dcjs_form_rows(review)]
                    + [{"Form": "North Carolina DHHS", "Row": "Single Audit",
                        "Answer": f"{risk.nc_matrix_row(review)[0]}: {risk.nc_matrix_row(review)[1]}",
                        "Points": risk.nc_matrix_row(review)[2]}],
                    hide_index=True, width="stretch")
                st.caption("Worked out by code from the audit data, with no AI. These are the audit rows only; the "
                           "rest of each form needs the agency's own records.")

    # --- Findings ---
    with tabs[2]:
        if not recent:
            st.write(f"No findings on federal grants for {first_year} to {totals['last_year']}.")
        else:
            st.caption("Each finding is the auditor's own report. It is marked as yours when the auditor attached it "
                       "to a program your agency funded; if that program also came from elsewhere, read it to confirm "
                       "it concerns your part.")
        for f in recent:
            with st.container(border=True):
                tags = []
                if agency and agency in f["agencies"]:
                    tags.append(pill("On your grants", "blue"))
                if f["mw"] or f["mo"]:
                    tags.append(pill("Serious", "high"))
                elif f["sd"]:
                    tags.append(pill("Significant deficiency", "medium"))
                if f["repeat"]:
                    tags.append(pill("Repeat", "medium"))
                if f["qc"]:
                    tags.append(pill("Questioned costs", "medium"))
                st.markdown(f'<div class="name">{escape(areas(f["requirements"]))}</div>'
                            f'<div class="muted">Finding {escape(f["reference_number"])} · {f["audit_year"]} audit · '
                            f'{escape((f["programs"] or "program not recorded").title())}</div>'
                            f'<div style="margin-top:6px">{"".join(tags)}</div>', unsafe_allow_html=True)
                with st.expander("What the auditor found"):
                    st.text(f["finding_text"] or "The clearinghouse holds no text for this finding. Read the audit report.")
                    st.markdown(f"[Open the audit on fac.gov]({common.source_url(f['report_id'])})")
                if f["planned_action"]:
                    with st.expander("What the locality says it will do (its own words)"):
                        st.text(f["planned_action"])

    # --- Audit history ---
    with tabs[3]:
        history = query("""
            select a.*, (select count(distinct reference_number) from findings f where f.report_id = a.report_id) as n
            from audits a where a.auditee_ein = %s order by audit_year desc, fac_accepted_date desc
        """, (ein,))
        st.dataframe(
            [{"Audit year": a["audit_year"], "Filed": a["fac_accepted_date"],
              "Months after year end": risk.months_between(a["fy_end_date"], a["fac_accepted_date"]),
              "Federal spending": a["total_amount_expended"],
              "Opinion": risk.worst_opinion([a["gaap_results"]]) or "", "Findings": a["n"],
              "Audit": common.source_url(a["report_id"])} for a in history],
            hide_index=True, width="stretch",
            column_config={"Audit year": st.column_config.NumberColumn(format="%d"),
                           "Federal spending": st.column_config.NumberColumn(format="dollar"),
                           "Audit": st.column_config.LinkColumn(display_text="fac.gov")})


if ein and ein in names:
    locality_view()
else:
    worklist_view()
