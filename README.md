# Subrecipient Risk Screen

A tool for a state grants monitor. It pulls Virginia local governments' single-audit
results from the Federal Audit Clearinghouse (FAC), shows what the auditors found, and
(in later phases) drafts a risk sheet per locality for a human to approve.

Federal rule 2 CFR 200.332 requires a state that passes federal money down to
subrecipients to assess each one's risk and follow up on audit findings. Today that is
done by reading each audit and filling in a spreadsheet by hand.

## Status

**Phase 1, the data foundation (no AI): in progress.** The data is loaded into Postgres.
The lookup page is not built yet.

## What is in the database

Loaded from the FAC API on 2026-10-10. The most recent audit in it was accepted by the
FAC on 2026-10-07.

| Table | Rows | One row is |
|---|---|---|
| `audits` | 2,669 | one audit of a Virginia local entity, audit years 2016 to 2025 |
| `findings` | 1,260 | one finding on one federal award |
| `finding_texts` | 598 | the auditor's written text for one finding |

The 2,669 audits cover 449 distinct entities, counted by EIN. The loader dropped 9 exact
duplicate rows from `findings` and 2 from `finding_texts`. Table definitions are in
[schema.sql](schema.sql).

| Phase | What it delivers | State |
|---|---|---|
| 1 | Virginia audits and findings in Postgres, plus a deployed lookup page | In progress |
| 2 | AI-drafted risk sheets, measured against 30 hand-rated localities | Not started |
| 3 | Human-approval workflow, MCP server, memo to a grants manager | Not started |

## What the data looks like

Checked against the live FAC API on 2026-10-10.

- The API holds 8,508 audits with a Virginia auditee address, audit years 2016 to 2026.
  Between 235 and 314 a year are tagged `entity_type = local`.
- `local` is wider than cities and counties. It includes school boards, housing
  authorities, planning district commissions and water authorities.
- Only `general` has a state column (`auditee_state`). `findings` and `findings_text`
  have none, so they are fetched by `report_id`.
- The finding ID is `reference_number` in `findings` and `finding_ref_number` in
  `findings_text`.
- Yes/no fields arrive as text, not true/false: `Yes`/`No` in `general`, `Y`/`N` in `findings`.
- `findings` only lists findings tied to a federal award. An audit can report a
  financial-statement material weakness in `general` and still have zero rows in `findings`.

Counts for the 2,669 Virginia `local` audits (audit years 2016 to 2025):

| Measure | Count |
|---|---|
| Audits with at least one finding | 351 (13%) |
| Distinct findings | 598 |
| Of those, with real auditor text | 438 |
| Of those, with only the placeholder `GSA_MIGRATION` | 160 |
| Audits flagging a material weakness in `general` with no rows in `findings` | 148 |

- The missing text is almost all in audit years 2016 to 2018 (158 of the 160 placeholders).
  From 2019 on, every finding but two has real text. Median length is about 1,600 characters.
- Every finding has a matching `findings_text` row.
- An entity's name is spelled differently from year to year (833 spellings for 449
  entities), so the EIN is what ties its audits together.
- All 148 material-weakness-but-no-findings audits were submitted to the current GSA
  system. None of the 1,751 Census-era audits show that pattern, which I have not explained yet.

## Run it

Windows, Python 3.14, no WSL.

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

In `.env`, set `FAC_API_KEY` to a free key from <https://api.data.gov/signup> and
`DATABASE_URL` to a Postgres connection string (this project uses Neon's free tier). Then:

```powershell
.venv\Scripts\python explore_fac.py
```

prints one real row from each of the three FAC tables and saves nothing, and

```powershell
.venv\Scripts\python load_fac.py
```

rebuilds the three database tables from the FAC. It takes about a minute and is safe to
run again.

## Data source

Federal Audit Clearinghouse API, <https://api.fac.gov>. Field list:
<https://www.fac.gov/api/dictionary/>.
