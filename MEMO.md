# Memo

**To:** State grants manager
**From:** [my name]
**Date:** October 11, 2026
**Subject:** A faster first pass on subrecipient audit review, and how far to trust it

## Recommendation

Pilot this tool in one agency as the first pass on subrecipient audits, with a monitor
approving everything it drafts. It does the lookups and the reading. The judgment stays
with your staff.

## The problem

Under 2 CFR 200.332 an agency that passes federal money to localities must evaluate
each one's risk, verify it was audited, and issue a written decision within six months
on every audit finding that touches the agency's own money.

Keeping up is hard. The Commonwealth's fiscal year 2025 single audit found that Social
Services had not completed 15 of 316 locality risk assessments, after 50 of 324 the
year before (finding 2025-017, repeated every year since 2021). Its corrective action
plan describes tracking the work in spreadsheets. The state auditors have also cited
agencies for not issuing management decisions.

The audits themselves are public, in the Federal Audit Clearinghouse (FAC).

## What a real risk form asks

The forms Virginia agencies publish ask about the audit in much the same way: is it on
file, was it on time, and are any findings on this agency's money. The
Emergency Management form gives 35 points, its high-risk line, for one finding on its
own grant and 5 for a finding on another agency's. How severe the finding is does not
change the score. The details and sources are in `PROCESS.md`.

## What I built

1. **A clean copy of the data.** 2,669 audits of 449 Virginia local entities, 2016 to
   2025, with each audit's federal programs, which agency passed the money down, the
   findings and the locality's corrective action plans. Loaded October 11, 2026.
2. **An agency's worklist.** Pick an agency and see its subrecipients. For Criminal
   Justice Services, 2023 to 2025: 188 subrecipients, 52 whose latest audit was filed
   late, 42 whose next audit is overdue, and 7 with findings on its money.
3. **The audit rows of the risk form, filled in.** For each locality, fixed code works
   out the audit rows of three real forms and the date the management decision is due.
   No AI is involved.
4. **A drafted write-up.** For localities with findings, an AI model (Claude) drafts a
   severity rating, the reasons with the auditor's words quoted, and what to check
   next. This is the text for a form's "documented concerns" box.
5. **A required human decision.** Each draft waits for a monitor to approve it, change
   it or reject it. Only approved drafts are shown.

Two choices matter for trust. Where there are no findings the AI is never asked, so it
cannot invent a concern. And code checks every quote, word for word, against the
finding it cites.

## What the test showed

I tested the AI on 30 localities, 10 each that a mechanical reading of my rubric rates
low, medium and high.

| Check | Result |
|---|---|
| AI rating matches my rating | 29 of 30 |
| AI rating matches the rubric applied mechanically | 28 of 30 |
| AI rating matches a second, separate AI pass | 27 of 30 |
| Same rating each time the whole test was run (three runs) | 30 of 30 |
| Quotes found word for word in the cited finding | 110 of 110 |
| Localities with no findings left unrated, nothing invented | 10 of 10 |

How I rated: a second AI pass drafted a rating for each locality, I reviewed all 30 and
changed four. I had seen AI ratings first, so this was a review, not a blind rating,
and it likely overstates agreement.

Every disagreement came from one sentence in my rubric, on when a problem counts as
"systemic". The yes/no flags in the data settle most ratings, and plain code agrees
with the AI on 28 of 30. So the AI earns its place in the reading and the write-up,
not in the rating.

## Cost

About **$0.08 per drafted write-up** (range $0.03 to $0.17) at the model's published
rates. That is an upper estimate; the test ran on a subscription. Only the 68
localities with findings need a draft, so a yearly pass for Virginia is about $5. The
database and page run on free tiers. The real cost is the monitor's review time.

## Risks

- **My reading of the forms is unchecked.** I applied each form's wording to FAC data.
  No agency has confirmed I read its form the way its monitors do.
- **The subrecipient list comes from the audits, not from the agency.** Auditors type
  the agency's name freely; 88 percent of entries were matched. The agency's own award
  list is the true list.
- **The human check was not blind,** and my rubric has not been reviewed by a grants
  professional.
- **The FAC does not hold everything.** It cannot say whether a management decision
  was issued or a corrective action carried out, and 70 entities had an audit disclose
  a financial-statement weakness with no detail on file.
- **It covers the audit rows only.** Late reports, site visits and staff turnover need
  the agency's own records.
- **A verified quote is not a verified conclusion.**
- **Small test.** Thirty localities, one state, one model version.

## Next steps

1. Have a grants monitor check the form rows and rate the 30 localities blind.
2. Replace the matched names with one agency's real subrecipient list and pilot there.
3. Add a drafted management decision letter for each finding on the agency's money.
