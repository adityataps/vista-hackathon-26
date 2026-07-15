package com.payinvestigator.ingest;

import com.payinvestigator.ingest.rules.ErrorHit;
import com.payinvestigator.ingest.rules.PaymentErrorDetector;
import com.payinvestigator.ingest.xml.Pacs008Parser;
import com.payinvestigator.ingest.xml.ParsedPayment;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Parity test against the real sample pacs.008 files used across all three
 * PayInvestigator implementations (Python Lambda x2, this Spring service).
 * Confirms the same 6 FAULTY files are flagged with the expected error code
 * and every OK file (other than the intentional 020 duplicate pair) is clean.
 */
class Pacs008ParserAndErrorDetectorParityTest {

    private static final Path SAMPLE_DIR =
            Path.of("C:\\Users\\u727254\\Desktop\\VISTA - hack\\payment-files");

    private static final Map<String, String> EXPECTED_ERROR_BY_FILE = Map.of(
            "003_pacs008_FAULTY.xml", "BENEFICIARY_NAME_INCOMPLETE",
            "019_pacs008_FAULTY.xml", "BENEFICIARY_NAME_INCOMPLETE",
            "004_pacs008_FAULTY.xml", "IBAN_WRONG_LENGTH",
            "017_pacs008_FAULTY.xml", "IBAN_WRONG_LENGTH",
            "005_pacs008_FAULTY.xml", "DUPLICATE_UETR",
            "010_pacs008_FAULTY.xml", "BIC_IBAN_COUNTRY_MISMATCH"
    );

    @Test
    void allSampleFilesMatchExpectedErrorClassification() throws IOException {
        assertTrue(Files.isDirectory(SAMPLE_DIR), "Sample payment-files directory must exist: " + SAMPLE_DIR);

        List<Path> files = new ArrayList<>();
        try (var stream = Files.list(SAMPLE_DIR)) {
            stream.filter(p -> p.toString().endsWith(".xml")).sorted().forEach(files::add);
        }
        assertEquals(21, files.size(), "Expected 21 sample xml files (20 unique + 1 duplicate)");

        List<String> seenUetrs = new ArrayList<>();
        Map<String, String> actualErrorByFile = new TreeMap<>();

        for (Path file : files) {
            String rawXml = Files.readString(file);
            ParsedPayment parsed = Pacs008Parser.parse(rawXml);

            List<ErrorHit> hits = PaymentErrorDetector.detectErrors(parsed, null, null, null, seenUetrs);
            if (!hits.isEmpty()) {
                // A file can legitimately trip more than one rule (e.g. a
                // wrong-length IBAN also fails its mod-97 checksum); record
                // all codes and just check the expected one is among them.
                actualErrorByFile.put(file.getFileName().toString(),
                        hits.stream().map(ErrorHit::code).reduce((a, b) -> a + "," + b).orElse(""));
            }
            seenUetrs.add(parsed.uetr);
        }

        for (var expected : EXPECTED_ERROR_BY_FILE.entrySet()) {
            String actual = actualErrorByFile.get(expected.getKey());
            assertTrue(actual != null && actual.contains(expected.getValue()),
                    "Mismatch for file " + expected.getKey() + ": expected to contain " + expected.getValue() + " but was " + actual);
        }

        // Exactly one of the byte-identical 020 duplicate pair should be flagged
        // as DUPLICATE_UETR (whichever is processed second, depending on file
        // listing order) - the other is the original, clean file.
        long duplicate020Count = actualErrorByFile.entrySet().stream()
                .filter(e -> e.getKey().startsWith("020_pacs008_OK") && e.getValue().contains("DUPLICATE_UETR"))
                .count();
        assertEquals(1, duplicate020Count, "Expected exactly one of the 020 duplicate-UETR files to be flagged: " + actualErrorByFile);

        assertEquals(EXPECTED_ERROR_BY_FILE.size() + 1, actualErrorByFile.size(),
                "Unexpected extra/missing error classifications: " + actualErrorByFile);
    }
}
