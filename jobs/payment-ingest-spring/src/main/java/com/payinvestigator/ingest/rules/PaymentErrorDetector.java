package com.payinvestigator.ingest.rules;

import com.payinvestigator.ingest.xml.ParsedPayment;

import java.math.BigDecimal;
import java.math.MathContext;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Business-rule error detection for pacs.008 payments, ported from
 * jobs/pacs008-generator/agent_error_knowledge.yaml (see also the Python
 * twin of this logic in jobs/payment-ingest/error_rules.py).
 *
 * Reference-data-backed checks (BIC directory / sanctions watchlist / closed
 * accounts / already-seen UETRs) are skipped gracefully when the
 * corresponding collection is null or empty, so this class works standalone
 * without any external lookups wired up.
 */
public final class PaymentErrorDetector {

    // ISO 13616 IBAN length by country code (extend as needed).
    private static final Map<String, Integer> IBAN_LENGTH_BY_COUNTRY = Map.ofEntries(
            Map.entry("AD", 24), Map.entry("AT", 20), Map.entry("BE", 16), Map.entry("CH", 21),
            Map.entry("CY", 28), Map.entry("CZ", 24), Map.entry("DE", 22), Map.entry("DK", 18),
            Map.entry("EE", 20), Map.entry("ES", 24), Map.entry("FI", 18), Map.entry("FR", 27),
            Map.entry("GB", 22), Map.entry("GR", 27), Map.entry("HU", 28), Map.entry("IE", 22),
            Map.entry("IS", 26), Map.entry("IT", 27), Map.entry("LI", 21), Map.entry("LU", 20),
            Map.entry("LV", 21), Map.entry("MC", 27), Map.entry("MT", 31), Map.entry("NL", 18),
            Map.entry("NO", 15), Map.entry("PL", 28), Map.entry("PT", 25), Map.entry("SE", 24),
            Map.entry("SI", 19), Map.entry("SK", 24), Map.entry("SM", 27)
    );

    private static final Pattern IBAN_SHAPE = Pattern.compile("^[A-Za-z]{2}\\d.*");
    private static final Pattern INCOMPLETE_NAME = Pattern.compile("^[A-Z]\\.$");
    private static final Set<String> PLACEHOLDER_NAMES = Set.of("UNKNOWN", "N/A", "NA", "TBD");
    private static final double SANCTIONS_MATCH_THRESHOLD = 0.85;
    private static final BigDecimal XCHG_RATE_TOLERANCE = new BigDecimal("0.01"); // 1%

    private PaymentErrorDetector() {
    }

    public static List<ErrorHit> detectErrors(
            ParsedPayment p,
            Set<String> knownBics,
            Collection<String> watchlist,
            Collection<String> closedAccounts,
            Collection<String> existingUetrs
    ) {
        List<ErrorHit> hits = new ArrayList<>();

        checkIbanChecksum(p).ifPresent(hits::add);
        checkBeneficiaryNameIncomplete(p).ifPresent(hits::add);
        checkAddressIncomplete(p).ifPresent(hits::add);
        checkXchgRateInconsistent(p).ifPresent(hits::add);

        hits.addAll(checkIbanLength(p));
        hits.addAll(checkBicIbanCountryMismatch(p));
        hits.addAll(checkBicUnknown(p, knownBics));
        hits.addAll(checkSanctionsNameHit(p, watchlist));

        checkDuplicateUetr(p, existingUetrs).ifPresent(hits::add);
        checkAccountClosed(p, closedAccounts).ifPresent(hits::add);

        return hits;
    }

    public static String formatErrorMsg(List<ErrorHit> hits) {
        if (hits.isEmpty()) {
            return null;
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < hits.size(); i++) {
            if (i > 0) sb.append("; ");
            sb.append(hits.get(i));
        }
        return sb.toString();
    }

    // ── IBAN checksum (ISO 7064 mod-97) ────────────────────────────────────

