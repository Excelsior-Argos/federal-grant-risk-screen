"""The AI layer: gather a locality's evidence, draft a risk sheet, check it, save it.

Used by evaluate.py (Phase 2) and workflow.py (Phase 3). Nothing here approves anything.
"""
import calendar
import json
from datetime import date
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from common import query, requirement_names, source_url

MODEL = "claude-opus-5-5"
PRICE_PER_MILLION = {"input": 4.00, "output": 20.00}  # US dollars, Claude Opus 5.5 list price
WINDOW_YEARS = 3
# The rubric file opens with a note to me about its review status ("> ..." lines). That note
# is not part of the rubric, so the model does not get it.
RUBRIC = "\n".join(line for line in Path(__file__).with_name("RUBRIC.md").read_text(encoding="utf-8").splitlines()
                   if not line.startswith(">"))


# ---------- 1. Evidence: everything the rating is allowed to rest on ----------

def gather_evidence(ein):
    """Collect one locality's audits and findings for the review window."""
    last_year = query("select max(audit_year) as year from audits")[0]["year"]
    first_year = last_year - WINDOW_YEARS + 1

    audits = query("""
        select report_id, auditee_name, audit_year, fy_end_date, fac_accepted_date, total_amount_expended,
               gaap_results, is_going_concern_included, is_internal_control_material_weakness_disclosed,
               is_material_noncompliance_disclosed, is_low_risk_auditee
        from audits
        where auditee_ein = %s and audit_year between %s and %s
        order by audit_year desc, fac_accepted_date desc
    """, (ein, first_year, last_year))

    # One row per federal program in each audit, with the state agencies that passed the money down.
    awards = query("""
        select a.audit_year, w.report_id, w.award_reference, w.aln, w.federal_program_name, w.amount_expended,
               w.is_major, w.is_direct, w.audit_report_type,
               array_remove(array_agg(distinct p.agency), null) as agencies
        from awards w
        join audits a using (report_id)
        left join passthroughs p using (report_id, award_reference)
        where a.auditee_ein = %s and a.audit_year between %s and %s
        group by a.audit_year, w.report_id, w.award_reference, w.aln, w.federal_program_name, w.amount_expended,
                 w.is_major, w.is_direct, w.audit_report_type
        order by a.audit_year desc, w.amount_expended desc
    """, (ein, first_year, last_year))

    # One row per finding. A finding can touch several awards; a flag counts if it is set on any of them.
    findings = query("""
        select a.audit_year, f.report_id, f.reference_number,
               count(distinct f.award_reference) as awards,
               string_agg(distinct f.type_requirement, '') as type_requirement,
               bool_or(f.is_material_weakness) as is_material_weakness,
               bool_or(f.is_significant_deficiency) as is_significant_deficiency,
               bool_or(f.is_modified_opinion) as is_modified_opinion,
               bool_or(f.is_repeat_finding) as is_repeat_finding,
               bool_or(f.is_questioned_costs) as is_questioned_costs,
               string_agg(distinct w.aln || ' ' || w.federal_program_name, '; ') as programs,
               array_remove(array_agg(distinct p.agency), null) as agencies,
               t.finding_text, c.planned_action
        from findings f
        join audits a using (report_id)
        left join awards w using (report_id, award_reference)
        left join passthroughs p using (report_id, award_reference)
        left join finding_texts t using (report_id, reference_number)
        left join corrective_actions c using (report_id, reference_number)
        where a.auditee_ein = %s and a.audit_year between %s and %s
        group by a.audit_year, f.report_id, f.reference_number, t.finding_text, c.planned_action
        order by a.audit_year desc, f.reference_number
    """, (ein, first_year, last_year))

    name = query("""
        select auditee_name from audits where auditee_ein = %s
        order by audit_year desc, fac_accepted_date desc limit 1
    """, (ein,))[0]["auditee_name"]
    return {"ein": ein, "name": name, "first_year": first_year, "last_year": last_year,
            "audits": audits, "awards": awards, "findings": findings}


def audit_flag_notes(evidence):
    """Audit-level warnings that the FAC records with no finding text behind them."""
    notes = []
    for audit in evidence["audits"]:
        flags = [label for label, on in [
            ("a material weakness in financial reporting", audit["is_internal_control_material_weakness_disclosed"]),
            ("material noncompliance", audit["is_material_noncompliance_disclosed"]),
            ("a going-concern doubt", audit["is_going_concern_included"]),
        ] if on]
        if flags:
            notes.append(f"The {audit['audit_year']} audit disclosed {' and '.join(flags)}.")
    return notes


