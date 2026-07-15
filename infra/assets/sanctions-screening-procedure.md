# Sanctions Screening Procedure — OFAC SDN and International Watchlists

Sanctions screening is mandatory for every payment processed through PAYplus. This document defines the lists screened, match thresholds, hold and release procedures, and false-positive handling requirements.

---

## Watchlists Screened

| List | Authority | Scope |
|------|-----------|-------|
| OFAC SDN (Specially Designated Nationals) | US Treasury | Individuals, entities, vessels — global |
| OFAC Non-SDN Consolidated Sanctions | US Treasury | Sectoral/country programs (Iran, Russia, Cuba, NK) |
| EU Consolidated Financial Sanctions List | European Union | EU-designated individuals and entities |
| UK Financial Sanctions List (UKFSF/HMT) | HM Treasury | Post-Brexit UK-specific designations |
| UN Security Council Consolidated List | United Nations | Global — Al-Qaida, Taliban, DPRK, Iran regimes |

Screening is applied to: `Cdtr/Nm`, `Dbtr/Nm`, `CdtrAgt/FinInstnId`, `DbtrAgt/FinInstnId`, `Cdtr/PstlAdr/Ctry` (country-level programs).

---

## Match Score Thresholds

| Score Range | Action | SLA |
|-------------|--------|-----|
| ≥ 0.95 (exact or near-exact) | Automatic HOLD — freeze immediately | Notify compliance within 15 minutes |
| 0.85 – 0.94 | Automatic HOLD | Notify compliance within 1 hour |
| 0.70 – 0.84 | Advisory flag — payment continues, analyst review required | Review within 4 hours |
| < 0.70 | Clear — no action | — |
| Exact string match | Automatic HOLD regardless of score | Notify compliance within 15 minutes |

Thresholds are configurable per corridor and payment value. High-value payments (>USD 1M equivalent) apply a lower advisory threshold of 0.65.

---

## PayInvestigator Demo Watchlist Entities

The following names are pre-loaded in the demo screening engine and will trigger HOLD events:

| Entity Name | List | Match Score | Notes |
|-------------|------|-------------|-------|
| Orion Global Resources FZE | OFAC SDN | 0.97 | Exact alias match |
| Kestrel Maritime Holdings Ltd | EU Consolidated | 0.93 | Primary name match |

These names are fictitious and used solely for demonstration purposes.

---

## Hold Procedure

When a payment is placed on a sanctions hold, the following steps must be completed in sequence:

1. **Freeze immediately** — set payment status to `HOLD`; no funds movement permitted.
2. **Log match details** — record: matched field, matched name value, watchlist name, match score, matched entity reference ID, and timestamp.
3. **Generate compliance case** — create an exception record with investigation type `SANCTIONS_HOLD`.
4. **Notify compliance officer** — within the SLA defined by the score band above; include the payment details and match evidence.
5. **Await written approval** — payment must not be released without documented compliance officer sign-off. Phone/verbal approval is insufficient.
6. **Record decision** — log the approver identity, approval timestamp, and rationale in the audit trail.

---

## Release Conditions

A sanctioned payment may only be released if:
- A compliance officer confirms the match is a false positive with documented evidence, OR
- A valid OFAC license (or equivalent regulatory authorisation) is on file for the transaction, OR
- The relevant authority has been notified as required by law (e.g. OFAC blocking report filed)

**Under no circumstances** may an agent, automated system, or operations staff release a sanctions hold without compliance officer approval.

---

## False Positive Handling

False positives are common due to common names, transliteration variants, and subsidiaries of sanctioned entities.

**Common causes:**
- Common name collision (e.g. "Ali Hassan" matching an SDN alias)
- Transliteration differences (Arabic, Cyrillic, Chinese names)
- Subsidiary or affiliated entity with similar name but no designation
- Historical designation subsequently removed from list

**Resolution steps:**
1. Collect supporting documentation: certificate of incorporation, passport/ID, corporate registry extract, trade documents.
2. Apply name disambiguation analysis: compare full legal name, date of birth, nationality, address, business sector with the watchlist entry.
3. If clearly different entities: document the analysis, record as `FALSE_POSITIVE`, release with compliance officer sign-off.
4. If uncertain after documentation review: escalate to Senior Compliance Officer.

**Escalation:**
- Unresolved within 4 hours → Senior Compliance Officer
- Unresolved within 24 hours → Chief Compliance Officer
- Potential true positive → Legal and Regulatory Affairs team

---

## Regulatory References

- OFAC 31 CFR Part 501 — Reporting, Procedures, and Penalties
- FATF Recommendation 6 — Targeted Financial Sanctions Related to Terrorism and Proliferation
- EU Regulation 2580/2001 — Specific restrictive measures against persons and entities
- Bank Secrecy Act 31 U.S.C. §5318(l) — Special due diligence requirements
- SWIFT CBPR+ guidelines: sanctions screening expected at both instructing and intermediary agent level
