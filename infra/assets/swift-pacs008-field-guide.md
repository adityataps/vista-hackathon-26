# SWIFT CBPR+ pacs.008.001.08 Field Reference Guide

The `pacs.008` FIToFICustomerCreditTransfer is the primary interbank credit transfer message in the SWIFT CBPR+ (Cross-Border Payments and Reporting Plus) framework. This guide covers key fields, CBPR+-specific constraints, and validation rules for SR2025.

---

## Message Structure

A CBPR+ pacs.008 consists of two blocks:
- **AppHdr** (`head.001.001.02`) — Business Application Header carrying routing and service metadata
- **Document** (`pacs.008.001.08`) — Payment instruction body

Both blocks are wrapped in a single XML envelope. The `BizSvc` value in AppHdr identifies the service: `swift.cbprplus.03` for CBPR+ SR2025.

---

## AppHdr Key Fields

| Field | XPath | Description | CBPR+ Rule |
|-------|-------|-------------|------------|
| BizMsgIdr | `AppHdr/BizMsgIdr` | Business message identifier | Max 35 chars; unique per sender per day |
| MsgDefIdr | `AppHdr/MsgDefIdr` | Message definition identifier | Must be `pacs.008.001.08` |
| BizSvc | `AppHdr/BizSvc` | Business service | `swift.cbprplus.03` (SR2025) |
| Fr BICFI | `AppHdr/Fr/FIId/FinInstnId/BICFI` | Sending institution BIC | Valid 8 or 11-char BIC; ISO 9362 |
| To BICFI | `AppHdr/To/FIId/FinInstnId/BICFI` | Receiving institution BIC | Valid 8 or 11-char BIC |
| CreDt | `AppHdr/CreDt` | Creation datetime | ISO 8601 with timezone |

---

## Payment Identification Fields