# ---------- 2. The audit review a real agency form asks for, worked out by code ----------
#
# Sources: 2 CFR 200.332 and 200.512, the Virginia DCJS Grant Monitoring Risk Assessment form,
# and the North Carolina DHHS county subrecipient risk matrix. See PROCESS.md.

AUDIT_DUE_MONTHS = 9  # 2 CFR 200.512: an audit is due nine months after the fiscal year ends


DECISION_DUE_MONTHS = 6  # 2 CFR 200.521(d): a management decision is due six months after the FAC accepts the audit


def months_between(start, end):
    """Whole months from one date to another, rounded up.

    Fiscal years end on the last day of a month, so 30 June to 31 March counts as nine months, not ten.
    """
    months = (end.year - start.year) * 12 + (end.month - start.month)
    start_is_month_end = start.day == calendar.monthrange(start.year, start.month)[1]
    return months + (1 if end.day > start.day and not start_is_month_end else 0)


def months_after(start, months):
    """The date a number of months after another date."""
    month = start.month - 1 + months
    year, month = start.year + month // 12, month % 12 + 1
    return start.replace(year=year, month=month, day=min(start.day, calendar.monthrange(year, month)[1]))


def audit_threshold(previous_year_end):
    """Federal spending at which the next fiscal year needs a single audit (2 CFR 200.501).

    The line rose from $750,000 to $1,000,000 for fiscal years that begin on or after 1 October 2024.
    The next fiscal year begins the day after the previous one ended.
    """
    return 1_000_000 if previous_year_end >= date(2024, 9, 30) else 750_000


def next_audit_overdue(latest_year_end):
    """True when the audit for the year after the latest one on file should have been filed by today."""
    return date.today() > months_after(latest_year_end, 12 + AUDIT_DUE_MONTHS)


def worst_opinion(opinions):
    """The most serious of a list of auditor opinions: adverse or disclaimer, then qualified, then unmodified."""
    # The FAC writes opinions two ways: words ("unmodified_opinion,qualified_opinion") and letters (U, Q, A, D).
    words = set()
    for opinion in opinions:
        words.update(re.split(r"[\s,_]+", str(opinion or "").lower()))
    if words & {"adverse", "disclaimer", "a", "d"}:
        return "adverse or disclaimer"
    if words & {"qualified", "q"}:
        return "qualified"
    return "unmodified" if words & {"unmodified", "u"} else None


def audit_review(evidence, agency=None):
    """The audit facts a pass-through agency records about one subrecipient. No AI is involved.

    With an agency named, 'its' programs and findings are the ones on money that agency passed down.
    """
    if not evidence["audits"]:
        return {"audit_on_file": False, "agency": agency}

    latest = evidence["audits"][0]
    programs = [w for w in evidence["awards"] if w["report_id"] == latest["report_id"]]
    own = [w for w in programs if agency in w["agencies"]] if agency else programs
    recent = [f for f in evidence["findings"] if f["audit_year"] >= latest["audit_year"] - 1]  # the last two years
    own_findings = [f for f in recent if agency in f["agencies"]] if agency else recent
    months = months_between(latest["fy_end_date"], latest["fac_accepted_date"])

    return {
        "audit_on_file": True,
        "agency": agency,
        "audit_year": latest["audit_year"],
        "report_id": latest["report_id"],
        "fiscal_year_end": latest["fy_end_date"],
        "accepted_by_fac": latest["fac_accepted_date"],
        "months_after_year_end": months,
        "late": months > AUDIT_DUE_MONTHS,
        "years_behind": evidence["last_year"] - latest["audit_year"],  # 0 when the newest audit year is on file
        "next_audit_overdue": next_audit_overdue(latest["fy_end_date"]),
        "federal_spending": latest["total_amount_expended"],
        "low_risk_auditee": latest["is_low_risk_auditee"],
        "going_concern": latest["is_going_concern_included"],
        "statement_material_weakness": latest["is_internal_control_material_weakness_disclosed"],
        "opinion_financial_statements": worst_opinion([latest["gaap_results"]]),
        "opinion_major_programs": worst_opinion([w["audit_report_type"] for w in programs if w["is_major"]]),
        "own_programs": own,
        "own_spending": sum(w["amount_expended"] or 0 for w in own),
        "own_program_audited_as_major": any(w["is_major"] for w in own),
        "opinion_own_programs": worst_opinion([w["audit_report_type"] for w in own if w["is_major"]]),
        "findings_two_years": len(recent),
        "own_findings": own_findings,
        # Findings in the latest audit, split by whose money they are on.
        "latest_own": sum(1 for f in own_findings if f["report_id"] == latest["report_id"]),
        "latest_other": sum(1 for f in recent if f["report_id"] == latest["report_id"] and f not in own_findings),
        "next_audit_threshold": audit_threshold(latest["fy_end_date"]),
        # The agency owes a written decision on each finding on its own money in the latest audit.
        "decision_due": (months_after(latest["fac_accepted_date"], DECISION_DUE_MONTHS)
                         if any(f["report_id"] == latest["report_id"] for f in own_findings) else None),
    }


