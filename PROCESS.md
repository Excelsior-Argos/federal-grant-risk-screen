# The real process this tool supports

How a state agency actually assesses the risk of a local government it passes federal
money to, what it does with that locality's single audit, and where this tool fits.
Researched on 2026-10-11 from the rule text, the auditors' test plan, and the documents
Virginia agencies publish. Each claim names its source at the end.

The research found the real blank forms and the written procedures. It did not find any
completed assessment: those are internal agency records.

## What the rule requires

| Rule | What the agency must do |
|---|---|
| 2 CFR 200.332(c) | Evaluate each subrecipient's risk of fraud and noncompliance. Four things to consider: experience with similar awards; results of previous audits, including whether the program was audited as a major program; new staff or systems; federal monitoring results. No schedule is set. |
| 2 CFR 200.332(g) | Verify that each subrecipient that must have a single audit had one. |
| 2 CFR 200.501 | A single audit is required at $750,000 of federal spending, or $1,000,000 for fiscal years beginning on or after 1 October 2024. |
| 2 CFR 200.512(a) | The audit is due nine months after the fiscal year ends, or 30 days after the auditor's report if that is sooner. |
| 2 CFR 200.332(e)(2) to (4) | Follow up on findings related to the agency's own subaward. The agency is not responsible for findings on other agencies' money. |
| 2 CFR 200.521 | Issue a written management decision on each of those findings within six months of the FAC accepting the audit: whether the finding is sustained, why, what the locality must do, and by when. |

The federal auditors' test plan (OMB Compliance Supplement, Part 3, section M) has them
pick a sample of subrecipients and check that the agency verified each audit, and pick a
sample of audits with findings and check each management decision. So an agency must be
able to show a documented risk evaluation, proof it checked the audit, and a dated
decision for every finding on its own money.

## How Virginia agencies do it

| Agency | What it publishes | How the audit is used |
|---|---|---|
| Emergency Management (VDEM) | A full scored form in its EM Grants system, repeated yearly. | Two rows. "Audit performed": 5 points if an audit was required and not done. "Single audit results": 5 points for a finding on another agency's program, 35 for a finding on a VDEM grant, 40 for both. High risk starts at 35. Severity is not scored. |
| Criminal Justice Services (DCJS) | Policy 5-1:003 (August 2025) and a risk assessment spreadsheet. Assess within 30 days of an award, then yearly. | Staff verify in the FAC that the audit was submitted and "review audit findings for elements that may require additional monitoring conditions". The spreadsheet scores whether an audit exists and the auditor's opinion, with a free-text box of documented concerns that can raise the level. |
| Social Services (VDSS) | Nothing public. The state auditors' findings describe it. | Program consultants complete a risk assessment per locality each year (316 in fiscal year 2025, 15 not completed). High and medium ratings need a monitoring review or a written reason. Audit findings are tracked in a central spreadsheet. |
| Transportation (VDOT) | A yearly letter and response form to every locality that got over $100,000, and a review procedure. | The locality confirms whether a single audit was required and sends it in. VDOT reads the auditor's reports, reconciles the locality's federal spending schedule to its own payments within 3 percent, and writes back. |
| Health (VDH) | A 2014 policy the state auditors call outdated; one program guide. | The program downloads the latest audit from the FAC, checks for findings related to its subawards, and asks for the corrective action plan. |
| Housing and Community Development | Four risk levels, form not published. | Every funded body uploads its audit within nine months. No accepted audit, no reimbursement. |
| Behavioral Health (DBHDS) | Contract language only. | Boards send their audit with findings and corrective action plans within 30 days. |
| Rail and Public Transportation | A yes/no review checklist. | First two items: "Single Audit received for each year" and "No Single Audit findings were identified". |
| Education (VDOE) | A list of ten factors, no points. | "History of audit findings" is one factor. |

No agency publishes a management decision letter template, and the state auditors have
cited Social Services and Health for not issuing them.

## What the real forms ask about the audit

Most common first, across the Virginia forms:

1. Was a single audit required?
2. Was it done and filed?
3. Were there any findings?
4. Were the findings on this agency's own program? This is the main question.
5. Is there a corrective action plan, and is it adequate?
6. Were there questioned costs?
7. Does the locality's federal spending schedule match the agency's payments? (VDOT only.)

Rarely or never scored on the Virginia forms: material weakness against significant
deficiency, repeat findings, and more than one year of history. Forms from other states
do score them. Texas's education agency gives points per material weakness and per
repeat finding, and North Carolina's county matrix separates findings with corrective
action from significant or unresolved ones.

## Where this tool fits

