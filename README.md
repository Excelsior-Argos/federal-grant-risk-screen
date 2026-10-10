# Subrecipient Risk Screen

A tool for a state grants monitor. It pulls Virginia local governments' single-audit
results from the Federal Audit Clearinghouse (FAC), shows what the auditors found, and
drafts a risk sheet per locality that a human must approve.

Federal rule 2 CFR 200.332 requires a state that passes federal money down to
subrecipients to assess each one's risk and follow up on audit findings. Today that is
done by reading each audit and filling in a spreadsheet by hand.

## Status

| Phase | What it delivers | State |
|---|---|---|
| 1 | Virginia audits and findings in Postgres, plus a lookup page | Data loaded and page working locally. **Not deployed**: needs a GitHub account. |
| 2 | AI-drafted risk sheets, measured against 30 hand-rated localities | Code written. **The AI has not been run**: needs a Claude API key. The 30 hand ratings are not filled in. |
| 3 | Human-approval workflow, MCP server, memo to a grants manager | Workflow and MCP server working. **Memo not written**: it needs the Phase 2 numbers. |

No accuracy or cost figure exists yet. Nothing in this repo should be read as evidence
that the AI ratings are right.

## How it fits together

```
FAC API ──load_fac.py──> Postgres (Neon) ──┬──> app.py          lookup page (Streamlit)
                                           ├──> risk.py         evidence, AI draft, quote check
                                           │      ├─ evaluate.py   Phase 2: measure the AI
                                           │      └─ workflow.py   Phase 3: draft, then human approval (LangGraph)
                                           └──> mcp_server.py   two read-only tools for AI agents (MCP)
```

| File | What it does |
|---|---|
| [explore_fac.py](explore_fac.py) | Prints one real row from each FAC table. Saves nothing. |
| [schema.sql](schema.sql), [load_fac.py](load_fac.py) | The three data tables and the loader that fills them. |
| [common.py](common.py) | Database access and FAC lookups shared by everything else. |
| [app.py](app.py) | The lookup page. Shows a risk sheet only after a person has approved it. |
| [RUBRIC.md](RUBRIC.md) | How a rating is decided. Read by me, by the AI and by `rule_rating`. |
| [risk.py](risk.py), [schema_risk.sql](schema_risk.sql) | Gathers a locality's evidence, drafts the sheet, checks every quote, stores the draft. |
| [evaluate.py](evaluate.py), [eval/](eval/) | Picks 30 localities, compares AI ratings with mine, logs each miss. |
| [workflow.py](workflow.py) | Drafts one sheet, pauses, and records the reviewer's decision. |
| [mcp_server.py](mcp_server.py) | `get_locality_findings` and `search_findings` for any MCP client. |

## What is in the database

Loaded from the FAC API on 2026-10-10. The most recent audit in it was accepted by the
FAC on 2026-10-07.

| Table | Rows | One row is |
|---|---|---|
| `audits` | 2,669 | one audit of a Virginia local entity, audit years 2016 to 2025 |
| `findings` | 1,260 | one finding on one federal award |
| `finding_texts` | 598 | the auditor's written text for one finding |
| `risk_sheets` | 0 | one drafted risk sheet and the reviewer's decision on it |

The 2,669 audits cover 449 distinct entities, counted by EIN. The loader dropped 9 exact
duplicate rows from `findings` and 2 from `finding_texts`.

## What the data looks like

Checked against the live FAC API on 2026-10-10.

- `entity_type = local` is wider than cities and counties. It includes school boards,
  housing authorities, planning district commissions and water authorities.
- Only `general` has a state column (`auditee_state`). `findings` and `findings_text`
  have none, so they are fetched by `report_id`.
- The finding ID is `reference_number` in `findings` and `finding_ref_number` in
  `findings_text`. The loader names it `reference_number` in both.
- Yes/no fields arrive as text, not true/false: `Yes`/`No` in `general`, `Y`/`N` in `findings`.
- `findings` only lists findings tied to a federal award. An audit can report a
  financial-statement material weakness in `general` and still have zero rows in `findings`.
- An entity's name is spelled differently from year to year (833 spellings for 449
  entities), so the EIN is what ties its audits together.

| Measure | Count |
|---|---|
| Audits with at least one finding | 351 of 2,669 (13%) |
| Distinct findings | 598 |
| Of those, with real auditor text | 438 |
| Of those, with only the placeholder `GSA_MIGRATION` | 160 |
| Audits flagging a material weakness in `general` with no rows in `findings` | 148 |

The missing text is almost all in audit years 2016 to 2018 (158 of the 160). From 2019
on, every finding but two has real text. All 148 material-weakness-but-no-findings
audits were submitted to the current GSA system; none of the 1,751 Census-era audits
show that pattern, which I have not explained yet.

## How a risk sheet is made

1. **Evidence.** `gather_evidence` collects the locality's audits and findings for the
   three most recent audit years (2023 to 2025).
2. **No findings, no AI.** If there is no finding text, the sheet says "no basis to
   rate" and is written by code. The AI is not called, so it cannot invent anything.
3. **Draft.** Otherwise Claude (`claude-opus-5-5`) gets the rubric and the evidence and
   returns a rating, reasons with the auditor's words quoted, and what to check next.
4. **Quote check.** Code looks for every quote, word for word, in the finding it cites.
   Anything it cannot find is flagged to the reviewer.
5. **Human decision.** The draft is stored as a draft. `workflow.py` pauses until a
   person approves it, changes the rating, or rejects it. Only approved sheets appear
   on the page.

`rule_rating` applies the rubric's steps 1 to 4 to the yes/no flags with no AI. Across
the 68 localities that have finding text in the window it gives 39 low, 15 medium and
14 high. The evaluation sample takes 10 of each.

## Run it

Windows, Python 3.14, no WSL.

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env`: `FAC_API_KEY` (free, <https://api.data.gov/signup>), `DATABASE_URL`
(a Postgres connection string; this project uses Neon's free tier) and, for the AI
steps only, `ANTHROPIC_API_KEY`.

| To do this | Run this |
|---|---|
| Rebuild the data tables from the FAC (about a minute, safe to repeat) | `.venv\Scripts\python load_fac.py` |
| Open the lookup page | `.venv\Scripts\python -m streamlit run app.py` |
| Draft and review one locality's risk sheet | `.venv\Scripts\python workflow.py "Fairfax County"` |
| Run the Phase 2 evaluation | `.venv\Scripts\python evaluate.py run`, then `evaluate.py report` |
| Start the MCP server (normally an MCP client starts it) | `.venv\Scripts\python mcp_server.py` |

To use the MCP server from Claude Desktop or Claude Code, register it as a stdio server
whose command is the venv's `python.exe` with the argument `mcp_server.py` and this
folder as the working directory.

## What was tested, and what was not

Tested on 2026-10-10:

- The loader, and the row counts above read back from the database.
- The lookup page in a browser, for a locality with findings and one with none.
- Evidence gathering, the rule rating, the no-findings sheet and the quote checker.
- The LangGraph workflow end to end (draft, pause, approve, record) on a locality with
  no findings, which needs no AI call.
- Both MCP tools, called through a real MCP client over stdio.

Not tested: the call to Claude in `risk.ask_model`, and so everything in `evaluate.py run`
and `evaluate.py report`. There was no API key on this machine.

## Data source

Federal Audit Clearinghouse API, <https://api.fac.gov>. Field list:
<https://www.fac.gov/api/dictionary/>.