def dcjs_form_rows(review):
    """The two audit rows of Virginia DCJS's Grant Monitoring Risk Assessment form: (row, answer, points)."""
    if not review["audit_on_file"]:
        return [("Single-Audit", "No audit on file. The form gives 6 points if federal grants exceed $750,000, "
                 "otherwise 2. The FAC cannot say which.", None)]
    whose = review["agency"] or "the agency's"
    opinion = worst_opinion([review["opinion_financial_statements"], review["opinion_major_programs"]])
    if opinion == "adverse or disclaimer":
        row = ("Audit with Adverse or Disclaimer of Opinion", 12)
    elif opinion == "qualified":
        row = ("Audit with Qualified Opinion", 4)
    elif review["agency"] and review["own_program_audited_as_major"]:
        row = (f"Audit performed on a {whose} program and Unmodified", 0)
    else:
        row = (f"Audit performed on a program other than {whose} and Unmodified", 1)
    return [("Single-Audit", "Yes", 0), ("Audit Opinion", row[0], row[1])]


def vdem_form_rows(review):
    """The two audit rows of Virginia VDEM's subrecipient financial risk assessment: (row, answer, points).

    This form looks at the latest audit only and scores a finding by whose money it is on, not by how
    severe it is. On the full form 0 to 15 points is low risk, 15 to 34 medium and 35 or more high, so
    one finding on the agency's own grant is enough for high.
    """
    if not review["audit_on_file"]:
        return [("G. Audit performed", "No audit on file. The form gives 5 points if a single audit was required "
                 "and not done. The FAC cannot say whether one was required.", None)]
    rows = []
    if review["next_audit_overdue"] and review["federal_spending"] >= review["next_audit_threshold"]:
        rows.append(("G. Audit performed", f"The next year's audit is overdue, and the year on file spent "
                     f"${review['federal_spending']:,.0f} in federal money, over the "
                     f"${review['next_audit_threshold']:,.0f} line. Probably required and not done.", 5))
    else:
        rows.append(("G. Audit performed", "Single audit on file", 0))
    if not review["agency"]:
        answer = ("Findings in the latest audit. Pick a state agency to see whose money they are on."
                  if review["latest_own"] else "No findings in the latest audit")
        rows.append(("H. Single audit results", answer, None if review["latest_own"] else 0))
    elif review["latest_own"] and review["latest_other"]:
        rows.append(("H. Single audit results", "Findings on this agency's grant and on another agency's", 40))
    elif review["latest_own"]:
        rows.append(("H. Single audit results", "Finding on a grant this agency manages", 35))
    elif review["latest_other"]:
        rows.append(("H. Single audit results", "Finding on another agency's program only", 5))
    else:
        rows.append(("H. Single audit results", "No findings in the latest audit", 0))
    return rows