| Step in the real process | In this tool | Not covered |
|---|---|---|
| List the agency's subrecipients | "View as a state agency" lists every local entity whose audit names that agency as the source of money. | The agency's own award list is the true list. The FAC names are typed freely by each locality's auditor; 88 percent were matched to an agency. |
| Verify the audit is on file | Shown for each locality, with the date the FAC accepted it. | Whether an audit was required when none is on file. |
| Check it was on time | Months from fiscal year end to acceptance, late if over nine. | The 30-day rule, which needs the auditor's report date. |
| Read the findings | Finding text, flags and the locality's corrective action plan. | Findings on the financial statements only, which the FAC flags without text. |
| Separate findings on the agency's money | Each finding is tagged with its program and the agency that passed the money down. | |
| Fill in the audit rows of the risk form | Worked out by code for three real forms: VDEM, DCJS and North Carolina's. | Every other row: late reports, site visits, staff turnover, award size. |
| Write up documented concerns | The AI drafts them with the auditor's words quoted, and a person approves. | |
| Issue a management decision | The six-month due date is shown. | The decision itself, and whether one was issued. |
| Check corrective action was taken | The plan is shown. | Whether it was carried out. |
| Reconcile spending to payments | | Needs the agency's payment records. |

## What changed in the tool because of this

Before, the tool rated a locality as a whole from the severity of its findings. The
real forms mostly ask a different question: is the audit on file, on time, and are the
findings on my money. So the tool now loads each audit's federal programs, the agency
each was passed through and the corrective action plans, shows an agency its own
subrecipients, and fills in the audit rows of three real forms by code. The severity
rating from `RUBRIC.md` is kept as the draft of a monitor's documented concerns. It is
not what a Virginia form scores.

## Sources

- 2 CFR 200.332, 200.501, 200.512 and 200.521: <https://www.ecfr.gov/current/title-2/part-200>
- OMB Compliance Supplement 2025, Part 3, section M: <https://www.whitehouse.gov/omb/information-resources/guidance/compliance-supplement>
- VDEM briefing slides and job aid (September 2024): <https://www.vdem.virginia.gov/wp-content/uploads/2024/09/subrecipient-briefing-slide-updated-language.pdf>
- DCJS policy 5-1:003, effective 15 August 2025, and risk assessment spreadsheet: <https://www.dcjs.virginia.gov/node/5262>
- DCJS Grant Monitoring Policy and Procedures (2019): <https://www.dcjs.virginia.gov/sites/dcjs.virginia.gov/files/publications/victims/dcjsmonitoringpolicy.pdf>
- Commonwealth of Virginia single audit, fiscal year 2025, findings 2025-014, 2025-017 and 2025-018, and the corrective action plan: <https://app.fac.gov/dissemination/summary/2025-06-GSAFAC-0000388108>
- VDOT subrecipient letter, response form and review training: <https://www.vdot.virginia.gov/doing-business/for-localities/local-assistance/locally-administered-projects/>
- VDH Ryan White Part B monitoring guide: <https://www.vdh.virginia.gov/content/uploads/sites/10/2017/10/WHAT-TO-EXPECT-FROM-A-MONITORING-SITE-VISIT.pdf>
- DHCD weatherization operations manual: <https://www.dhcd.virginia.gov/sites/default/files/DocX/weatherization/operations-manual/wap-operations-manual.pdf>
- DBHDS Exhibit F, federal grant compliance requirements: <https://dbhds.virginia.gov/wp-content/uploads/2026/03/07.-P1636.3-Exhibit-F-AMD3-FY26-27-Federal-Grant-Requirements7.1.25.pdf>
- DRPT State Management Plan (January 2024): <https://drpt.virginia.gov/wp-content/uploads/2024/02/2024-State-Management-Plan-1.pdf>
- VDOE IDEA fiscal monitoring: <https://www.doe.virginia.gov/programs-services/special-education/grants-funding/idea-fiscal-monitoring>
- North Carolina DHHS Risk Evaluation Matrix, County Subrecipient (September 2024): <https://ncdhhs.gov/sa-risk-evaluation-matrix-county-subrecipient-appendix-2-92024/open>
- Texas Education Agency risk assessment indicators, 2023-24: <https://tea.texas.gov/finance-and-grants/grants/grants-administration/23-24-gca-risk-assessment-process-103123.pdf>
- DOJ Office of Justice Programs sample subrecipient risk assessment tool: <https://www.ojp.gov/sites/g/files/xyckuh241/files/media/document/Sample_Subrecipient_Monitoring_Risk_Assessment_Tool.pdf>

How this was researched: I did it with an AI assistant (Claude). It read the rule text,
the DCJS documents, the North Carolina matrix and the Virginia single audit directly,
and summarised the other agency documents from the links above. I have not yet read
each source myself, and I should before I rely on a detail in front of a client.
