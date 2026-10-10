# Risk rating rubric

> **Status: draft written by Claude, not yet reviewed by me.** The rubric is mine to own.
> Until I have read it, changed what I disagree with and removed this note, every rating
> produced with it is provisional.

This rubric turns a locality's single-audit findings into one rating. It is used three
ways: by me when I hand-rate, by the AI when it drafts a risk sheet, and by a few lines
of code (`rule_rating` in `risk.py`) that apply steps 1 to 4 mechanically as a reference.

## What is looked at

The **review window** is the three most recent audit years in the database. Within it,
the **latest audit** is the locality's most recent audit year, and **earlier audits**
are the one or two years before that.

A **serious finding** is one the auditor marked as a material weakness, or one that led
to a modified opinion on compliance for a federal program.

## The rating

Apply the first step that fits.

1. **No basis to rate.** There are no findings on federal awards anywhere in the review
   window, or no audit on file in the window at all. Do not rate. This is not a clean
   bill of health: say so, and say whether any audit in the window disclosed a
   financial-statement material weakness, material noncompliance or a going-concern
   doubt, because those appear in the FAC without any finding text.

2. **High.** The latest audit has any of:
   - a serious finding that is also a repeat finding;
   - a serious finding that also has questioned costs;
   - a serious finding, when an earlier audit in the window also had a serious finding;
   - a going-concern doubt.

3. **Medium.** Not high, and the latest audit has any of:
   - a serious finding;
   - a repeat finding;
   - a finding with questioned costs;
   - three or more findings.

4. **Low.** There are findings in the window, but nothing above applies. This covers
   findings only in earlier audits, and a latest audit with one or two findings that are
   significant deficiencies or lesser, not repeated, with no questioned costs.

## Judgment from the text

Steps 1 to 4 use only the yes/no flags. The auditor's written text can justify moving a
high, medium or low rating **one level**, in either direction. This never applies to
"no basis to rate".

- **Up one level** when the text shows the problem is systemic: it spans several
  programs, or the auditor traces it to missing staff, missing reconciliations or absent
  controls across the finance function.
- **Down one level** when the text shows the problem was isolated and already corrected
  before the audit was issued.

Any adjustment must be stated as its own reason, with the words that justify it quoted.

## What a risk sheet must contain

- The rating.
- Each reason, with the auditor's own words quoted exactly and the audit year and
  finding number they came from.
- What a reviewer should check next.

Nothing in a risk sheet may come from outside the audit data. If the data does not say
it, the sheet does not say it.
