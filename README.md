# Subrecipient Risk Screen

A tool for a state grants monitor. It pulls Virginia local governments' single-audit
results from the Federal Audit Clearinghouse (FAC), shows a state agency which of its
subrecipients have findings on its money, fills in the audit rows of real agency risk
forms, and drafts a risk sheet per locality that a human must approve.

Federal rule 2 CFR 200.332(c) requires an agency that passes federal money down to
subrecipients to evaluate each one's risk of noncompliance, and names the results of
previous audits as one of four things to consider. The rule sets no schedule; agencies
set their own.

This is a real gap in Virginia. The Commonwealth's fiscal year 2025 single audit
(finding 2025-017, in the FAC as report `2025-06-GSAFAC-0000388108`) found that the
Department of Social Services had not completed 15 of 316 locality risk assessments,
after 50 of 324 the year before. The finding has repeated every year since fiscal year
2021, and the corrective action plan describes tracking the work in spreadsheets.

This tool covers the audit-results factor only. It feeds a risk assessment; it does
not replace one. [PROCESS.md](PROCESS.md) sets out how Virginia agencies actually do
this work, with sources, and which steps the tool does and does not cover.

## Status

| Phase | What it delivers | State |
|---|---|---|
| 1 | Virginia audits and findings in Postgres, plus a lookup page | Data loaded and page working locally. **Not deployed**: needs a GitHub account. |
| 1b | The agency view, added after researching the real process | Working locally: an agency's subrecipients, audit on file and on time, findings on its money, and the audit rows of three real forms. |
| 2 | AI-drafted risk sheets, measured against 30 hand-rated localities | AI run on 30 localities on 2026-10-10. The tool matches my ratings on 29 of 30. **My check was a review of AI-drafted ratings, not a blind rating.** |
| 3 | Human-approval workflow, MCP server, memo to a grants manager | Workflow and MCP server working. [MEMO.md](MEMO.md) is written. |

## Results so far

From [eval/REPORT.md](eval/REPORT.md), run on 2026-10-10 with `claude-opus-5-5`:

| Check | Result |
|---|---|
| AI rating matches the rubric applied by code to the yes/no flags | 28 of 30 (93%) |
| Quotes found word for word in the finding they cite | 116 of 116 |
| Localities with no findings left unrated, nothing invented | 10 of 10 |
| AI rating matches my rating | 29 of 30 (97%) |
| AI rating matches a second, separate AI pass | 27 of 30 (90%) |
| Estimated cost per drafted sheet, at API list prices | $0.055 |

These show the AI applies the rubric consistently. The AI is given the same rubric and
flags as the code it is compared with. For my own ratings in
[eval/ratings.csv](eval/ratings.csv), another AI session drafted a rating for each
locality and I reviewed all 30 and changed four, having seen AI ratings first. That is
weaker than rating blind. Every disagreement came from one sentence in the rubric, on
what counts as a systemic problem; my reasons are in [eval/misses.csv](eval/misses.csv). [RUBRIC.md](RUBRIC.md) is also still a draft.

## How it fits together

```
FAC API ──load_fac.py──> Postgres (Neon) ──┬──> app.py          agency view and lookup page (Streamlit)
                                           ├──> risk.py         evidence, audit review, AI draft, quote check
                                           │      ├─ evaluate.py   Phase 2: measure the AI
                                           │      └─ workflow.py   Phase 3: draft, then human approval (LangGraph)
                                           └──> mcp_server.py   two read-only tools for AI agents (MCP)
```

| File | What it does |
|---|---|
| [explore_fac.py](explore_fac.py) | Prints one real row from each FAC table. Saves nothing. |
| [PROCESS.md](PROCESS.md) | The real process: the rules, what Virginia agencies do, the forms they use, and where this tool fits. |
| [schema.sql](schema.sql), [load_fac.py](load_fac.py) | The six data tables and the loader that fills them. |
| [common.py](common.py) | Database access, FAC lookups and the matching of pass-through names to state agencies. |
| [app.py](app.py) | The page. Pick an agency to see its subrecipients, then a locality. Shows a risk sheet only after a person has approved it. |
| [RUBRIC.md](RUBRIC.md) | How a finding-severity rating is decided. Read by me, by the AI and by `rule_rating`. |
| [risk.py](risk.py), [schema_risk.sql](schema_risk.sql) | Gathers a locality's evidence, works out the audit review and form rows by code, drafts the sheet, checks every quote, stores the draft. |
| [evaluate.py](evaluate.py), [eval/](eval/) | Picks 30 localities, compares AI ratings with mine and with a second AI's, logs each miss. |
| [workflow.py](workflow.py) | Drafts one sheet, pauses, and records the reviewer's decision. |
| [mcp_server.py](mcp_server.py) | `get_locality_findings` and `search_findings` for any MCP client. |

