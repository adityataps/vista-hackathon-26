# Payment Exception Error Code Catalog — SWIFT CBPR+ pacs.008

Reference catalog for AI-assisted payment exception investigation. Each entry describes detection logic, required fields, and resolution steps for errors encountered in pacs.008.001.08 CBPR+ SR2025 messages.

---

## IBAN_INVALID_CHECKSUM

**Category**: Account Identifier | **Severity**: High | **Investigation Type**: UTAP (Unable to Apply)

**Description**: The creditor IBAN contains an invalid check digit pair. The two-digit check value at positions 3–4 of the IBAN does not satisfy the ISO 7064 Mod-97-10 algorithm, indicating the IBAN was miskeyed, truncated, or corrupted in transit.

**Detection**: Apply ISO 7064 Mod-97: move the first 4 characters to the end, convert all letters to digits (A=10 … Z=35), compute the integer modulo 97. A valid IBAN yields remainder 1. Any other result is a checksum failure.

**Required Fields**:
- `CdtTrfTxInf/CdtrAcct/Id/IBAN`

**Suggested Action**:
1. Flag payment as UTAP; do not apply funds.
2. Issue camt.110 Request For Information to the debtor agent (DbtrAgt BIC) requesting the correct creditor IBAN.
3. Log the invalid IBAN and the computed remainder in the investigation record.
4. Await corrected IBAN; resubmit as a new pacs.008 with the original UETR preserved.

**Auto-Repairable**: No — the original correct IBAN cannot be derived from a corrupted value.

**Example**:
- Received: `DE89370400440532013000` (check digits `89` — remainder ≠ 1)
- Expected: `DE87370400440532013000` (check digits `87` — remainder = 1)

---

## IBAN_WRONG_LENGTH

**Category**: Account Identifier | **Severity**: High | **Investigation Type**: UTAP

**Description**: The creditor IBAN length does not match the expected length for the country code in positions 1–2, per the ISO 13616 country registry. The most common cause is truncation during data entry or system export.

**Detection**: Extract the two-character country code from IBAN positions 1–2. Look up the expected total IBAN length in the ISO 13616 registry (e.g. DE=22, GB=22, FR=27, NL=18). If `len(IBAN) ≠ expected`, raise this error.

**Required Fields**:
- `CdtTrfTxInf/CdtrAcct/Id/IBAN`

**Suggested Action**:
1. Flag payment as UTAP; do not apply funds.
2. Log the received IBAN, its actual length, and the expected length for the country.
3. Issue camt.110 RQST to DbtrAgt requesting the full, correct IBAN.
4. Do not attempt to pad or guess the missing digits.

**Auto-Repairable**: No.

**Example**:
- Received: `FR7630006000011234567890` (24 chars)
- Expected length for FR: 27 chars → 3 digits missing

---

## BIC_IBAN_COUNTRY_MISMATCH

**Category**: Account Identifier / Routing | **Severity**: High | **Investigation Type**: UTAP / Routing Clarification

**Description**: The country code embedded in the creditor agent BIC (positions 5–6) does not match the country code in the creditor IBAN (positions 1–2). This typically indicates that either the wrong BIC or the wrong IBAN was entered for the creditor.

**Detection**: Extract `BIC[4:6]` and `IBAN[0:2]`. If they differ, flag a mismatch. Note: legitimate exceptions exist for branch BICs of multinational banks — treat as a suspected error requiring confirmation, not a hard reject.

**Required Fields**:
- `CdtTrfTxInf/CdtrAgt/FinInstnId/BICFI`
- `CdtTrfTxInf/CdtrAcct/Id/IBAN`

**Suggested Action**:
1. Hold payment pending clarification.
2. Determine whether the error is in the BIC (wrong institution) or the IBAN (wrong account country).
3. Cross-reference the IBAN country with the BIC directory to identify the correct creditor agent.
4. If a clear correction is identified, propose the corrected routing for human approval before resubmission.
5. If ambiguous, issue camt.110 RQST to DbtrAgt.

**Auto-Repairable**: Partial — if the correct institution can be identified from the IBAN country, a routing correction can be proposed (requires human approval).

**Example**:
- CdtrAgt BIC: `DEUTDEDB` (DE = Germany)
- CdtrAcct IBAN: `NL91ABNA0417164300` (NL = Netherlands)
- Mismatch: BIC country DE ≠ IBAN country NL

---

## BIC_INVALID_COUNTRY

**Category**: Routing | **Severity**: High | **Investigation Type**: Routing / Possible Return

**Description**: The BIC for the creditor agent (or another agent field) contains a country code in positions 5–6 that does not exist in the ISO 3166-1 alpha-2 country list. This indicates the BIC is either fabricated, miskeyed, or corrupted.