| Field | XPath | Description | Constraint |
|-------|-------|-------------|------------|
| InstrId | `CdtTrfTxInf/PmtId/InstrId` | Instruction ID (sender's reference) | **Max 16 chars** in CBPR+ (stricter than base ISO 35) |
| EndToEndId | `CdtTrfTxInf/PmtId/EndToEndId` | End-to-end ID (originator's reference) | Max 35 chars; carried unchanged through the chain |
| UETR | `CdtTrfTxInf/PmtId/UETR` | Unique End-to-End Transaction Reference | UUID v4 format; globally unique; mandatory in CBPR+ |
| TxId | `CdtTrfTxInf/PmtId/TxId` | Transaction ID | Max 35 chars; set by first agent |

---

## Amount and FX Fields

| Field | XPath | Description | Validation |
|-------|-------|-------------|------------|
| IntrBkSttlmAmt | `CdtTrfTxInf/IntrBkSttlmAmt` | Interbank settlement amount | `Ccy` attribute = ISO 4217; max 2 decimal places for most currencies |
| IntrBkSttlmDt | `CdtTrfTxInf/IntrBkSttlmDt` | Value / settlement date | ISO 8601 date (`YYYY-MM-DD`) |
| InstdAmt | `CdtTrfTxInf/InstdAmt` | Instructed amount (before FX) | Present only when FX conversion applies |
| XchgRate | `CdtTrfTxInf/XchgRate` | Exchange rate applied | `InstdAmt × XchgRate` must ≈ `IntrBkSttlmAmt` (±1% tolerance) |
| ChrgBr | `CdtTrfTxInf/ChrgBr` | Charge bearer | `SLEV` (follows service level), `DEBT`, `CRED`, `SHAR` |

---

## Debtor Fields

| Field | XPath | Description | Validation |
|-------|-------|-------------|------------|
| DbtrAgt BICFI | `CdtTrfTxInf/DbtrAgt/FinInstnId/BICFI` | Debtor's bank BIC | Valid ISO 9362 BIC |
| Dbtr/Nm | `CdtTrfTxInf/Dbtr/Nm` | Debtor name | Max 140 chars |
| Dbtr/PstlAdr | `CdtTrfTxInf/Dbtr/PstlAdr` | Debtor postal address | TwnNm + Ctry minimum (FATF R.16) |
| DbtrAcct IBAN | `CdtTrfTxInf/DbtrAcct/Id/IBAN` | Debtor account IBAN | Must pass ISO 7064 Mod-97 |
| DbtrAcct Othr | `CdtTrfTxInf/DbtrAcct/Id/Othr/Id` | Debtor account (non-IBAN) | Used when IBAN not applicable |

---

## Creditor Fields

| Field | XPath | Description | Validation |
|-------|-------|-------------|------------|
| CdtrAgt BICFI | `CdtTrfTxInf/CdtrAgt/FinInstnId/BICFI` | Creditor's bank BIC | Country code (BIC[4:6]) must match IBAN country (IBAN[0:2]) |
| Cdtr/Nm | `CdtTrfTxInf/Cdtr/Nm` | Creditor name | Full legal name required; initials/placeholders not acceptable |
| Cdtr/PstlAdr | `CdtTrfTxInf/Cdtr/PstlAdr` | Creditor postal address | `TwnNm` + `Ctry` minimum; `StrtNm` required from SR2026 |
| CdtrAcct IBAN | `CdtTrfTxInf/CdtrAcct/Id/IBAN` | Creditor account IBAN | Length must match ISO 13616 country table; Mod-97 must pass |
| CdtrAcct Othr | `CdtTrfTxInf/CdtrAcct/Id/Othr/Id` | Creditor account (non-IBAN) | Used for non-SEPA corridors |

---

## Remittance and Purpose

| Field | XPath | Description | Constraint |
|-------|-------|-------------|------------|
| RmtInf/Ustrd | `CdtTrfTxInf/RmtInf/Ustrd` | Unstructured remittance info | Max 140 chars |
| RmtInf/Strd | `CdtTrfTxInf/RmtInf/Strd` | Structured remittance | ISO 11649 creditor reference or invoice details |
| Purp/Cd | `CdtTrfTxInf/Purp/Cd` | Purpose code | ISO 20022 ExternalPurpose1Code (e.g. SALA, SUPP, TAXS) |

---

## CBPR+ SR2025 Compliance Rules

- **UETR mandatory** — all CBPR+ messages must carry a UUID v4 UETR since SR2016; rejection code `FF01` if absent.
- **BizSvc mandatory** — `swift.cbprplus.03` in AppHdr required from SR2025; `swift.cbprplus.02` for SR2023 messages still in transit.
- **InstrId max 16 chars** — CBPR+ imposes a stricter 16-char limit vs. the base ISO 20022 35-char limit.
- **Structured address** — TwnNm + Ctry required; full structured address (including StrtNm) becomes mandatory in SR2026 per FATF Travel Rule alignment.
- **ChrgBr = SLEV** — required for most CBPR+ bilateral and multilateral corridors; `DEBT`/`CRED`/`SHAR` only where bilaterally agreed.
- **FX fields** — if `InstdAmt` is present, `XchgRate` must also be present; both absent is valid (no FX).

---

## Status Code Reference

| Code | Full Name | Meaning | Typical Trigger |
|------|-----------|---------|-----------------|
| RCVD | Received | Message accepted by receiving agent | Initial receipt |
| ACTC | AcceptedTechnicalValidation | XSD/format validation passed | Format check complete |
| ACSP | AcceptedSettlementInProcess | Settlement underway | Routing/correspondent engaged |
| ACWP | AcceptedWithoutPosting | Funds received but not credited | Pending beneficiary confirmation |
| ACCC | AcceptedCreditSettlementCompleted | Credited to beneficiary account | Settlement confirmed |
| HOLD | On Hold | Payment suspended | Sanctions, compliance, or duplicate hold |
| RJCT | Rejected | Payment rejected | Business validation failure |
| PDNG | Pending | Awaiting further information | UTAP / clarification request outstanding |