def nc_matrix_row(review):
    """The Single Audit row of North Carolina DHHS's county subrecipient risk matrix: (level, answer, weight).

    Our reading of its words: a finding is 'significant' if it is a material weakness or led to a modified
    opinion, 'not resolved' if the auditor marked it a repeat, and questioned costs stand in for chargebacks.
    """
    if not review["audit_on_file"]:
        return (None, "No audit on file, so the row cannot be scored.", None)
    findings = review["own_findings"]
    if not findings:
        return ("Low", "No audit findings for past 2 years.", 2)
    if any(f["is_material_weakness"] or f["is_modified_opinion"] or f["is_repeat_finding"] or f["is_questioned_costs"]
           for f in findings):
        return ("High", "Significant audit findings within past 2 years; audit findings not addressed and/or "
                "not resolved in timely manner; and/or chargebacks required.", 6)
    return ("Moderate", "Audit findings within the past two years with pending or completed corrective action "
            "and not requiring county charge backs.", 4)


def agency_worklist(agency):
    """Every locality one state agency passed money to in the review window, with its audit review.

    This is the list a monitor starts from: who are my subrecipients, is each audit on file and on
    time, and which ones have findings on my money. It is one database query, so it is quick.
    """
    last_year = query("select max(audit_year) as year from audits")[0]["year"]
    rows = query("""
        with subs as (
            select distinct a.auditee_ein
            from passthroughs p join audits a using (report_id)
            where p.agency = %(agency)s and a.audit_year between %(first)s and %(last)s
        ), latest as (  -- each subrecipient's most recent audit
            select distinct on (a.auditee_ein) a.*
            from audits a join subs using (auditee_ein)
            where a.audit_year between %(first)s and %(last)s
            order by a.auditee_ein, a.audit_year desc, a.fac_accepted_date desc
        ), own as (  -- this agency's programs in that audit
            select l.auditee_ein, sum(w.amount_expended) as own_spending, bool_or(w.is_major) as own_major
            from latest l join awards w using (report_id)
            where exists (select 1 from passthroughs p where p.report_id = w.report_id
                          and p.award_reference = w.award_reference and p.agency = %(agency)s)
            group by 1
        ), majors as (
            select l.auditee_ein, string_agg(distinct w.audit_report_type, ' ') as opinions
            from latest l join awards w using (report_id) where w.is_major group by 1
        ), per_finding as (  -- findings on this agency's money in the last two audit years
            select l.auditee_ein, a.audit_year, f.reference_number, bool_or(f.report_id = l.report_id) as in_latest,
                   bool_or(f.is_material_weakness) as mw, bool_or(f.is_modified_opinion) as mo,
                   bool_or(f.is_repeat_finding) as rep, bool_or(f.is_questioned_costs) as qc,
                   string_agg(distinct w.federal_program_name, '; ') as programs,
                   string_agg(distinct f.type_requirement, '') as requirements
            from latest l
            join audits a on a.auditee_ein = l.auditee_ein and a.audit_year >= l.audit_year - 1
            join findings f on f.report_id = a.report_id
            left join awards w on w.report_id = f.report_id and w.award_reference = f.award_reference
            where exists (select 1 from passthroughs p where p.report_id = f.report_id
                          and p.award_reference = f.award_reference and p.agency = %(agency)s)
            group by 1, 2, 3
        ), found as (
            select auditee_ein, json_agg(json_build_object(
                       'audit_year', audit_year, 'reference_number', reference_number, 'in_latest', in_latest,
                       'is_material_weakness', mw, 'is_modified_opinion', mo,
                       'is_repeat_finding', rep, 'is_questioned_costs', qc, 'programs', programs,
                       'requirements', requirements)) as own_findings
            from per_finding group by 1
        )
        select l.auditee_ein, l.auditee_name, l.audit_year, l.report_id, l.fy_end_date, l.fac_accepted_date,
               l.gaap_results, l.total_amount_expended, o.own_spending, coalesce(o.own_major, false) as own_major,
               m.opinions, coalesce(f.own_findings, '[]'::json) as own_findings,
               (select count(distinct x.reference_number) from findings x where x.report_id = l.report_id) as latest_total
        from latest l
        left join own o using (auditee_ein)
        left join majors m using (auditee_ein)
        left join found f using (auditee_ein)
        order by l.auditee_name
    """, {"agency": agency, "first": last_year - WINDOW_YEARS + 1, "last": last_year})

    worklist = []
    for row in rows:
        months = months_between(row["fy_end_date"], row["fac_accepted_date"])
        latest_own = sum(1 for f in row["own_findings"] if f["in_latest"])
        review = {
            "audit_on_file": True, "agency": agency,
            "opinion_financial_statements": worst_opinion([row["gaap_results"]]),
            "opinion_major_programs": worst_opinion([row["opinions"]]),
            "own_program_audited_as_major": row["own_major"],
            "own_findings": row["own_findings"],
            "latest_own": latest_own, "latest_other": row["latest_total"] - latest_own,
            "next_audit_overdue": next_audit_overdue(row["fy_end_date"]),
            "federal_spending": row["total_amount_expended"],
            "next_audit_threshold": audit_threshold(row["fy_end_date"]),
        }
        worklist.append({
            "ein": row["auditee_ein"], "name": row["auditee_name"], "audit_year": row["audit_year"],
            "report_id": row["report_id"], "next_audit_overdue": review["next_audit_overdue"],
            "months_after_year_end": months, "late": months > AUDIT_DUE_MONTHS,
            "own_spending": row["own_spending"], "own_findings": len(row["own_findings"]),
            "findings": row["own_findings"],
            "decision_due": (months_after(row["fac_accepted_date"], DECISION_DUE_MONTHS)
                             if any(f["in_latest"] for f in row["own_findings"]) else None),
            "vdem_points": sum(points for _, _, points in vdem_form_rows(review)),
            "dcjs_points": sum(points for _, _, points in dcjs_form_rows(review)),
            "nc_level": nc_matrix_row(review)[0],
        })
    return worklist


