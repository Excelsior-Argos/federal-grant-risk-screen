"""Phase 2 proof: compare the AI's ratings with mine, with a second AI's and with the rubric applied by code.

Run in this order:
  .venv/Scripts/python evaluate.py sample   pick 30 localities and write eval/ratings.csv
  (fill in the my_rating column with low, medium or high)
  .venv/Scripts/python evaluate.py run      draft the 30 sheets and run the no-findings test
  .venv/Scripts/python evaluate.py report   write eval/REPORT.md and eval/misses.csv
"""
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

from common import query
from risk import MODEL, ask_model, check_quotes, draft_sheet, gather_evidence, rule_rating

EVAL = Path(__file__).with_name("eval")
RATED = EVAL / "ratings.csv"
RESULTS = EVAL / "results.json"
RATINGS = ["low", "medium", "high", "no_basis"]
SAMPLE_SIZE = 30
PROBE_SIZE = 10


def window():
    last = query("select max(audit_year) as year from audits")[0]["year"]
    return last - 2, last


def sample():
    """Pick the localities to rate by hand: an even spread across the rubric's low, medium and high."""
    if RATED.exists():
        sys.exit(f"{RATED} already exists. Delete it yourself if you really want a new sample.")
    first, last = window()
    candidates = query("""
        select distinct a.auditee_ein
        from audits a
        join finding_texts t using (report_id)
        where a.audit_year between %s and %s and t.finding_text is not null
        order by 1
    """, (first, last))
    print(f"{len(candidates)} localities have finding text in {first} to {last}. Rating each by rule ...")
    by_rating = {"low": [], "medium": [], "high": []}
    for row in candidates:
        evidence = gather_evidence(row["auditee_ein"])
        by_rating[rule_rating(evidence)].append((evidence["ein"], evidence["name"]))
    print("  by rule:", {rating: len(rows) for rating, rows in by_rating.items()})

    # Take turns drawing from each group so no rating dominates. The seed makes the draw repeatable.
    rng = random.Random(2026)
    for rows in by_rating.values():
        rng.shuffle(rows)
    chosen = []
    while len(chosen) < SAMPLE_SIZE and any(by_rating.values()):
        for rating in by_rating:
            if by_rating[rating] and len(chosen) < SAMPLE_SIZE:
                chosen.append(by_rating[rating].pop())
    chosen.sort(key=lambda pair: pair[1].lower())

    EVAL.mkdir(exist_ok=True)
    with RATED.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["ein", "name", "second_ai_rating", "second_ai_notes", "my_rating", "my_note"])
        writer.writerows([ein, name, "", "", "", ""] for ein, name in chosen)
    print(f"Wrote {len(chosen)} localities to {RATED}. Fill in my_rating with low, medium or high.")


