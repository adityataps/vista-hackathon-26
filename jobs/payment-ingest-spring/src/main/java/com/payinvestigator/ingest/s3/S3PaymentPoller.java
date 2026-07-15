package com.payinvestigator.ingest.s3;

import com.payinvestigator.ingest.config.S3IngestProperties;
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
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Request;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Response;
import software.amazon.awssdk.services.s3.model.S3Object;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;

/**
 * Polls the configured S3 bucket/prefix on a fixed schedule, and for every
 * *.xml object not already recorded in the payments table: downloads it,
 * parses the pacs.008 message, runs error detection, and inserts the row.
 *
 * A simple "already ingested by s3_key" DB lookup is used instead of an
 * event notification (SQS/SNS) to keep this a self-contained polling
 * service - swap {@link #poll()}'s trigger for an S3 event listener if
 * near-real-time ingestion is needed later.
 */
@Service
@ConditionalOnProperty(name = "payment-ingest.source", havingValue = "s3", matchIfMissing = true)
public class S3PaymentPoller {

    private static final Logger log = LoggerFactory.getLogger(S3PaymentPoller.class);

    private final S3Client s3Client;
    private final S3IngestProperties props;
    private final PaymentRepository paymentRepository;
    private final ReferenceDataLoader referenceDataLoader;
    private final ErrorResolutionAgent errorResolutionAgent;

    private volatile ReferenceDataLoader.ReferenceData referenceData;

    public S3PaymentPoller(S3Client s3Client, S3IngestProperties props,
                            PaymentRepository paymentRepository, ReferenceDataLoader referenceDataLoader,
                            ErrorResolutionAgent errorResolutionAgent) {
        this.s3Client = s3Client;
        this.props = props;
        this.paymentRepository = paymentRepository;
        this.referenceDataLoader = referenceDataLoader;
        this.errorResolutionAgent = errorResolutionAgent;
    }

    @Scheduled(fixedDelayString = "${payment-ingest.s3.poll-interval-ms:15000}")
    public void poll() {
        if (props.getBucket() == null || props.getBucket().isBlank()) {
            log.warn("payment-ingest.s3.bucket is not configured - skipping poll cycle.");
            return;
        }
        if (referenceData == null) {
            referenceData = referenceDataLoader.load();
        }

        Set<String> alreadyIngested = paymentRepository.findAllIngestedS3Keys();
        int processed = 0, failed = 0, skipped = 0;

        String continuationToken = null;
        do {
            ListObjectsV2Request.Builder reqBuilder = ListObjectsV2Request.builder()
                    .bucket(props.getBucket())
                    .prefix(props.getPaymentsPrefix());
            if (continuationToken != null) {
                reqBuilder.continuationToken(continuationToken);
            }
            ListObjectsV2Response listResponse = s3Client.listObjectsV2(reqBuilder.build());

            for (S3Object obj : listResponse.contents()) {
                String key = obj.key();
                if (!key.endsWith(".xml")) {
                    skipped++;
                    continue;
                }
                if (alreadyIngested.contains(key)) {
                    continue;
                }
                try {
                    processOne(key);
                    processed++;
                } catch (Exception e) {
                    log.error("failed to ingest s3://{}/{}: {}", props.getBucket(), key, e.getMessage(), e);
                    failed++;
                }
            }
            continuationToken = listResponse.isTruncated() ? listResponse.nextContinuationToken() : null;
        } while (continuationToken != null);

        if (processed > 0 || failed > 0) {
            log.info("poll cycle complete: processed={}, failed={}, skipped={}", processed, failed, skipped);
        }
    }

    private void processOne(String key) throws IOException {
        String rawXml = downloadObject(key);

        ParsedPayment parsed;
        try {
            parsed = Pacs008Parser.parse(rawXml);
        } catch (Pacs008Parser.MalformedPaymentFileException e) {
            log.error("skipping unparseable file s3://{}/{}: {}", props.getBucket(), key, e.getMessage());
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
        boolean isFaulty = key.toUpperCase().contains("FAULTY");

        Long paymentId = paymentRepository.insert(key, parsed, isFaulty, hasError, errorMsg, rawXml);
        log.info("ingested {} (msg_id={}, payment_id={}, has_error={})", key, parsed.msgId, paymentId, hasError);

        if (hasError) {
            errorResolutionAgent.investigate(key, paymentId, parsed, hits);
        }
    }

    private String downloadObject(String key) throws IOException {
        try (ResponseInputStream<GetObjectResponse> stream = s3Client.getObject(
                GetObjectRequest.builder().bucket(props.getBucket()).key(key).build())) {
            return new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