## What is in the database

Loaded from the FAC API on 2026-10-11. The most recent audit in it was accepted by the
FAC on 2026-10-07.

| Table | Rows | One row is |
|---|---|---|
| `audits` | 2,669 | one audit of a Virginia local entity, audit years 2016 to 2025 |
| `awards` | 69,610 | one federal program in one audit, with whether it was audited as a major program and the opinion |
| `passthroughs` | 58,531 | one award and the body that passed the money down |
| `findings` | 1,260 | one finding on one federal award |
| `finding_texts` | 598 | the auditor's written text for one finding |
| `corrective_actions` | 598 | what the locality says it will do about one finding |
| `risk_sheets` | 0 | one drafted risk sheet and the reviewer's decision on it |

The 2,669 audits cover 449 distinct entities, counted by EIN. The loader dropped 9 exact
duplicate rows from `findings` and 2 each from `finding_texts` and `corrective_actions`.

Each locality's auditor types the pass-through agency's name freely: there are 1,889
spellings. Matching on a phrase each agency's name always contains ties 51,236 of the
58,531 rows (88%) to one of 13 Virginia state agencies. The rest are federal agencies,
other states, or bodies such as "Commonwealth of Virginia" that name no agency.

## The agency view

A monitor works for one agency and answers for the findings on that agency's money, so
the page starts there. For audit years 2023 to 2025:

| Agency | Subrecipients | Latest audit filed late | Next audit overdue | With findings on its money |
|---|---|---|---|---|
| Criminal Justice Services | 188 | 52 | 42 | 7 |
| Social Services | 142 | 33 | 22 | 7 |
| Education | 139 | 34 | 17 | 15 |

For each locality the page then answers what a real form asks: is the audit on file and
on time, what did the auditor conclude, which findings are on this agency's money, and
when is the management decision due. Code turns that into the audit rows of three real
forms (Virginia VDEM, Virginia DCJS and North Carolina DHHS). No AI is used for this.

How the project's own severity rating compares with a real form, across the 68
localities with a finding in the window: it gives the same level as North Carolina's
audit row for 27. The rating looks hardest at the latest audit and wants more than one
warning sign before it says high. My reading of North Carolina's row marks any serious,
repeat or questioned-cost finding in two years as high. Neither is wrong; they are
different rules, and the Virginia forms score something else again: whose money the
finding is on.

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

1. **Evidence.** `gather_evidence` collects the locality's audits, federal programs,
   findings and corrective action plans for the three most recent audit years (2023 to
   2025). Each finding carries its program and the state agency that passed the money down.
2. **No findings, no AI.** If there is no finding text, the sheet says "no basis to
   rate" and is written by code. The AI is not called, so it cannot invent anything.
3. **Draft.** Otherwise Claude (`claude-opus-5-5`) gets the rubric and the evidence and
   returns a rating, reasons with the auditor's words quoted, and what to check next.
   With `ANTHROPIC_API_KEY` set the call goes to the Claude API. Without it, the call
   goes through Claude Code on this machine, using a Claude subscription.
4. **Quote check.** Code looks for every quote, word for word, in the finding it cites.
   Anything it cannot find is flagged to the reviewer. A quote from the locality's own
   corrective action plan fails this check on purpose: only the auditor's words count.
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
(a Postgres connection string; this project uses Neon's free tier). For the AI steps,
either set `ANTHROPIC_API_KEY` or sign Claude Code in once with `claude auth login`.

| To do this | Run this |
|---|---|
| Rebuild the data tables from the FAC (about two minutes, safe to repeat) | `.venv\Scripts\python load_fac.py` |
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

- The AI draft through Claude Code, for 30 sampled localities and 10 with no findings.

- The approval workflow on a locality that needs an AI draft (City of Emporia, rejected
  as a test and removed), on 2026-10-11.

- The agency view, the audit review and all three form rows on 2026-10-11: run headless
  through three page views with no errors, and the agency worklist checked against the
  per-locality review for 20 localities with no mismatch.

Not tested: the Claude API route in `risk.ask_model` (no API key on this machine). The
form rows are my reading of each form's wording applied to FAC data; no agency has
checked them.

## Data source

Federal Audit Clearinghouse API, <https://api.fac.gov>. Field list:
<https://www.fac.gov/api/dictionary/>.