**Detection**: Extract `BIC[4:6]`. Check against the static ISO 3166-1 alpha-2 country list (249 codes). If not found, raise this error. No external directory lookup required.

**Required Fields**:
- `CdtTrfTxInf/CdtrAgt/FinInstnId/BICFI`
- Any agent BIC field in AppHdr or CdtTrfTxInf

**Suggested Action**:
1. Hold payment; do not route.
2. Log the invalid BIC and the invalid country code substring.
3. Issue camt.110 RQST to DbtrAgt for the correct creditor agent BIC.
4. If no valid BIC can be identified, return the payment via pacs.004 with reject code RC01 (IncorrectAgentBIC).

**Auto-Repairable**: Partial — if institution code (BIC positions 1–4) is recognisable, a correct BIC may be derivable; requires human verification.

**Example**:
- Received BIC: `ZAPHZZ22XXX` — country code `ZZ` is not in ISO 3166

---

## BENEFICIARY_NAME_INCOMPLETE

**Category**: Beneficiary Data | **Severity**: Medium | **Investigation Type**: UTAP

**Description**: The creditor name field (`Cdtr/Nm`) contains only initials, a single token, or a placeholder value insufficient for name-account matching at the creditor agent. This violates CBPR+ expectations and will likely cause the receiving bank to return the payment.

**Detection**: Apply structural heuristics to `Cdtr/Nm`:
- Length < 5 characters
- Matches pattern `^[A-Z]\.$` (single initial with period)
- Single word with no spaces
- Known placeholders: `UNKNOWN`, `N/A`, `TEST`, `-`

**Required Fields**:
- `CdtTrfTxInf/Cdtr/Nm`

**Suggested Action**:
1. Flag as UTAP; place payment on hold.
2. Issue camt.110 RQST to DbtrAgt requesting the full legal name of the creditor.
3. Log the incomplete name received and the reason for the hold.
4. Upon receipt of the full name, update the payment record and resubmit for name-account matching.

**Auto-Repairable**: No — the full legal name must be obtained from the originating party.

**Example**:
- Received: `Cdtr/Nm = "P."`
- Expected: `"Petra Müller"` or equivalent full legal name

---

## ADDRESS_INCOMPLETE

**Category**: Beneficiary Data / Compliance | **Severity**: Medium | **Investigation Type**: RQFI (Compliance) / UTAP

**Description**: The creditor postal address contains only the country code with no town name or street address. This violates FATF Recommendation 16 (Travel Rule), which requires the originator and beneficiary address to be sufficiently complete for AML screening purposes.

**Detection**: Parse `Cdtr/PstlAdr`. Flag if:
- `TwnNm` is absent or empty AND `StrtNm`/`AdrLine` is absent or empty
- Only `Ctry` is present

**Required Fields**:
- `CdtTrfTxInf/Cdtr/PstlAdr/Ctry`
- `CdtTrfTxInf/Cdtr/PstlAdr/TwnNm`
- `CdtTrfTxInf/Cdtr/PstlAdr/StrtNm`

**Suggested Action**:
1. Flag for compliance review (RQFI).
2. Issue camt.110 RQST to DbtrAgt requesting a structured address (minimum: street, town, country).
3. Note that from CBPR+ SR2026, structured address will be mandatory — treat as a pre-emptive compliance flag.
4. Do not release payment until address is complete if AML policy requires it.

**Auto-Repairable**: No.

**Example**:
- Received: `<PstlAdr><Ctry>DE</Ctry></PstlAdr>`
- Expected: `<PstlAdr><StrtNm>Hauptstraße 12</StrtNm><TwnNm>Frankfurt</TwnNm><Ctry>DE</Ctry></PstlAdr>`

---

## DUPLICATE_UETR

**Category**: Duplicate | **Severity**: High | **Investigation Type**: Duplicate Clarification / Recall

**Description**: A payment message has been received with a UETR (Unique End-to-End Transaction Reference) that already exists in the transaction registry. Per SWIFT standards, UETRs must be globally unique per transaction; a repeat indicates either a duplicate submission or a UETR reuse error by the sender.

**Detection**: Query the transaction registry for the received `PmtId/UETR`. If a record exists, raise this error. The registry must cover at minimum the current processing day; best practice is a 13-month rolling window.

**Required Fields**:
- `CdtTrfTxInf/PmtId/UETR`

**Suggested Action**:
1. Hold the newly received payment immediately; do not settle.
2. Retrieve the original payment record matching the UETR.
3. Compare: debtor IBAN, creditor IBAN, amount, currency, value date, remittance info.
4. If all fields match → confirmed duplicate → issue camt.056 recall for the later message.
5. If fields differ → possible UETR reuse → escalate to DbtrAgt for clarification.
6. Return the duplicate payment with reject code AM05 (DuplicatePayment) if confirmed.

