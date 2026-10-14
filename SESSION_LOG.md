# Session log

## 2026-10-10: Session 1, look at the data first

**Done**
- Created the project folder, virtual environment (Python 3.14.2) and a local git repo.
- Wrote `explore_fac.py`, which prints one real row from `general`, `findings` and
  `findings_text`. Ran it with the public demo key; it works.
- Confirmed both things I had been told: state is only in `general`, and the finding ID
  is named differently in `findings` (`reference_number`) and `findings_text`
  (`finding_ref_number`).

**Surprises**
- `entity_type = local` covers far more than cities and counties.
- Yes/no fields are text, and the two tables spell them differently.
- Census-era audits (2016 to about 2022) appear to have no finding text, only a placeholder.
- An audit can flag a material weakness in `general` with no rows in `findings`.

**Later the same day, with my own FAC key**
- Checked all 2,669 Virginia `local` audits. Only 351 (13%) have any finding.
- Corrected an early guess: finding text is missing for 2016 to 2018 only, not through 2022.
  From 2019 on the auditor's words are there.
- 148 audits flag a material weakness in `general` but have no rows in `findings`.
- First commit made. The repo is local only; GitHub is on hold until I can make an account.

**Evening: the database**
- Created a Neon project (Postgres 18, free tier) and put its connection string in `.env`.
- Wrote `schema.sql` (three tables) and `load_fac.py` (fetch, clean, load). Loaded 2,669
  audits, 1,260 finding rows and 598 finding texts.
- Cleaning the loader does: Yes/No and Y/N become true/false, the `GSA_MIGRATION`
  placeholder becomes empty, exact duplicate rows are dropped, and the finding ID gets
  one name (`reference_number`) in both tables.
- Loaded every `local` entity and every year. This was Claude's recommendation and I have
  not confirmed it yet. Narrowing later is a filter, not a rebuild.

**Night: I asked Claude to build the rest so I can study it afterwards**
- This changes how we work. The brief said I would write the rubric, the hand ratings
  and the miss causes, and explain each step back. I have not done any of that yet.
- Built and tested: the lookup page (`app.py`), the LangGraph approval workflow
  (`workflow.py`) and the MCP server with two tools (`mcp_server.py`).
- Built but never run against the AI: `risk.py` (the Claude call) and `evaluate.py`.
  There is no Claude API key on this machine.
- `RUBRIC.md` is Claude's draft, marked as such. `eval/hand_ratings.csv` lists the 30
  sampled localities with the rating column empty.

**Late night: the AI run**
- No API credits, so the drafts go through Claude Code on my Claude subscription. I
  signed the command-line tool in with `claude auth login`.
- Ran `evaluate.py run` and `report`. AI matched the rule-based reference on 28 of 30,
  all 116 quotes were found word for word, and all 10 no-findings localities came back
  unrated. Estimated $0.055 per sheet at API list prices.
- The two mismatches are both the AI rating one level higher and citing finance
  staffing. Whether that is right is mine to judge in `eval/misses.csv`.
- `MEMO.md` written as a draft.

## 2026-10-11: Session 2, being honest about the second ratings

- I had an AI fill in all 30 ratings and notes. I checked about 10 myself and agreed
  with each. I did not record which 10.
- So the file is now `eval/second_ratings.csv` and the report calls it "a second AI
  rater". It agrees with the first AI on 27 of 30. It has a `checked_by_me` column for
  the rows I rate myself.
- The lookup page now shows the "Modified opinion" label, which the rubric uses and the
  page was missing.

- Later I went through all 30 and agreed with each second rating, so every row is
  marked `checked_by_me`. The tool matches them on 27 of 30. This was a review after
  seeing the AI's answer, not a blind rating, and the report says so.

- Then I read the five disagreements and wrote my own ruling on each. I rate Floyd,
  Shenandoah and Wytheville medium (the second AI said high), New River Valley low (the
  tool said medium) and Middle Peninsula high. My ratings and the second AI's now sit
  side by side in `eval/ratings.csv`. The tool matches mine on 29 of 30.
- Every disagreement came from the rubric's "systemic" sentence.
- The memo is no longer marked draft.

- Checked the problem statement against sources. Corrected two things: the federal rule
  does not say "every year" (agencies set the schedule), and "a monitor fills in a
  spreadsheet by hand" was an assumption. Replaced it with evidence from Virginia's own
  single audit: Social Services missed 15 of 316 locality risk assessments in fiscal
  year 2025 (finding 2025-017), read from the FAC.
