# Duplicate Payment Detection and Resolution Runbook

A duplicate payment occurs when the same economic transaction is processed more than once, either due to a system error, a submission retry, or a UETR reuse. This runbook defines detection methods, investigation steps, and resolution paths.

---

## What Constitutes a Duplicate

### Type 1 — UETR Duplicate
The same Unique End-to-End Transaction Reference (`PmtId/UETR`) appears in two separate pacs.008 messages. Per SWIFT standards, a UETR must be a globally unique UUID v4 generated once per transaction and never reused. Any UETR collision is an error.

### Type 2 — Business Duplicate
Two payments share the same combination of:
- Debtor account (IBAN or account ID)
- Creditor account (IBAN or account ID)
- Amount and currency
- Value date

within a configurable duplicate-check window (default: 24 hours). Business duplicates may carry different UETRs if the sender incorrectly generated a new UETR for a retry.

### Type 3 — Instruction ID Duplicate
The same `InstrId` is submitted by the same instructing agent (`InstgAgt BIC`) within the check window. Less definitive than UETR — use as a corroborating signal.

---

## Detection

| Signal | Confidence | Action |
|--------|-----------|--------|
| UETR match | High | Automatic HOLD |
| Business key match (accts + amount + ccy + date) | Medium-High | HOLD + investigation |
| InstrId match from same InstgAgt | Medium | Flag for review |
| Two or more signals | Very High | Automatic HOLD |

---

## Investigation Steps

1. **Hold the later-received payment** — do not settle while investigation is underway.
2. **Retrieve the original payment record** — pull by UETR or business key from the payments table.
3. **Field-level comparison** — compare all material fields between original and suspected duplicate:
   - Debtor IBAN / name
   - Creditor IBAN / name
   - Amount and currency
   - Value date
   - Remittance information (`RmtInf/Ustrd`)
   - Instructing agent BIC
4. **Determine duplicate type:**
   - **All fields identical** → confirmed duplicate → proceed to Recall
   - **Most fields identical, UETR differs** → likely retry with new UETR → treat as business duplicate
   - **UETR matches but amounts/parties differ** → UETR reuse error by sender → escalate to instructing agent
5. **Document the comparison** in the exception investigation record.

---

## Recall Procedure (camt.056)

When a confirmed duplicate is identified and the second payment has been forwarded to the creditor agent:

1. Issue a `camt.056 PaymentCancellationRequest` to the creditor agent.
2. Include in the cancellation request:
   - `OrgnlMsgId` — message ID of the duplicate payment
   - `OrgnlMsgNmId` — `pacs.008.001.08`
   - `OrgnlUETR` — UETR of the duplicate
   - `CxlRsnInf/Cd` — `DUPL` (Duplicate Payment)
3. **SLA:** Creditor agent must respond with `camt.029` within 2 business days (SWIFT CBPR+ standard).
4. If funds have already been credited to the beneficiary, the creditor agent must initiate a debit reversal from the beneficiary's account.

---

## Resolution Outcomes

| Scenario | Resolution |
|----------|------------|
| Duplicate confirmed, payment not yet settled | Cancel second payment; update status to CANCELLED; release original |
| Duplicate confirmed, recall accepted | Record cancellation confirmation; close exception |
| Duplicate confirmed, recall rejected (funds disbursed) | Initiate dispute process; notify operations and legal |
| Not a duplicate — UETR reuse by sender | Return second payment with reject code AM05; request new UETR from sender |
| Business duplicate — sender confirms intentional | Release second payment with documented confirmation |

---

## Audit Requirements

Every duplicate investigation must include in the audit trail:
- Detection timestamp and detection method (UETR / business key / InstrId)
- Original payment record reference
- Field-by-field comparison table
- Analyst identity and decision timestamp
- Approval chain for any release decision
- Outcome and final payment status

Audit records must be retained for a minimum of 7 years per BSA/AML requirements.

---

## Prevention Guidance (for instructing agents)

- Generate UETR using UUID v4 exactly once per transaction; never reuse for retries
- Implement idempotency checks before resubmission: verify the original message status via gSRP before sending a new pacs.008
- Use `InstrId` consistently and track it in your system as the primary idempotency key
- For retries after a network timeout: wait for confirmation or query status; do not assume the first message was lost
