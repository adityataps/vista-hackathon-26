-- =====================================================================
-- PayInvestigator mock payment DB
-- Modeled loosely on Finastra GPP's real MINF (payment master) and
-- NEWJOURNAL (audit history) tables, simplified for the hackathon demo.
--
-- Field names/prefixes (P_*, MID, ACTIONID, FIELD_LOGICAL_ID, etc.) are kept
-- consistent with GPP naming conventions so the demo "feels" real, while the
-- column set is trimmed down to only what the agents need.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- MINF: one row per payment, always reflecting its CURRENT/latest state.
-- ---------------------------------------------------------------------
CREATE TABLE MINF (
    P_MID                   TEXT PRIMARY KEY,       -- unique payment/message id (e.g. MID000001)
    P_OFFICE                TEXT NOT NULL,           -- processing office/branch code
    P_MSG_TYPE              TEXT NOT NULL,           -- SWIFT/ISO20022 message type, e.g. pacs.008, MT103

    P_STATUS                TEXT NOT NULL,           -- current lifecycle status (see status list below)
    P_LAST_ACTION           TEXT,                    -- last action code/description applied to the payment

    P_ERROR_CODE            TEXT,                    -- current blocking error code, if any (FK-ish to error_code_catalog)
    P_ERROR_DESC            TEXT,                    -- short human-readable error description

    P_AMOUNT                NUMBER(18,2) NOT NULL,
    P_CURRENCY              TEXT NOT NULL,           -- ISO currency code
    P_VALUE_DATE            DATE,
    P_PRIORITY              TEXT DEFAULT 'NORM',     -- NORM / URGENT / HIGH

    -- Debit (sender / ordering customer) side
    P_DBTR_NAME             TEXT,
    P_DBT_ACCT_NB           TEXT,                    -- sender IBAN/account number
    P_DBT_ACCT_CCY          TEXT,
    P_DBTR_AGT_BIC          TEXT,                    -- sender bank BIC

    -- Credit (receiver / beneficiary) side
    P_CDTR_NAME             TEXT,
    P_CDT_ACCT_NB           TEXT,                    -- receiver IBAN/account number
    P_CDT_ACCT_CCY          TEXT,
    P_CDTR_AGT_BIC          TEXT,                    -- receiver bank BIC

    P_COUNTRY_CODE          TEXT,                    -- beneficiary/destination country

    P_DUPLICATE_INDEX       INTEGER DEFAULT 0,       -- >0 flags payment as a probable duplicate
    P_SANCTIONS_HIT_FLAG    TEXT DEFAULT 'N',         -- Y/N screening hit indicator
    P_SANCTIONS_SCORE       NUMBER(5,2),              -- match confidence score 0-100

    XML_MSG                 TEXT,                     -- raw SWIFT/pacs.008 payload (for realism/demo drill-down)

    P_CREATE_DATETIME       TEXT NOT NULL,            -- ISO8601 timestamp payment was created
    P_LAST_UPDATE_DATETIME  TEXT NOT NULL             -- ISO8601 timestamp of latest state change
);

-- Suggested P_STATUS values:
--   NEW, VALIDATED, PENDING_REPAIR, HELD_COMPLIANCE, HELD_DUPLICATE,
--   AUTO_CORRECTED, PENDING_APPROVAL, RELEASED, COMPLETED, CANCELLED, REJECTED

-- ---------------------------------------------------------------------
-- NEWJOURNAL: append-only history/audit trail, one row per state change.
-- ---------------------------------------------------------------------
CREATE TABLE NEWJOURNAL (
    PK_JOURNAL          INTEGER PRIMARY KEY AUTOINCREMENT,
    MID                 TEXT NOT NULL REFERENCES MINF(P_MID),
    OFFICE              TEXT,
    TIME_STAMP          TEXT NOT NULL,               -- ISO8601 timestamp of this history event
    STATUS              TEXT NOT NULL,                -- status the payment moved to at this point
    ACTIONID1           TEXT,                         -- primary action code (e.g. AUTO_FIX, HOLD, RELEASE)
    ACTIONID2           TEXT,                         -- secondary/sub-action code
    USERNAME            TEXT,                         -- user or agent that performed the action (e.g. 'TECH_DIAGNOSIS_AGENT')
    MODULE_ID           TEXT,                         -- originating agent/module (Intake, Investigation, Compliance, Technical, Resolution)
    ERROR_CODE          TEXT,
    ERROR_DESC          TEXT,
    ERROR_PARAMS        TEXT,                         -- extra context, e.g. old/new field values as JSON
    ERROR_SEVERITY      INTEGER,                      -- 1=info,2=warning,3=error,4=critical
    FIELD_LOGICAL_ID    TEXT,                         -- which logical field changed (e.g. CDT_ACCT_NB) if applicable
    FLOW_ID             TEXT,                         -- flow/workflow instance identifier
    FAULT               TEXT DEFAULT 'N'              -- Y/N whether this event represents a fault
);

CREATE INDEX IX_NEWJOURNAL_MID ON NEWJOURNAL(MID);
CREATE INDEX IX_MINF_STATUS ON MINF(P_STATUS);
