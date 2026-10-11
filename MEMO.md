# Memo

**To:** State grants manager
**From:** [my name]
**Date:** October 11, 2026
**Subject:** A faster first pass on subrecipient risk, and how far to trust it

## Recommendation

Pilot this tool on one program's subrecipients as a first pass, with a monitor approving
every sheet. Do not use its ratings unreviewed. It reads the audits and drafts the
paperwork; the risk judgment stays with your staff.

## The problem

Under 2 CFR 200.332(c), an agency that passes federal money to subrecipients must
evaluate each one's risk of noncompliance. The results of previous audits are one of
four things the rule says to consider. The rule sets no schedule. Agencies set their
own, and the Department of Criminal Justice Services, for one, publishes a policy of
assessing before each award period or annually.

Keeping up is hard. The Commonwealth's fiscal year 2025 single audit found that the
Department of Social Services had not completed 15 of 316 locality risk assessments,
after 50 of 324 the year before (finding 2025-017, repeated every year since fiscal
year 2021). Its corrective action plan describes tracking the work in spreadsheets.

The audit evidence itself is public: each locality's single audit is in the Federal
Audit Clearinghouse (FAC). In that data, 369 Virginia local entities have an audit for
2023 to 2025 and only 68 have any finding on a federal award. One agency's
subrecipients are a subset of these.

## What I built

1. **A clean copy of the data.** 2,669 audits of 449 Virginia local entities, 2016 to
   2025, loaded from the FAC on October 10, 2026, with 598 findings.
2. **A lookup page.** Pick a locality and see each finding, whether it was a material
   weakness, a repeat or had questioned costs, the auditor's text, and a link to the
   source audit.
3. **A drafted risk sheet per locality.** An AI model (Claude) reads the last three
   years of findings against a written rubric and drafts a low, medium or high rating,
   the reasons with the auditor's words quoted, and what to check next.
4. **A required human decision.** Each draft waits for a monitor to approve it, change
   the rating or reject it. Only approved sheets are shown.

Two design choices matter for trust:

- **No findings, no AI.** For the 301 entities with no findings in the window, the
  sheet says "no basis to rate" and is written by fixed code. The AI is never asked, so
  it cannot invent a concern.
- **Every quote is checked.** Code looks for each quoted passage, word for word, in the
  finding it cites, and flags any it cannot find.

## Accuracy so far

I tested 30 localities, 10 each that a mechanical reading of the rubric rates low,
medium and high.

| Check | Result |
|---|---|
| AI rating matches my rating | 29 of 30 (97%) |
| AI rating matches the rubric applied mechanically to the audit's yes/no flags | 28 of 30 (93%) |
| AI rating matches a second, separate AI pass | 27 of 30 (90%) |
| Quotes found word for word in the cited finding | 116 of 116 |
| Localities with no findings correctly left unrated, with nothing invented | 10 of 10 |

How I rated: a second AI pass drafted a rating for each locality, I reviewed all 30 and
I changed four. I saw AI ratings before I judged, so this is a review, not a blind
rating, and it likely overstates agreement.

Every disagreement, in all three comparisons, came from one sentence in the rubric: the
text may move a rating up one level when the problem is "systemic".

- **Where I disagree with the tool.** One locality. The tool moved it from low to
  medium because the auditor tied two late filings to vacancies in the finance office.
  I rate it low: the filings were late and nothing more.
- **Where the tool went above the flags and I agree.** One locality, moved from medium
  to high, with three material weaknesses in its latest audit.
- **Where the second AI pass went higher than the tool.** Three localities. I sided
  with the tool each time: the text did not show a systemic problem, and in one case
  the locality was already fixing it.

So the yes/no flags decide most ratings and the AI follows them. What is unsettled is
what counts as systemic, and that is a question about the rubric, not about the model.

These figures need care. The AI is given the same rubric and the same flags as the
mechanical check, and my own check was a review. Together they show the AI applies the
rubric consistently. They do not show the rubric is right, or that an experienced
monitor would agree.

## Cost

About **$0.06 per drafted sheet** (range $0.03 to $0.10), priced at the model's
published rates. That is an upper estimate; the test ran on a subscription and was not
billed per call. Only the 68 localities with findings need a draft, so a full annual
pass for Virginia is under $5 in AI charges. The database and the page run on free
tiers. The real cost is the monitor's review time, which this does not remove.

## Risks

- **The human check was not blind.** I reviewed ratings an AI had drafted. A stronger
  test is a grants monitor rating the 30 without seeing any AI output.
- **It covers one risk factor of four.** The rule also names prior experience with
  similar awards, new staff or systems, and federal monitoring results. The tool reads
  audit results only, so it feeds a risk assessment and does not replace one.
- **The rubric is a draft.** It has not been reviewed by a grants professional. A wrong
  rubric applied consistently is still wrong.
- **The FAC does not hold everything.** Its findings table covers federal awards only.
  70 entities with no findings there still had an audit disclose a material weakness in
  their financial statements. The tool says so on the sheet and sends the monitor to
  the report, but it cannot read what is not in the data.
- **The entity list is wider than cities and counties.** It includes school boards,
  housing authorities and a few out-of-state entities filed with a Virginia address.
  It needs matching to our actual subrecipient list.
- **A verified quote is not a verified conclusion.** The check proves the words are the
  auditor's. It does not prove the AI's reading of them.
- **Small test.** Thirty localities, one state, one model version. Any change to the
  model or the rubric means running the test again.

## Next steps

1. Tighten the rubric's definition of "systemic", since every disagreement came from it.
2. Have a grants professional review the rubric and rate the 30 localities blind.
3. Match the entity list to one program's subrecipients and pilot there.
