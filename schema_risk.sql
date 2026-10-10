-- Risk sheets drafted by the AI and the reviewer's decision on each.
-- Kept apart from schema.sql so that reloading the FAC data never deletes them.

create table if not exists risk_sheets (
    id              bigint generated always as identity primary key,
    auditee_ein     text not null,
    auditee_name    text not null,
    rating          text not null,                -- the AI's draft: low, medium, high or no_basis
    rule_rating     text not null,                -- the rubric's steps 1 to 4 applied by code
    sheet           jsonb not null,               -- the full drafted sheet
    quote_problems  jsonb not null default '[]',  -- quotes that could not be found in the finding text
    model           text,                         -- empty when no AI call was needed
    input_tokens    integer not null default 0,
    output_tokens   integer not null default 0,
    cost_usd        numeric(10, 5) not null default 0,
    status          text not null default 'draft',  -- draft, approved or rejected
    final_rating    text,                         -- the reviewer's rating, set on approval
    reviewer        text,
    reviewer_note   text,
    reviewed_at     timestamptz,
    created_at      timestamptz not null default now()
);