# ---------- 3. The rubric's steps 1 to 4, applied by code as a reference ----------

def rule_rating(evidence):
    """Rate from the yes/no flags alone. No AI, and no reading of the text."""
    findings = evidence["findings"]
    if not findings:
        return "no_basis"

    latest_year = max(audit["audit_year"] for audit in evidence["audits"])
    latest = [f for f in findings if f["audit_year"] == latest_year]
    earlier = [f for f in findings if f["audit_year"] < latest_year]

    def serious(finding):
        return finding["is_material_weakness"] or finding["is_modified_opinion"]

    going_concern = any(a["is_going_concern_included"] for a in evidence["audits"] if a["audit_year"] == latest_year)
    if (going_concern
            or any(serious(f) and (f["is_repeat_finding"] or f["is_questioned_costs"]) for f in latest)
            or (any(serious(f) for f in latest) and any(serious(f) for f in earlier))):
        return "high"
    if (any(serious(f) or f["is_repeat_finding"] or f["is_questioned_costs"] for f in latest)
            or len(latest) >= 3):
        return "medium"
    return "low"


# ---------- 4. The risk sheet and the AI call that drafts it ----------

class Reason(BaseModel):
    reason: str = Field(description="One plain-English sentence saying why this matters for the rating.")
    quote: str = Field(description="The auditor's words, copied exactly from one finding's text. At most 50 words.")
    audit_year: int = Field(description="The audit year of the finding the quote was copied from.")
    reference_number: str = Field(description="The reference number of the finding the quote was copied from.")


class RiskSheet(BaseModel):
    rating: Literal["low", "medium", "high", "no_basis"]
    summary: str = Field(description="Two or three sentences a grants manager can read in ten seconds.")
    reasons: list[Reason] = Field(description="Empty when the rating is no_basis.")
    next_checks: list[str] = Field(description="What a human reviewer should check next. Three items at most.")


SYSTEM = f"""You draft subrecipient risk sheets for a state grants monitor. Under 2 CFR 200.332 the \
state must assess each local government it passes federal money to, and the monitor uses single-audit \
results from the Federal Audit Clearinghouse to do it. Your draft goes to a human reviewer, who approves, \
changes or rejects it. Nothing you write is final.

Rate the locality with this rubric:

<rubric>
{RUBRIC}
</rubric>

The reviewer will check every quote against the source audit, so two things matter more than anything else:

- Use only the evidence in the message. You know nothing else about this locality. If the evidence has \
no findings, the rating is no_basis and the list of reasons is empty.
- Copy each quote character for character from the finding text, including the auditor's own wording, \
spelling and punctuation. Choose a short continuous passage; do not join separate passages with an \
ellipsis or tidy them up. Give the audit year and reference number of the finding you copied it from.

Each finding names the federal programs it touches and the Virginia state agency that passed the money \
down. A monitor works for one agency and is answerable for the findings on that agency's money, so say \
which agency each reason concerns. Some findings carry the locality's corrective action plan. That is \
the locality's own promise, not the auditor's judgment: use it to say what to verify, never quote it as \
evidence, and do not treat a plan as proof that a problem is fixed. An audit accepted more than nine \
months after its fiscal year ended was filed late, which is worth a check of its own.

Write for a busy grants manager: plain words, short sentences, no audit jargon you have not explained."""