**Auto-Repairable**: No.

**Example**:
- First message: UETR `550e8400-e29b-41d4-a716-446655440000`, settled 09:14
- Second message: same UETR received 11:32 — held as duplicate

---

## XCHG_RATE_INCONSISTENT

**Category**: FX / Amount | **Severity**: Medium | **Investigation Type**: Clarification with Instructing Agent

**Description**: When a currency conversion is present, the instructed amount multiplied by the exchange rate deviates from the interbank settlement amount by more than the accepted tolerance (default 1%). This indicates an inconsistent rate, a rounding error, or a data entry mistake in one of the three amount fields.

**Detection**: If `InstdAmt` currency ≠ `IntrBkSttlmAmt` currency:
```
deviation = |InstdAmt × XchgRate − IntrBkSttlmAmt| / IntrBkSttlmAmt
if deviation > 0.01: raise XCHG_RATE_INCONSISTENT
```

**Required Fields**:
- `CdtTrfTxInf/InstdAmt` (with `Ccy` attribute)
- `CdtTrfTxInf/XchgRate`
- `CdtTrfTxInf/IntrBkSttlmAmt` (with `Ccy` attribute)

**Suggested Action**:
1. Flag for clarification; do not settle.
2. Log the three values received and the computed deviation percentage.
3. Issue camt.110 RQST to DbtrAgt requesting confirmation of the correct rate and settlement amount.
4. Consider rounding conventions (e.g. mid-market rate at cut-off time) before escalating.

**Auto-Repairable**: Partial — if the exchange rate is clearly erroneous (e.g. 0.5 when market rate is ~1.08), the correct rate can be proposed for approval.

**Example**:
- InstdAmt: USD 10,000 | XchgRate: 0.5 | IntrBkSttlmAmt: EUR 10,800
- Expected IntrBkSttlmAmt at rate 0.5: EUR 5,000 → deviation 116% → clearly inconsistent

---

## SANCTIONS_NAME_HIT

**Category**: Compliance | **Severity**: Critical | **Investigation Type**: Compliance Hold

**Description**: The creditor name (or another screened party) has matched an entry on a sanctions watchlist — OFAC SDN, EU Consolidated List, UK Financial Sanctions List (UKFSF/HMT), or UN Security Council Consolidated List — above the configured match threshold. Payment must be frozen immediately.

**Detection**: Fuzzy name matching against watchlist entries. Match score ≥ 0.85 triggers automatic HOLD. Exact matches trigger HOLD regardless of score. Screening covers `Cdtr/Nm`, `Dbtr/Nm`, and institution identifiers.

**Required Fields**:
- `CdtTrfTxInf/Cdtr/Nm`
- `CdtTrfTxInf/Dbtr/Nm`
- `CdtTrfTxInf/CdtrAgt/FinInstnId`

**Suggested Action**:
1. Freeze payment immediately — no funds movement under any circumstances.
2. Log the matched name, the watchlist entry, the match score, and the timestamp.
3. Generate a compliance case and notify the Compliance Officer within 1 hour.
4. Do not release the payment without written Compliance Officer approval.
5. If a false positive is suspected, obtain supporting documentation (incorporation certificate, passport copy) and apply name disambiguation analysis.
6. All decisions must be recorded in the audit trail with the approver's identity.

**Auto-Repairable**: No — human compliance approval is mandatory.

**Example**:
- `Cdtr/Nm = "Orion Global Resources FZE"` — OFAC SDN match, score 0.97

---

## ACCOUNT_CLOSED

**Category**: Account Identifier | **Severity**: High | **Investigation Type**: UTAP / Return

**Description**: The creditor account identified by the IBAN has been marked as closed in the beneficiary bank's account records. The payment cannot be credited and must be returned or redirected.

**Detection**: Lookup the creditor IBAN against the beneficiary bank account status database. If status is `CLOSED` or `DORMANT`, raise this error. (In PayInvestigator demo: closed accounts are pre-loaded in the reference dataset.)

**Required Fields**:
- `CdtTrfTxInf/CdtrAcct/Id/IBAN`

**Suggested Action**:
1. Flag as UTAP; do not credit funds.
2. Issue camt.110 RQST to DbtrAgt requesting an updated creditor account.
3. If no response within SLA: return payment via pacs.004 with reject code AC04 (ClosedAccountNumber).
4. Log the closed IBAN, the detection source, and the return action in the audit trail.

**Auto-Repairable**: No — a valid replacement account must be provided by the originating party.

**Example**:
- `CdtrAcct/Id/IBAN = "CH9300762011623852957"` — status: CLOSED as of 2025-03-01
