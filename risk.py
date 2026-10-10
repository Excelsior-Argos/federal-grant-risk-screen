"""The AI layer: gather a locality's evidence, draft a risk sheet, check it, save it.

Used by evaluate.py (Phase 2) and workflow.py (Phase 3). Nothing here approves anything.
"""
import json
import re
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from common import query, requirement_names, source_url

MODEL = "claude-opus-5-5"
PRICE_PER_MILLION = {"input": 4.00, "output": 20.00}  # US dollars, Claude Opus 5.5 list price
WINDOW_YEARS = 3
RUBRIC = Path(__file__).with_name("RUBRIC.md").read_text(encoding="utf-8")


# ---------- 1. Evidence: everything the rating is allowed to rest on ----------

def gather_evidence(ein):
    """Collect one locality's audits and findings for the review window."""
    last_year = query("select max(audit_year) as year from audits")[0]["year"]
    first_year = last_year - WINDOW_YEARS + 1

    audits = query("""
        select report_id, auditee_name, audit_year, fy_end_date, total_amount_expended, gaap_results,
               is_going_concern_included, is_internal_control_material_weakness_disclosed,
               is_material_noncompliance_disclosed, is_low_risk_auditee
        from audits
        where auditee_ein = %s and audit_year between %s and %s
        order by audit_year desc, fac_accepted_date desc
    """, (ein, first_year, last_year))

    # One row per finding. A finding can touch several awards; a flag counts if it is set on any of them.
    findings = query("""
        select a.audit_year, f.report_id, f.reference_number,
               count(*) as awards,
               string_agg(distinct f.type_requirement, '') as type_requirement,
               bool_or(f.is_material_weakness) as is_material_weakness,
               bool_or(f.is_significant_deficiency) as is_significant_deficiency,
               bool_or(f.is_modified_opinion) as is_modified_opinion,
               bool_or(f.is_repeat_finding) as is_repeat_finding,
               bool_or(f.is_questioned_costs) as is_questioned_costs,
               t.finding_text
        from findings f
        join audits a using (report_id)
        left join finding_texts t using (report_id, reference_number)
        where a.auditee_ein = %s and a.audit_year between %s and %s
        group by a.audit_year, f.report_id, f.reference_number, t.finding_text
        order by a.audit_year desc, f.reference_number
    """, (ein, first_year, last_year))

    name = query("""
        select auditee_name from audits where auditee_ein = %s
        order by audit_year desc, fac_accepted_date desc limit 1
    """, (ein,))[0]["auditee_name"]
    return {"ein": ein, "name": name, "first_year": first_year, "last_year": last_year,
            "audits": audits, "findings": findings}


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


# ---------- 2. The rubric's steps 1 to 4, applied by code as a reference ----------

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


# ---------- 3. The risk sheet and the AI call that drafts it ----------

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
            f"requirement=\"{'; '.join(requirement_names(f['type_requirement']))}\">")
        lines.append(f["finding_text"] or "(The FAC holds no text for this finding.)")
        lines.append("</finding>")
    return "\n".join(lines)


def ask_model(evidence):
    """Send the evidence to Claude and get back a drafted risk sheet plus what the call cost."""
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
    usage = {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": round(response.usage.input_tokens * PRICE_PER_MILLION["input"] / 1_000_000
                          + response.usage.output_tokens * PRICE_PER_MILLION["output"] / 1_000_000, 5),
    }
    return response.parsed_output, usage


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
                   f"{evidence['last_year']}, so there is no basis to rate. This is not a clean bill of health.")
        if notes:
            summary += " " + " ".join(notes) + " The FAC holds no detail on these."
        checks = (["Read the audit reports flagged above; the detail is only in the report itself."] if notes else
                  ["Confirm the latest audit covers the programs this agency funds."])
    return RiskSheet(rating="no_basis", summary=summary, reasons=[], next_checks=checks)


def draft_sheet(evidence):
    """Draft one locality's risk sheet. The AI is only called when there is finding text to read."""
    if not any(f["finding_text"] for f in evidence["findings"]):
        return no_basis_sheet(evidence), {"model": None, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0}
    return ask_model(evidence)


# ---------- 4. Checks and storage ----------

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