def evidence_as_text(evidence):
    """Lay the evidence out for the model."""
    lines = [f"Locality: {evidence['name']}",
             f"Review window: audit years {evidence['first_year']} to {evidence['last_year']}", ""]
    if not evidence["audits"]:
        lines.append("No audit is on file for this locality in the review window.")
    for a in evidence["audits"]:
        lines.append(
            f"<audit year=\"{a['audit_year']}\" federal_spending=\"{a['total_amount_expended']}\" "
            f"fiscal_year_end=\"{a['fy_end_date']}\" accepted_by_clearinghouse=\"{a['fac_accepted_date']}\" "
            f"months_after_year_end=\"{months_between(a['fy_end_date'], a['fac_accepted_date'])}\" "
            f"opinion_on_financial_statements=\"{a['gaap_results']}\" "
            f"material_weakness_disclosed=\"{a['is_internal_control_material_weakness_disclosed']}\" "
            f"material_noncompliance_disclosed=\"{a['is_material_noncompliance_disclosed']}\" "
            f"going_concern=\"{a['is_going_concern_included']}\" low_risk_auditee=\"{a['is_low_risk_auditee']}\" />")
    lines.append("")
    if not evidence["findings"]:
        lines.append("No findings on federal awards are on file for this locality in the review window.")
    for f in evidence["findings"]:
        lines.append(
            f"<finding audit_year=\"{f['audit_year']}\" reference_number=\"{f['reference_number']}\" "
            f"material_weakness=\"{f['is_material_weakness']}\" significant_deficiency=\"{f['is_significant_deficiency']}\" "
            f"modified_opinion=\"{f['is_modified_opinion']}\" repeat_finding=\"{f['is_repeat_finding']}\" "
            f"questioned_costs=\"{f['is_questioned_costs']}\" federal_awards_affected=\"{f['awards']}\" "
            f"requirement=\"{'; '.join(requirement_names(f['type_requirement']))}\" "
            f"programs=\"{f['programs'] or 'not recorded'}\" "
            f"passed_through=\"{'; '.join(f['agencies']) or 'no Virginia state agency recognised'}\">")
        lines.append(f["finding_text"] or "(The FAC holds no text for this finding.)")
        if f["planned_action"]:
            lines.append("<locality_corrective_action_plan>")
            lines.append(f["planned_action"])
            lines.append("</locality_corrective_action_plan>")
        lines.append("</finding>")
    return "\n".join(lines)