def read_csv(path):
    """Read a CSV file as a list of rows. Excel saves in an older Windows encoding, so try that second."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with path.open(encoding=encoding, newline="") as file:
                return list(csv.DictReader(file))
        except UnicodeDecodeError:
            continue
    sys.exit(f"Cannot read {path}.")


def run():
    """Draft a sheet for each sampled locality, then test localities that have no findings."""
    results = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {"sheets": {}, "probe": {}}

    for row in read_csv(RATED):
        if row["ein"] in results["sheets"]:
            continue  # already drafted on an earlier run; do not pay for it twice
        evidence = gather_evidence(row["ein"])
        sheet, usage = draft_sheet(evidence)
        results["sheets"][row["ein"]] = {
            "name": evidence["name"], "rule_rating": rule_rating(evidence), "ai_rating": sheet.rating,
            "sheet": sheet.model_dump(), "quote_problems": check_quotes(sheet, evidence), "usage": usage,
        }
        RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"  {evidence['name']}: AI says {sheet.rating}, rule says {rule_rating(evidence)}")

    # The no-findings test. draft_sheet() never calls the AI for these localities, so here we
    # call the AI directly to prove the prompt alone also refuses to invent a rating.
    first, last = window()
    clean = query("""
        select a.auditee_ein, bool_or(a.is_internal_control_material_weakness_disclosed) as flagged
        from audits a
        where a.audit_year between %s and %s
        group by a.auditee_ein
        having not exists (
            select 1 from findings f join audits b using (report_id)
            where b.auditee_ein = a.auditee_ein and b.audit_year between %s and %s)
        order by 1
    """, (first, last, first, last))
    rng = random.Random(2026)
    flagged = [r["auditee_ein"] for r in clean if r["flagged"]]
    unflagged = [r["auditee_ein"] for r in clean if not r["flagged"]]
    # Half the test uses audits that flag a material weakness: the hardest case not to embellish.
    probe = rng.sample(flagged, PROBE_SIZE // 2) + rng.sample(unflagged, PROBE_SIZE - PROBE_SIZE // 2)
    for ein in probe:
        if ein in results["probe"]:
            continue
        evidence = gather_evidence(ein)
        sheet, usage = ask_model(evidence)
        results["probe"][ein] = {"name": evidence["name"], "flagged": ein in flagged, "ai_rating": sheet.rating,
                                 "reasons": len(sheet.reasons), "summary": sheet.summary, "usage": usage}
        RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"  no-findings test, {evidence['name']}: AI says {sheet.rating} with {len(sheet.reasons)} reasons")


def agreement(pairs):
    """pairs is a list of (expected, ai). Returns the count that match and a small table of the rest."""
    matches = sum(1 for expected, ai in pairs if expected == ai)
    table = Counter(pairs)
    lines = ["| Expected | AI low | AI medium | AI high | AI no basis |", "|---|---|---|---|---|"]
    for expected in RATINGS:
        if any(e == expected for e, _ in pairs):
            lines.append(f"| {expected} | " + " | ".join(str(table[(expected, ai)]) for ai in RATINGS) + " |")
    return matches, lines


def report():
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    rows = [row for row in read_csv(RATED) if row["ein"] in results["sheets"]]
    sheets = results["sheets"]
    out = ["# Evaluation report", "",
           f"Model: `{MODEL}`. {len(sheets)} localities drafted. Generated by `evaluate.py report`.", ""]
    misses = []

    def filled(column):
        return {row["ein"]: row[column].strip().lower() for row in rows if row[column].strip().lower() in RATINGS}
    mine, second_ai = filled("my_rating"), filled("second_ai_rating")

    out += ["## AI against my ratings", ""]
    if mine:
        pairs = [(mine[ein], sheets[ein]["ai_rating"]) for ein in mine]
        matches, table = agreement(pairs)
        changed = sum(1 for ein in mine if ein in second_ai and mine[ein] != second_ai[ein])
        out += [f"Agreement: **{matches} of {len(pairs)}** ({matches / len(pairs):.0%}).", "",
                "How I rated: a separate AI session drafted a rating for each locality, I reviewed all of them, and "
                f"I changed {changed}. I saw AI ratings before I judged, so this is a review, not a blind rating, "
                "and it is likely to overstate agreement.", ""] + table + [""]
        misses += [(ein, "my rating", mine[ein]) for ein in mine if mine[ein] != sheets[ein]["ai_rating"]]
    else:
        out += ["Not available: the `my_rating` column in `eval/ratings.csv` is empty.", ""]

    out += ["## AI against a second AI rater", "",
            "The `second_ai_rating` column was filled in by a separate AI session using the same rubric. That "
            "session may have had access to the first AI's drafts, so this is a weak check: two AI passes agreeing "
            "is not evidence that either is right.", ""]
    if second_ai:
        pairs = [(second_ai[ein], sheets[ein]["ai_rating"]) for ein in second_ai]
        matches, table = agreement(pairs)
        out += [f"Agreement: **{matches} of {len(pairs)}** ({matches / len(pairs):.0%}).", ""] + table + [""]
        misses += [(ein, "second AI rater", second_ai[ein]) for ein in second_ai if second_ai[ein] != sheets[ein]["ai_rating"]]
    else:
        out += ["Not available: the `second_ai_rating` column is empty.", ""]

    out += ["## AI against the rubric applied by code", "",
            "The reference here is `rule_rating`: steps 1 to 4 of the rubric applied to the yes/no flags. "
            "It cannot read the text, so a disagreement is not automatically an AI error.", ""]
    pairs = [(s["rule_rating"], s["ai_rating"]) for s in sheets.values()]
    matches, table = agreement(pairs)
    out += [f"Agreement: **{matches} of {len(pairs)}** ({matches / len(pairs):.0%}).", ""] + table + [""]
    misses += [(ein, "rubric by code", s["rule_rating"]) for ein, s in sheets.items() if s["rule_rating"] != s["ai_rating"]]

    quotes = sum(len(s["sheet"]["reasons"]) for s in sheets.values())
    problems = [(s["name"], p) for s in sheets.values() for p in s["quote_problems"]]
    out += ["## Quotes", "",
            f"{quotes} quotes drafted. **{quotes - len(problems)} of {quotes}** were found word for word in the "
            "finding they cite.", ""]
    out += [f"- {name}, finding {p['reference_number']} ({p['audit_year']}): {p['problem']}. Quote: \"{p['quote']}\""
            for name, p in problems] + ([""] if problems else [])

    probe = results["probe"]
    passed = [p for p in probe.values() if p["ai_rating"] == "no_basis" and p["reasons"] == 0]
    out += ["## Localities with no findings", "",
            f"{len(probe)} localities with no findings in the window were sent to the AI directly. "
            f"**{len(passed)} of {len(probe)}** came back as no basis to rate with no reasons invented. "
            f"{sum(1 for p in probe.values() if p['flagged'])} of them had an audit that flags a material weakness.", ""]
    out += [f"- FAILED: {p['name']} was rated {p['ai_rating']} with {p['reasons']} reasons."
            for p in probe.values() if p not in passed] + ([""] if len(passed) < len(probe) else [])

    calls = [s["usage"] for s in sheets.values() if s["usage"]["model"]]
    if calls:
        cost = sum(u["cost_usd"] for u in calls)
        out += ["## Cost", "",
                f"{len(calls)} AI calls for the sampled localities: ${cost:.2f} in total, "
                f"**${cost / len(calls):.3f} per locality** on average "
                f"({sum(u['input_tokens'] for u in calls) // len(calls):,} tokens in, "
                f"{sum(u['output_tokens'] for u in calls) // len(calls):,} out).", ""]
        if any(u["via"] == "Claude Code" for u in calls):
            out += ["These calls went through Claude Code on a Claude subscription, so nothing was billed per call. "
                    "The dollar figure is what the same tokens would cost at Claude API list prices, and the token "
                    "counts include Claude Code's own overhead, so treat it as an upper estimate.", ""]

    (EVAL / "REPORT.md").write_text("\n".join(out), encoding="utf-8")
    # Keep any causes already written, so running the report again never erases them.
    misses_file = EVAL / "misses.csv"
    causes = {}
    if misses_file.exists():
        causes = {(row["ein"], row["compared_with"]): row["cause"] for row in read_csv(misses_file)}
    with misses_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["ein", "name", "compared_with", "expected", "ai_rating", "ai_summary", "cause"])
        for ein, compared_with, expected in misses:
            s = sheets[ein]
            writer.writerow([ein, s["name"], compared_with, expected, s["ai_rating"], s["sheet"]["summary"],
                             causes.get((ein, compared_with), "")])
    print("\n".join(out))
    print(f"{len(misses)} disagreements written to eval/misses.csv. The cause column is for me to fill in.")


if __name__ == "__main__":
    commands = {"sample": sample, "run": run, "report": report}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