- The 369 figure is my own count of local entities with an audit for 2023 to 2025. It
  is not a count of any agency's subrecipients.

- Looked for the real process to test against. Found two real instruments:
  the DCJS Grant Monitoring Risk Assessment spreadsheet (8 factors, points, low 1 to 6,
  medium 7 to 13, high 14 or more) and North Carolina's county subrecipient risk matrix.
  Found no completed assessments; those are internal agency records.
- What this showed: the real form scores the audit by whether one exists and by the
  auditor's opinion, with a free-text box for concerns. My rubric scores finding flags
  instead. So the tool's rating does not match the form a monitor actually fills in.
  Not fixed yet.

- Then researched the whole real process and wrote it up in `PROCESS.md`, with sources:
  the federal rules, the auditors' test plan, and what nine Virginia agencies publish.
- The biggest thing I had wrong: I rated a locality as a whole, by how severe its
  findings were. A real monitor works for one agency and asks whether the audit is on
  file, on time, and whether the findings are on that agency's money. Virginia's VDEM
  form gives 35 points, its high-risk line, for one finding on a VDEM grant, and 5 for
  a finding on someone else's.
- So the tool changed. The loader now also pulls each audit's federal programs, who
  passed the money down, and the corrective action plans (six tables). The page has an
  agency view: pick an agency, see its subrecipients, late and overdue audits, findings
  on its money, the management decision due date, and the audit rows of three real
  forms (VDEM, DCJS, North Carolina), all worked out by code.
- The AI now gets each finding's program, agency and corrective action plan, and is told
  a plan is a promise and not proof. Evaluation rerun with this evidence.
- Kept the severity rubric as the draft of a monitor's "documented concerns". Checked it
  against North Carolina's audit row: same level for 27 of 68 localities.
- Evaluation rerun finished: every one of the 30 AI ratings is the same as in the first
  run. 29 of 30 against mine, 117 of 117 quotes found, 10 of 10 no-findings cases left
  unrated, about $0.07 a sheet.
- Rewrote the memo around the agency view and cut it back to two pages.

## 2026-10-14: Session 4, published and deployed

- Rewrote the 17 commits to use my GitHub private email before anything went public.
- Created the public repo `Excelsior-Argos/federal-grant-risk-screen` and pushed.
- Created a free Azure App Service web app. Azure for Students only allows five regions;
  West US 3 was refused, so it runs in Mexico Central.
- Created a read-only database login for the site and gave Azure that one, not the owner
  login. Tested: it reads everything and is refused when it tries to write.
- Connected Azure to GitHub. The managed-identity method failed ("couldn't verify how
  GitHub Actions issues OIDC tokens"), so it uses a publish profile stored as a GitHub
  secret. First GitHub Actions run passed and the page is live at https://federal-grant-risk-screen-hufggeccbygdeedg.mexicocentral-01.azurewebsites.net

**Not done**
- `RUBRIC.md` still carries its draft notice.
- I have not read the sources in `PROCESS.md` myself. An AI assistant did the research.
- No agency has checked my reading of their forms.

**Mine to do**
- Read `RUBRIC.md`, change what I disagree with, remove the draft notice.
- After the run, fill in the `cause` column of `eval/misses.csv`.
- Confirm or change "every `local` entity, every year".

**Next session**
- Put my name on the memo. Decide whether to tighten "systemic" in the rubric.
  Create the GitHub repo, push, deploy the page.

## 2026-10-14: Session 4 (continued), a page a monitor can use

- Approved all AI drafts at once (my decision, in chat). 68 localities now have an
  approved risk sheet: 16 high, 15 medium, 37 low. No draft failed the quote check, so
  none were held back. The page says they were approved in bulk, not read one by one.
- Rebuilt the page. It opens on DCJS with four number tiles and a "Needs your attention"
  list of cards, each with its rating, the compliance areas involved, the decision due
  date and an Open button. Opening a locality now replaces the page, with a Back button,
  instead of appearing far below the tables (the old "tick a row" seemed to do nothing).
- A locality has four tabs: Summary (the approved risk sheet with the auditor's quotes),
  Audit checks, Findings, and Audit history. Plain words throughout: "audit problems on
  your grants", "your written decision is due".
- Light theme in `.streamlit/config.toml`.