    private static boolean isIbanShaped(String value) {
        return value != null && IBAN_SHAPE.matcher(value).matches();
    }

    private static boolean ibanMod97Valid(String iban) {
        String cleaned = iban.replace(" ", "").toUpperCase();
        if (cleaned.length() < 4) {
            return false;
        }
        String rearranged = cleaned.substring(4) + cleaned.substring(0, 4);
        StringBuilder expanded = new StringBuilder();
        for (char c : rearranged.toCharArray()) {
            if (Character.isLetter(c)) {
                expanded.append(Character.getNumericValue(c));
            } else if (Character.isDigit(c)) {
                expanded.append(c);
            } else {
                return false;
            }
        }
        try {
            return new java.math.BigInteger(expanded.toString()).mod(java.math.BigInteger.valueOf(97))
                    .equals(java.math.BigInteger.ONE);
        } catch (NumberFormatException e) {
            return false;
        }
    }

    private static java.util.Optional<ErrorHit> checkIbanChecksum(ParsedPayment p) {
        String iban = p.creditorIban != null ? p.creditorIban : p.debtorIban;
        if (!isIbanShaped(iban)) {
            return java.util.Optional.empty();
        }
        if (!ibanMod97Valid(iban)) {
            return java.util.Optional.of(new ErrorHit("IBAN_INVALID_CHECKSUM",
                    "IBAN '" + iban + "' fails ISO 7064 mod-97 checksum validation."));
        }
        return java.util.Optional.empty();
    }

    // ── IBAN length per country ─────────────────────────────────────────────

    private static List<ErrorHit> checkIbanLength(ParsedPayment p) {
        List<ErrorHit> hits = new ArrayList<>();
        checkOneIbanLength("debtor_iban", p.debtorIban).ifPresent(hits::add);
        checkOneIbanLength("creditor_iban", p.creditorIban).ifPresent(hits::add);
        return hits;
    }

    private static java.util.Optional<ErrorHit> checkOneIbanLength(String fieldName, String iban) {
        if (!isIbanShaped(iban)) {
            return java.util.Optional.empty();
        }
        String country = iban.substring(0, 2).toUpperCase();
        Integer expected = IBAN_LENGTH_BY_COUNTRY.get(country);
        if (expected != null && iban.length() != expected) {
            return java.util.Optional.of(new ErrorHit("IBAN_WRONG_LENGTH",
                    fieldName + " '" + iban + "' has length " + iban.length()
                            + ", expected " + expected + " for country " + country + "."));
        }
        return java.util.Optional.empty();
    }

    // ── BIC / IBAN country mismatch ─────────────────────────────────────────

    private static List<ErrorHit> checkBicIbanCountryMismatch(ParsedPayment p) {
        List<ErrorHit> hits = new ArrayList<>();
        checkOnePair("debtor_bic", p.debtorBic, "debtor_iban", p.debtorIban).ifPresent(hits::add);
        checkOnePair("creditor_bic", p.creditorBic, "creditor_iban", p.creditorIban).ifPresent(hits::add);
        return hits;
    }

    private static java.util.Optional<ErrorHit> checkOnePair(String bicField, String bic, String ibanField, String iban) {
        if (bic == null || bic.length() < 6 || !isIbanShaped(iban)) {
            return java.util.Optional.empty();
        }
        String bicCountry = bic.substring(4, 6).toUpperCase();
        String ibanCountry = iban.substring(0, 2).toUpperCase();
        if (!bicCountry.equals(ibanCountry)) {
            return java.util.Optional.of(new ErrorHit("BIC_IBAN_COUNTRY_MISMATCH",
                    bicField + " '" + bic + "' country (" + bicCountry + ") does not match "
                            + ibanField + " '" + iban + "' country (" + ibanCountry + ")."));
        }
        return java.util.Optional.empty();
    }

    // ── BIC directory lookup ─────────────────────────────────────────────────

