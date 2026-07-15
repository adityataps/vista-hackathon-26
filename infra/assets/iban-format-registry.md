# IBAN Format Registry — ISO 13616 Country Reference

The International Bank Account Number (IBAN) is structured as `CC DD BBAN`: two-character ISO 3166 country code, two-digit check pair, and the Basic Bank Account Number (BBAN) whose length and structure varies by country. Total IBAN length = 2 + 2 + BBAN length.

---

## Length and Structure by Country

| Country | Code | Length | BBAN Structure | Fictional Example |
|---------|------|--------|----------------|-------------------|
| Albania | AL | 28 | 8n 16c | AL47212110090000000235698741 |
| Andorra | AD | 24 | 4n 4n 12c | AD1200012030200359100100 |
| Austria | AT | 20 | 5n 11n | AT611904300234573201 |
| Belgium | BE | 16 | 3n 7n 2n | BE68539007547034 |
| Bosnia & Herzegovina | BA | 20 | 3n 3n 8n 2n | BA391290079401028494 |
| Bulgaria | BG | 22 | 4a 4n 2n 8c | BG80BNBG96611020345678 |
| Croatia | HR | 21 | 7n 10n | HR1210010051863000160 |
| Cyprus | CY | 28 | 3n 5n 16c | CY17002001280000001200527600 |
| Czech Republic | CZ | 24 | 4n 6n 10n | CZ6508000000192000145399 |
| Denmark | DK | 18 | 4n 9n 1n | DK5000400440116243 |
| Estonia | EE | 20 | 2n 2n 11n 1n | EE382200221020145685 |
| Finland | FI | 18 | 6n 7n 1n | FI2112345600000785 |
| France | FR | 27 | 5n 5n 11c 2n | FR7630006000011234567890189 |
| Germany | DE | 22 | 8n 10n | DE89370400440532013000 |
| Gibraltar | GI | 23 | 4a 15c | GI75NWBK000000007099453 |
| Greece | GR | 27 | 3n 4n 16c | GR1601101250000000012300695 |
| Hungary | HU | 28 | 3n 4n 1n 15n 1n | HU42117730161111101800000000 |
| Iceland | IS | 26 | 4n 2n 6n 10n | IS140159260076545510730339 |
| Ireland | IE | 22 | 4a 6n 8n | IE29AIBK93115212345678 |
| Israel | IL | 23 | 3n 3n 13n | IL620108000000099999999 |
| Italy | IT | 27 | 1a 5n 5n 12c | IT60X0542811101000000123456 |
| Latvia | LV | 21 | 4a 13c | LV80BANK0000435195001 |
| Liechtenstein | LI | 21 | 5n 12c | LI21088100002324013AA |
| Lithuania | LT | 20 | 5n 11n | LT121000011101001000 |
| Luxembourg | LU | 20 | 3n 13c | LU280019400644750000 |
| Malta | MT | 31 | 4a 5n 18c | MT84MALT011000012345MTLCAST001S |
| Monaco | MC | 27 | 5n 5n 11c 2n | MC5811222000010123456789030 |
| Netherlands | NL | 18 | 4a 10n | NL91ABNA0417164300 |
| Norway | NO | 15 | 4n 6n 1n | NO9386011117947 |
| Poland | PL | 28 | 8n 16n | PL61109010140000071219812874 |
| Portugal | PT | 25 | 4n 4n 11n 2n | PT50000201231234567890154 |
| Romania | RO | 24 | 4a 16c | RO49AAAA1B31007593840000 |
| San Marino | SM | 27 | 1a 5n 5n 12c | SM86U0322509800000000270100 |
| Saudi Arabia | SA | 24 | 2n 18c | SA0380000000608010167519 |
| Slovakia | SK | 24 | 4n 6n 10n | SK3112000000198742637541 |
| Slovenia | SI | 19 | 5n 8n 2n | SI56263300012039086 |
| Spain | ES | 24 | 4n 4n 1n 1n 10n | ES9121000418450200051332 |
| Sweden | SE | 24 | 3n 16n 1n | SE4550000000058398257466 |
| Switzerland | CH | 21 | 5n 12c | CH9300762011623852957 |
| United Arab Emirates | AE | 23 | 3n 16n | AE070331234567890123456 |
| United Kingdom | GB | 22 | 4a 6n 8n | GB29NWBK60161331926819 |

*n = numeric digit, a = uppercase letter, c = alphanumeric character*

---

## Validation Algorithm (ISO 7064 Mod-97)

1. **Rearrange** — move the first 4 characters (country + check digits) to the end.
   `DE89370400440532013000` → `370400440532013000DE89`

2. **Convert letters to digits** — A=10, B=11, C=12 … Z=35.
   `DE` → `1314`; `370400440532013000131489`

3. **Compute mod 97** — treat the full string as an integer; valid IBAN yields remainder **1**.

> **Implementation tip:** Process in 9-digit chunks to avoid integer overflow in languages without big integers: carry the running remainder forward as `(current_chunk + remainder_prefix) % 97`.

---

## Common Errors by Region

**Germany (DE, 22 chars)**
BLZ (sort code, digits 1–8 of BBAN) sometimes entered without account number suffix → produces short IBAN. Database truncation to 20 chars is also common; both raise `IBAN_WRONG_LENGTH`.

**France (FR, 27 chars)**
Display format includes spaces every 4 chars — strip before validation. RIB key (last 2 BBAN digits) occasionally omitted, yielding 25-char IBAN.

**United Kingdom (GB, 22 chars)**
Sort code frequently entered with hyphens (`20-00-00`) — strip. Legacy 7-digit account numbers need left-padding to 8 digits with `0`.

**Netherlands (NL, 18 chars)**
Old 9-digit account numbers must be left-padded to 10 before IBAN construction; failure to pad produces an 18-char string with a wrong checksum.

**Switzerland (CH, 21 chars)**
5-digit clearing number after country+check must match the bank's registered ID. PostFinance IBANs start with `CH93` — sometimes misrouted.

**SEPA general**
BIC country code (BIC[4:6]) must match IBAN country code (IBAN[0:2]) for standard corridors. Mismatches raise `BIC_IBAN_COUNTRY_MISMATCH`. Exception: branch BICs of multinational banks may legitimately differ.
