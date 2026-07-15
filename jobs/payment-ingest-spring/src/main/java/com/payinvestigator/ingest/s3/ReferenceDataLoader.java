package com.payinvestigator.ingest.s3;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.payinvestigator.ingest.config.S3IngestProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;

import java.io.IOException;
import java.util.List;
import java.util.Set;

/**
 * Loads optional reference data (BIC directory, sanctions watchlist, closed
 * accounts) from S3, under {@code payment-ingest.s3.reference-data-prefix}.
 * Each object is a JSON array of strings. Missing objects/prefix simply
 * disable the corresponding check in PaymentErrorDetector - this never fails
 * ingestion.
 */
@Component
public class ReferenceDataLoader {

    private static final Logger log = LoggerFactory.getLogger(ReferenceDataLoader.class);

    private final S3Client s3Client;
    private final S3IngestProperties props;
    private final ObjectMapper objectMapper;

    public ReferenceDataLoader(S3Client s3Client, S3IngestProperties props, ObjectMapper objectMapper) {
        this.s3Client = s3Client;
        this.props = props;
        this.objectMapper = objectMapper;
    }

    public record ReferenceData(Set<String> knownBics, List<String> watchlist, List<String> closedAccounts) {
    }

    public ReferenceData load() {
        String prefix = props.getReferenceDataPrefix();
        if (prefix == null || prefix.isBlank()) {
            log.info("payment-ingest.s3.reference-data-prefix not set - skipping BIC/watchlist/closed-account checks.");
            return new ReferenceData(null, null, null);
        }

        List<String> bicDirectory = loadJsonArray(prefix + "bic_directory.json");
        return new ReferenceData(
                bicDirectory != null ? Set.copyOf(bicDirectory) : null,
                loadJsonArray(prefix + "watchlist.json"),
                loadJsonArray(prefix + "closed_accounts.json")
        );
    }

    private List<String> loadJsonArray(String key) {
        try {
            var response = s3Client.getObject(GetObjectRequest.builder()
                    .bucket(props.getBucket())
                    .key(key)
                    .build());
            return objectMapper.readValue(response, List.class);
        } catch (NoSuchKeyException e) {
            log.info("Reference data s3://{}/{} not present - corresponding check disabled.", props.getBucket(), key);
            return null;
        } catch (SdkException | IOException e) {
            log.warn("Could not load reference data s3://{}/{}: {}", props.getBucket(), key, e.getMessage());
            return null;
        }
    }
}