    private static List<ErrorHit> checkBicUnknown(ParsedPayment p, Set<String> knownBics) {
        List<ErrorHit> hits = new ArrayList<>();
        if (knownBics == null || knownBics.isEmpty()) {
            return hits;
        }
        Map<String, String> fields = Map.of(
                "sender_bic", nullToEmpty(p.senderBic),
                "receiver_bic", nullToEmpty(p.receiverBic),
                "debtor_bic", nullToEmpty(p.debtorBic),
                "creditor_bic", nullToEmpty(p.creditorBic)
        );
        for (var entry : fields.entrySet()) {
            String bic = entry.getValue();
            if (!bic.isEmpty() && !knownBics.contains(bic)) {
                hits.add(new ErrorHit("BIC_UNKNOWN",
                        entry.getKey() + " '" + bic + "' is not present in the active BIC directory."));
            }
        }
        return hits;
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }

    // ── Incomplete beneficiary name ─────────────────────────────────────────

    private static boolean isIncompleteName(String name) {
        String trimmed = name.strip();
        if (trimmed.length() < 5) return true;
        if (INCOMPLETE_NAME.matcher(trimmed).matches()) return true;
        if (PLACEHOLDER_NAMES.contains(trimmed.toUpperCase())) return true;
        return !trimmed.contains(" ") && trimmed.length() < 8;
    }

    private static java.util.Optional<ErrorHit> checkBeneficiaryNameIncomplete(ParsedPayment p) {
        if (p.creditorName != null && isIncompleteName(p.creditorName)) {
            return java.util.Optional.of(new ErrorHit("BENEFICIARY_NAME_INCOMPLETE",
                    "Cdtr/Nm '" + p.creditorName + "' looks incomplete (too short / initials only / placeholder)."));
        }
        return java.util.Optional.empty();
    }

    // ── Incomplete beneficiary address ──────────────────────────────────────

    private static java.util.Optional<ErrorHit> checkAddressIncomplete(ParsedPayment p) {
        boolean hasCountryOnly = p.creditorCtry != null && !p.creditorCtry.isBlank()
                && (p.creditorTwnNm == null || p.creditorTwnNm.isBlank())
                && (p.creditorStrtNm == null || p.creditorStrtNm.isBlank());
        if (hasCountryOnly) {
            return java.util.Optional.of(new ErrorHit("ADDRESS_INCOMPLETE",
                    "Cdtr/PstlAdr only has Ctry populated; missing TwnNm/StrtNm/AdrLine."));
        }
        return java.util.Optional.empty();
    }

    // ── Duplicate UETR ───────────────────────────────────────────────────────

    private static java.util.Optional<ErrorHit> checkDuplicateUetr(ParsedPayment p, Collection<String> existingUetrs) {
        if (existingUetrs == null || existingUetrs.isEmpty() || p.uetr == null) {
            return java.util.Optional.empty();
        }
        if (existingUetrs.contains(p.uetr)) {
            return java.util.Optional.of(new ErrorHit("DUPLICATE_UETR",
                    "UETR '" + p.uetr + "' already exists in the payments table (possible duplicate submission)."));
        }
        return java.util.Optional.empty();
    }

    // ── FX consistency (InstdAmt * XchgRate vs IntrBkSttlmAmt) ──────────────

