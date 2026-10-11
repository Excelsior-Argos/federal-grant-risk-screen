# Memo

**To:** State grants manager
**From:** [my name]
**Date:** October 10, 2026
**Subject:** A faster first pass on subrecipient risk, and how far to trust it

> **Draft.** The accuracy section reports checks a computer can make. I have not yet
> hand-rated the 30 test localities, so there is no figure for agreement with a human
> reviewer. Do not circulate this memo until that figure is in.

## Recommendation

Pilot this tool on one program's subrecipients as a first pass, with a monitor approving
every sheet. Do not use its ratings unreviewed. It reads the audits and drafts the
paperwork; the risk judgment stays with your staff.

## The problem

Under 2 CFR 200.332 we must assess every subrecipient's risk each year and follow up on
audit findings. The evidence is public: each locality's single audit is in the Federal
Audit Clearinghouse (FAC). Today a monitor opens each audit, reads the findings and
fills in a spreadsheet by hand.

For Virginia that is 369 local entities with an audit in the last three audit years
(2023 to 2025). Only 68 of them have any finding on a federal award. A monitor spends
most of the time confirming there is nothing to read, and the rest reading closely.

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
| AI rating matches the rubric applied mechanically to the audit's yes/no flags | 28 of 30 (93%) |
| Quotes found word for word in the cited finding | 116 of 116 |
| Localities with no findings correctly left unrated, with nothing invented | 10 of 10 |
| AI rating matches my own hand rating | **Not yet measured** |

In both mismatches the AI rated one level higher than the flags alone. Each time it
said so and quoted the auditor tracing the problem to turnover or vacancies in finance staff. The
rubric allows that adjustment, so these may be the AI reading something the flags
cannot show. I have not yet reviewed them myself.

The 93% needs care. The AI is given the same rubric and the same flags as the
mechanical check, so it shows the AI applies the rubric consistently. It does not show
the rubric is right, or that a monitor would agree.

## Cost

About **$0.06 per drafted sheet** (range $0.03 to $0.10), priced at the model's
published rates. That is an upper estimate; the test ran on a subscription and was not
billed per call. Only the 68 localities with findings need a draft, so a full annual
pass for Virginia is under $5 in AI charges. The database and the page run on free
tiers. The real cost is the monitor's review time, which this does not remove.

## Risks

- **No human benchmark yet.** Until I hand-rate the 30, the accuracy claim is limited
  to the three checks above.
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

1. I hand-rate the 30 localities and report agreement, with the cause of each miss.
2. A grants professional reviews the rubric.
3. Match the entity list to one program's subrecipients and pilot there.
