# Payment Processing SLA Definitions and Escalation Procedures

This document defines the service level agreements (SLAs) for payment processing stages in PAYplus, the definition of a stuck payment, escalation paths, and recovery procedures for delayed or stalled payments.

---

## Standard Processing SLA Windows

| Stage | From Event | To Event | Target | Breach Threshold | Priority |
|-------|-----------|----------|--------|-----------------|----------|
| Receipt → Format validation | PAYMENT_RECEIVED | FORMAT_VALIDATED | < 5 s | > 30 s | P3 |
| Format → Sanctions screening | FORMAT_VALIDATED | SANCTIONS_CLEARED / SANCTIONS_HIT | < 30 s | > 2 min | P2 |
| Sanctions → Routing | SANCTIONS_CLEARED | ROUTING_RESOLVED | < 2 min | > 5 min | P2 |
| Routing → Settlement initiated | ROUTING_RESOLVED | SETTLEMENT_INITIATED | < 5 min | > 15 min | P1 |
| Settlement initiated → Correspondent ACK | SETTLEMENT_INITIATED | CORRESPONDENT_ACK | < 2 h | > 4 h | P1 |
| Correspondent ACK → Settlement confirmed | CORRESPONDENT_ACK | SETTLEMENT_CONFIRMED | < 30 min | > 2 h | P1 |
| **End-to-end (RCVD → ACCC)** | **PAYMENT_RECEIVED** | **SETTLEMENT_CONFIRMED** | **< 3 h** | **> 6 h** | **P0** |

SLA targets apply to standard business hours. Payments processed outside cut-off times are subject to next-day settlement; this does not constitute a breach.

---

## Stuck Payment Definition

A payment is classified as **stuck** when any of the following conditions are met:

1. **No ACCC within 6 hours** of PAYMENT_RECEIVED and no EXCEPTION_RAISED event exists.
2. **PROCESSING_DELAYED event present** with no subsequent SETTLEMENT_CONFIRMED after 2 additional hours.
3. **ACWP (AcceptedWithoutPosting) status** held for more than 2 hours without progression.
4. **No CORRESPONDENT_ACK** received within 4 hours of SETTLEMENT_INITIATED.

In the PayInvestigator system, stuck payments are identified by `is_stuck = true` in the payments table and have a PROCESSING_DELAYED event in the payment_events log.

---

## Priority Definitions

| Priority | Criteria |
|----------|----------|
| **P0** | End-to-end breach; payment value > USD 1M equivalent; regulatory deadline at risk; customer-impacting |
| **P1** | Single-stage breach; large-value payment; correspondent relationship at risk; potential cut-off miss |
| **P2** | Minor stage breach; low-value payment; no immediate customer impact |
| **P3** | Informational; performance monitoring only; no escalation required |

---

## Escalation Matrix

| Condition | L0 (Auto-notify) | L1 (Ops Team) | L2 (Team Lead) | L3 (Ops Manager) | L4 (Head of Payments) |
|-----------|-----------------|---------------|----------------|------------------|-----------------------|
| P3 breach | Dashboard alert | — | — | — | — |
| P2 breach | Dashboard alert | Within 30 min | Within 1 h | — | — |
| P1 breach | PagerDuty alert | Immediate | Within 15 min | Within 1 h | — |
| P0 breach | PagerDuty + SMS | Immediate | Immediate | Within 15 min | Within 30 min |
| Sanctions hold > 4 h unresolved | — | — | Compliance Officer | Senior Compliance Officer (8 h) | CCO (24 h) |
| Confirmed duplicate | — | Immediate | Within 30 min | — | — |
| UETR reuse suspected | — | Within 1 h | — | — | — |

---

## PROCESSING_DELAYED Recovery Procedure

When a `PROCESSING_DELAYED` event is detected:

1. **Identify the last known state** — retrieve all `payment_events` for the UETR; note the last event type, timestamp, and actor (correspondent BIC).
2. **Contact the correspondent agent** — use the BIC directory to identify the operations contact for the receiving institution; provide UETR and settlement date.
3. **Await status update** — allow 1 hour for a response before escalating.
4. **Issue global Status Request (gSRP)** — if no response after 1 hour, send a gSRP via SWIFT Correspondent Services quoting the UETR.
5. **Initiate payment trace (camt.031)** — if no ACCC within 8 hours total from SETTLEMENT_INITIATED, issue a `camt.031 GetTransaction` to formally request status.
6. **Escalate to P0** — if no resolution after 12 hours total from PAYMENT_RECEIVED, escalate to P0 and engage Head of Payments.
7. **Document all contact attempts** in the audit trail with timestamps, contact names, and outcomes.

---

## Cut-Off Times

Payments must be SETTLEMENT_INITIATED before the applicable cut-off time to achieve same-day settlement. Payments initiated after cut-off are queued for next-business-day settlement.

| Currency / System | Cut-Off (CET) |
|-------------------|--------------|
| EUR (TARGET2) | 17:00 |
| USD (CHIPS) | 17:00 ET (23:00 CET) |
| GBP (CHAPS) | 16:00 |
| CHF (SIC) | 16:30 |
| General CBPR+ | Bilateral — check correspondent agreement |

A payment that misses cut-off due to an exception investigation is still subject to SLA from the original PAYMENT_RECEIVED timestamp. The exception record should note the cut-off impact.

---

## Monitoring Queries

Use the following against the `payment_events` table to surface stuck payments:

```sql
-- Payments with no SETTLEMENT_CONFIRMED and received > 6 hours ago
SELECT p.msg_id, p.uetr, p.amount, p.currency, MIN(e.occurred_at) AS received_at
FROM payments p
JOIN payment_events e ON e.msg_id = p.msg_id AND e.event_type = 'PAYMENT_RECEIVED'
WHERE p.msg_id NOT IN (
    SELECT msg_id FROM payment_events WHERE event_type = 'SETTLEMENT_CONFIRMED'
)
AND p.msg_id NOT IN (
    SELECT msg_id FROM payment_events WHERE event_type = 'EXCEPTION_RAISED'
)
AND e.occurred_at < NOW() - INTERVAL '6 hours'
GROUP BY p.msg_id, p.uetr, p.amount, p.currency
ORDER BY received_at ASC;
```