    private static java.util.Optional<ErrorHit> checkXchgRateInconsistent(ParsedPayment p) {
        if (p.instdAmt == null || p.xchgRate == null || p.amount == null) {
            return java.util.Optional.empty();
        }
        if (p.instdAmtCcy != null && p.currency != null && p.instdAmtCcy.equals(p.currency)) {
            return java.util.Optional.empty();
        }
        if (p.amount.compareTo(BigDecimal.ZERO) == 0) {
            return java.util.Optional.empty();
        }
        BigDecimal rate;
        try {
            rate = new BigDecimal(p.xchgRate);
        } catch (NumberFormatException e) {
            return java.util.Optional.empty();
        }
        BigDecimal expected = p.instdAmt.multiply(rate);
        BigDecimal deviation = expected.subtract(p.amount).abs()
                .divide(p.amount, MathContext.DECIMAL64);
        if (deviation.compareTo(XCHG_RATE_TOLERANCE) > 0) {
            return java.util.Optional.of(new ErrorHit("XCHG_RATE_INCONSISTENT",
                    "InstdAmt(" + p.instdAmt + ") * XchgRate(" + rate + ") = " + expected
                            + ", deviates " + deviation.multiply(BigDecimal.valueOf(100)) + "% from IntrBkSttlmAmt("
                            + p.amount + ") - exceeds 1% tolerance."));
        }
        return java.util.Optional.empty();
    }

    // ── Sanctions watchlist (fuzzy name match) ──────────────────────────────

    private static List<ErrorHit> checkSanctionsNameHit(ParsedPayment p, Collection<String> watchlist) {
        List<ErrorHit> hits = new ArrayList<>();
        if (watchlist == null || watchlist.isEmpty()) {
            return hits;
        }
        matchWatchlist(p.creditorName, watchlist).ifPresent(match -> hits.add(new ErrorHit("SANCTIONS_NAME_HIT",
                "creditor_name '" + p.creditorName + "' fuzzy-matches watchlist entry '" + match + "'.")));
        matchWatchlist(p.debtorName, watchlist).ifPresent(match -> hits.add(new ErrorHit("SANCTIONS_NAME_HIT",
                "debtor_name '" + p.debtorName + "' fuzzy-matches watchlist entry '" + match + "'.")));
        return hits;
    }

    private static java.util.Optional<String> matchWatchlist(String name, Collection<String> watchlist) {
        if (name == null || name.isBlank()) {
            return java.util.Optional.empty();
        }
        String normalized = name.strip().toLowerCase();
        for (String entry : watchlist) {
            double score = similarity(normalized, entry.strip().toLowerCase());
            if (score >= SANCTIONS_MATCH_THRESHOLD) {
                return java.util.Optional.of(entry);
            }
        }
        return java.util.Optional.empty();
    }

    /** Normalized string similarity in [0,1], based on Levenshtein edit distance
     * (a reasonable stand-in for Python's difflib.SequenceMatcher ratio used
     * in the reference implementation). */
    private static double similarity(String a, String b) {
        if (a.isEmpty() && b.isEmpty()) return 1.0;
        int distance = levenshtein(a, b);
        int maxLen = Math.max(a.length(), b.length());
        return maxLen == 0 ? 1.0 : 1.0 - ((double) distance / maxLen);
    }

    private static int levenshtein(String a, String b) {
        int[][] dp = new int[a.length() + 1][b.length() + 1];
        for (int i = 0; i <= a.length(); i++) dp[i][0] = i;
        for (int j = 0; j <= b.length(); j++) dp[0][j] = j;
        for (int i = 1; i <= a.length(); i++) {
            for (int j = 1; j <= b.length(); j++) {
                int cost = a.charAt(i - 1) == b.charAt(j - 1) ? 0 : 1;
                dp[i][j] = Math.min(Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1), dp[i - 1][j - 1] + cost);
            }
        }
        return dp[a.length()][b.length()];
    }

    // ── Closed account lookup ────────────────────────────────────────────────

    private static java.util.Optional<ErrorHit> checkAccountClosed(ParsedPayment p, Collection<String> closedAccounts) {
        if (closedAccounts == null || closedAccounts.isEmpty() || p.creditorIban == null) {
            return java.util.Optional.empty();
        }
        if (closedAccounts.contains(p.creditorIban)) {
            return java.util.Optional.of(new ErrorHit("ACCOUNT_CLOSED",
                    "Beneficiary account '" + p.creditorIban + "' is marked closed in the account-status reference data."));
        }
        return java.util.Optional.empty();
    }
}
