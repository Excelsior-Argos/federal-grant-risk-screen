-- Six tables, rebuilt from scratch on every load.
-- Column names follow the FAC API, except that the finding ID is called
-- reference_number everywhere (the API calls it finding_ref_number in two tables).

drop table if exists corrective_actions;
drop table if exists finding_texts;
drop table if exists findings;
drop table if exists passthroughs;
drop table if exists awards;
drop table if exists audits;

-- One row per audit. Source: FAC `general`.
create table audits (
    report_id                                        text primary key,
    auditee_ein                                      text not null,  -- the stable ID for a locality across years
    auditee_uei                                      text,           -- empty for audits migrated from the Census system
    auditee_name                                     text not null,
    auditee_city                                     text,
    audit_year                                       integer not null,
    fy_end_date                                      date,
    fac_accepted_date                                date,
    audit_type                                       text,
    total_amount_expended                            bigint,         -- federal dollars spent that year
    gaap_results                                     text,           -- the auditor's opinion on the financial statements
    is_going_concern_included                        boolean,
    is_internal_control_deficiency_disclosed         boolean,
    is_internal_control_material_weakness_disclosed  boolean,
    is_material_noncompliance_disclosed              boolean,
    is_low_risk_auditee                              boolean,
    auditor_firm_name                                text,
    data_source                                      text,           -- CENSUS (migrated) or GSAFAC (current system)
    loaded_at                                        timestamptz not null default now()
);

-- One row per federal program in an audit. Source: FAC `federal_awards`.
create table awards (
    report_id             text not null references audits,
    award_reference       text not null,
    aln                   text,     -- the federal program number, e.g. 93.558
    federal_program_name  text,
    amount_expended       bigint,
    is_major              boolean,  -- the auditor tested this program in depth
    is_direct             boolean,  -- true: money came straight from a federal agency, not through the state
    audit_report_type     text,     -- the opinion on a major program: U unmodified, Q qualified, A adverse, D disclaimer
    findings_count        integer,
    primary key (report_id, award_reference)
);

-- Who passed the money down. One row per award per pass-through entity. Source: FAC `passthrough`.
create table passthroughs (
    report_id         text not null references audits,
    award_reference   text not null,
    passthrough_name  text not null,  -- as the locality's auditor typed it; spelling varies widely
    agency            text            -- the Virginia state agency we recognised in that name, if any
);
create index passthroughs_report on passthroughs (report_id, award_reference);
create index passthroughs_agency on passthroughs (agency);

-- One row per finding per federal award. Source: FAC `findings`.
create table findings (
    report_id                  text not null references audits,
    award_reference            text not null,
    reference_number           text not null,
    type_requirement           text,     -- compliance requirement letter codes, e.g. L = reporting
    is_modified_opinion        boolean,
    is_other_matters           boolean,
    is_material_weakness       boolean,
    is_significant_deficiency  boolean,
    is_other_findings          boolean,
    is_questioned_costs        boolean,
    is_repeat_finding          boolean,
    prior_finding_ref_numbers  text,
    primary key (report_id, award_reference, reference_number)
);

-- One row per finding: the auditor's written text. Source: FAC `findings_text`.
create table finding_texts (
    report_id                text not null references audits,
    reference_number         text not null,
    finding_text             text,     -- empty for 2016 to 2018, when the text was not collected
    contains_chart_or_table  boolean,
    primary key (report_id, reference_number)
);

-- One row per finding: what the locality says it will do about it. Source: FAC `corrective_action_plans`.
create table corrective_actions (
    report_id         text not null references audits,
    reference_number  text not null,
    planned_action    text,
    primary key (report_id, reference_number)
);
