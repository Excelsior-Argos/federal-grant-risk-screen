-- Three tables, rebuilt from scratch on every load.
-- Column names follow the FAC API, except that the finding ID is called
-- reference_number everywhere (the API calls it finding_ref_number in findings_text).

drop table if exists finding_texts;
drop table if exists findings;
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