def _usage(model, input_tokens, output_tokens, via):
    cost = input_tokens * PRICE_PER_MILLION["input"] / 1_000_000 + output_tokens * PRICE_PER_MILLION["output"] / 1_000_000
    return {"model": model, "via": via, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": round(cost, 5)}


def ask_model(evidence):
    """Send the evidence to Claude and get back a drafted risk sheet plus what the call used.

    There are two ways in. With ANTHROPIC_API_KEY set, call the Claude API, which is how a
    deployed version would run. Without one, go through Claude Code on this machine, which
    uses a Claude subscription and needs `claude auth login` to have been run once.
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        return _ask_api(evidence)
    return _ask_claude_code(evidence)


def _ask_api(evidence):
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment (.env)
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": evidence_as_text(evidence)}],
        output_format=RiskSheet,
        # If a safety classifier wrongly declines a request, let the API retry it on its recommended model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"No risk sheet for {evidence['name']}: the model stopped with '{response.stop_reason}'.")
    return response.parsed_output, _usage(response.model, response.usage.input_tokens,
                                          response.usage.output_tokens, "Claude API")


def _ask_claude_code(evidence):
    # Same system prompt, same evidence, same output shape as the API route. Tools, project
    # settings and MCP servers are switched off so the model sees nothing but the evidence.
    done = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", MODEL, "--system-prompt", SYSTEM,
         "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
         "--json-schema", json.dumps(RiskSheet.model_json_schema())],
        input=evidence_as_text(evidence), capture_output=True, text=True, encoding="utf-8",
        cwd=tempfile.gettempdir(), timeout=900)
    try:
        reply = json.loads(done.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Claude Code did not answer for {evidence['name']}: {done.stderr or done.stdout}") from None
    if reply.get("is_error") or not reply.get("structured_output"):
        raise RuntimeError(f"No risk sheet for {evidence['name']}: {reply.get('result')}")
    tokens = reply["usage"]
    input_tokens = (tokens["input_tokens"] + tokens.get("cache_creation_input_tokens", 0)
                    + tokens.get("cache_read_input_tokens", 0))
    model = next(iter(reply.get("modelUsage") or {}), MODEL)
    return RiskSheet.model_validate(reply["structured_output"]), _usage(model, input_tokens,
                                                                        tokens["output_tokens"], "Claude Code")


def no_basis_sheet(evidence):
    """The sheet for a locality with no findings. Written by code, so nothing can be invented."""
    if not evidence["audits"]:
        summary = (f"No single audit is on file for audit years {evidence['first_year']} to "
                   f"{evidence['last_year']}, so there is nothing to rate.")
        checks = ["Confirm whether the locality spent less than the single-audit threshold in federal funds, "
                  "or whether an audit is overdue."]
    else:
        notes = audit_flag_notes(evidence)
        summary = (f"No findings on federal awards are on file for audit years {evidence['first_year']} to "
                   f"{evidence['last_year']}, so there is no basis to rate. Real risk forms score that as the "
                   f"lowest audit risk, but it is not a clean bill of health.")
        if notes:
            summary += " " + " ".join(notes) + " The FAC holds no detail on these."
        checks = (["Read the audit reports flagged above; the detail is only in the report itself."] if notes else
                  ["Confirm the latest audit covers the programs this agency funds."])
    return RiskSheet(rating="no_basis", summary=summary, reasons=[], next_checks=checks)


def draft_sheet(evidence):
    """Draft one locality's risk sheet. The AI is only called when there is finding text to read."""
    if not any(f["finding_text"] for f in evidence["findings"]):
        return no_basis_sheet(evidence), _usage(None, 0, 0, None)
    return ask_model(evidence)


# ---------- 5. Checks and storage ----------

def _normal(text):
    """Ignore differences in spacing and in straight versus curly quotation marks."""
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def check_quotes(sheet, evidence):
    """Return a list of problems: quotes that are not in the finding they claim to come from."""
    problems = []
    texts = {(f["audit_year"], f["reference_number"]): _normal(f["finding_text"] or "") for f in evidence["findings"]}
    for reason in sheet.reasons:
        quote = _normal(reason.quote)
        cited = texts.get((reason.audit_year, reason.reference_number))
        if cited is not None and quote in cited:
            continue
        if any(quote in text for text in texts.values()):
            problem = "quote is real but attached to the wrong finding"
        else:
            problem = "quote not found in any finding text"
        problems.append({"audit_year": reason.audit_year, "reference_number": reason.reference_number,
                         "quote": reason.quote, "problem": problem})
    return problems


def save_sheet(evidence, sheet, usage, problems):
    """Store a draft. It stays a draft until a reviewer decides (see workflow.py)."""
    query(Path(__file__).with_name("schema_risk.sql").read_text())
    return query("""
        insert into risk_sheets (auditee_ein, auditee_name, rating, rule_rating, sheet, quote_problems,
                                 model, input_tokens, output_tokens, cost_usd)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning id
    """, (evidence["ein"], evidence["name"], sheet.rating, rule_rating(evidence), sheet.model_dump_json(),
          json.dumps(problems), usage["model"], usage["input_tokens"], usage["output_tokens"], usage["cost_usd"]))[0]["id"]


def record_decision(sheet_id, status, final_rating, reviewer, note):
    """Write the reviewer's decision on a draft."""
    query("""
        update risk_sheets
        set status = %s, final_rating = %s, reviewer = %s, reviewer_note = %s, reviewed_at = now()
        where id = %s
    """, (status, final_rating, reviewer, note, sheet_id))


def sources(evidence):
    """Links to the audits the evidence came from, newest first."""
    return [{"audit_year": a["audit_year"], "url": source_url(a["report_id"])} for a in evidence["audits"]]
