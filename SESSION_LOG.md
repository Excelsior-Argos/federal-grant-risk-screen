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

**Not done**
- No GitHub repo, so nothing is pushed.
- No Neon database.

**Open decisions (mine)**
- What counts as a "locality": every `local` entity, or only counties, cities and towns?
- Which audit years to load.

**Next session**
- Create a Neon account, agree the schema, write the loader.
