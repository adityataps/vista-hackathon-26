package com.payinvestigator.ingest.filesystem;

import com.payinvestigator.ingest.config.FileSystemIngestProperties;
import com.payinvestigator.ingest.db.PaymentRepository;
import com.payinvestigator.ingest.resolution.ErrorResolutionAgent;
import com.payinvestigator.ingest.rules.ErrorHit;
import com.payinvestigator.ingest.rules.PaymentErrorDetector;
import com.payinvestigator.ingest.xml.Pacs008Parser;
import com.payinvestigator.ingest.xml.ParsedPayment;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;

/**
 * Local-filesystem equivalent of {@link com.payinvestigator.ingest.s3.S3PaymentPoller}:
 * watches {@code payment-ingest.filesystem.watch-dir}/{@code payments-subdir}
 * on a fixed schedule, and for every *.xml file not already recorded in the
 * payments table (keyed by a synthetic "key" - its path relative to
 * watchDir, mirroring an S3 key), parses it, runs error detection, and
 * inserts the row - then (if errors were found) invokes the AI resolution
 * agent. Lets the whole pipeline run locally with just Postgres, no AWS
 * dependency, by setting {@code payment-ingest.source=filesystem}.
 *
 * Files are left in place after processing (not moved/deleted) - the
 * already-ingested-keys check in Postgres is what prevents reprocessing, so
 * dropping a fresh batch of files into the watched folder while the service
 * is running is enough to trigger ingestion on the next poll cycle.
 */
@Service
@ConditionalOnProperty(name = "payment-ingest.source", havingValue = "filesystem")
public class FileSystemPaymentPoller {

    private static final Logger log = LoggerFactory.getLogger(FileSystemPaymentPoller.class);

    private final FileSystemIngestProperties props;
    private final PaymentRepository paymentRepository;
    private final LocalReferenceDataLoader referenceDataLoader;
    private final ErrorResolutionAgent errorResolutionAgent;

    private volatile LocalReferenceDataLoader.ReferenceData referenceData;

    public FileSystemPaymentPoller(FileSystemIngestProperties props, PaymentRepository paymentRepository,
                                    LocalReferenceDataLoader referenceDataLoader, ErrorResolutionAgent errorResolutionAgent) {
        this.props = props;
        this.paymentRepository = paymentRepository;
        this.referenceDataLoader = referenceDataLoader;
        this.errorResolutionAgent = errorResolutionAgent;
    }

    @Scheduled(fixedDelayString = "${payment-ingest.filesystem.poll-interval-ms:5000}")
    public void poll() {
        Path paymentsDir = Path.of(props.getWatchDir(), props.getPaymentsSubdir());
        if (!Files.isDirectory(paymentsDir)) {
            log.warn("Local payments dir '{}' does not exist - skipping poll cycle. " +
                    "Create it and drop pacs.008 *.xml files into it.", paymentsDir);
            return;
        }
        if (referenceData == null) {
            referenceData = referenceDataLoader.load();
        }

        Set<String> alreadyIngested = paymentRepository.findAllIngestedS3Keys();
        int processed = 0, failed = 0;

        List<Path> files;
        try (var stream = Files.list(paymentsDir)) {
            files = stream.filter(p -> p.toString().endsWith(".xml")).sorted().toList();
        } catch (IOException e) {
            log.error("Failed to list '{}': {}", paymentsDir, e.getMessage(), e);
            return;
        }

        for (Path file : files) {
            String key = props.getPaymentsSubdir() + "/" + file.getFileName();
            if (alreadyIngested.contains(key)) {
                continue;
            }
            try {
                processOne(key, file);
                processed++;
            } catch (Exception e) {
                log.error("failed to ingest '{}': {}", file, e.getMessage(), e);
                failed++;
            }
        }

        if (processed > 0 || failed > 0) {
            log.info("poll cycle complete: processed={}, failed={}", processed, failed);
        }
    }

    private void processOne(String key, Path file) throws IOException {
        String rawXml = Files.readString(file);

        ParsedPayment parsed;
        try {
            parsed = Pacs008Parser.parse(rawXml);
        } catch (Pacs008Parser.MalformedPaymentFileException e) {
            log.error("skipping unparseable file '{}': {}", file, e.getMessage());
            return;
        }

        List<String> existingUetrs = paymentRepository.findExistingUetrs(parsed.uetr);
        List<ErrorHit> hits = PaymentErrorDetector.detectErrors(
                parsed,
                referenceData.knownBics(),
                referenceData.watchlist(),
                referenceData.closedAccounts(),
                existingUetrs
        );
        String errorMsg = PaymentErrorDetector.formatErrorMsg(hits);
        boolean hasError = !hits.isEmpty();
        boolean isFaulty = file.getFileName().toString().toUpperCase().contains("FAULTY");

        Long paymentId = paymentRepository.insert(key, parsed, isFaulty, hasError, errorMsg, rawXml);
        log.info("ingested {} (msg_id={}, payment_id={}, has_error={})", key, parsed.msgId, paymentId, hasError);

        if (hasError) {
            errorResolutionAgent.investigate(key, paymentId, parsed, hits);
        }
    }
}
