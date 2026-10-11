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

**Not done**
- No GitHub repo: nothing is pushed and the page is not deployed.
- No hand ratings, so no agreement-with-a-human figure. The memo stays a draft until then.

**Mine to do**
- Read `RUBRIC.md`, change what I disagree with, remove the draft notice.
- Hand-rate the 30 localities in `eval/hand_ratings.csv` before looking at any AI output.
- After the run, fill in the `cause` column of `eval/misses.csv`.
- Confirm or change "every `local` entity, every year".

**Next session**
- Hand-rate the 30, rerun `evaluate.py report`, fill in the miss causes, finish the memo.
  Create the GitHub repo, push, deploy the page.
