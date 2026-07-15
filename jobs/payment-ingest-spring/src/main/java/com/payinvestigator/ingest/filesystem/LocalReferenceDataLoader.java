package com.payinvestigator.ingest.filesystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.payinvestigator.ingest.config.FileSystemIngestProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;

/**
 * Local-disk equivalent of {@link com.payinvestigator.ingest.s3.ReferenceDataLoader}:
 * loads optional bic_directory.json / watchlist.json / closed_accounts.json
 * (each a JSON array of strings) from {@code watchDir/referenceDataSubdir},
 * for running the error-detection rules without any S3/AWS dependency.
 * Missing files simply disable the corresponding check.
 */
@Component
@ConditionalOnProperty(name = "payment-ingest.source", havingValue = "filesystem")
public class LocalReferenceDataLoader {

    private static final Logger log = LoggerFactory.getLogger(LocalReferenceDataLoader.class);

    private final FileSystemIngestProperties props;
    private final ObjectMapper objectMapper;

    public LocalReferenceDataLoader(FileSystemIngestProperties props, ObjectMapper objectMapper) {
        this.props = props;
        this.objectMapper = objectMapper;
    }

    public record ReferenceData(Set<String> knownBics, List<String> watchlist, List<String> closedAccounts) {
    }

    public ReferenceData load() {
        Path refDir = Path.of(props.getWatchDir(), props.getReferenceDataSubdir());
        if (!Files.isDirectory(refDir)) {
            log.info("Local reference-data dir '{}' not present - skipping BIC/watchlist/closed-account checks.", refDir);
            return new ReferenceData(null, null, null);
        }

        List<String> bicDirectory = loadJsonArray(refDir.resolve("bic_directory.json"));
        return new ReferenceData(
                bicDirectory != null ? Set.copyOf(bicDirectory) : null,
                loadJsonArray(refDir.resolve("watchlist.json")),
                loadJsonArray(refDir.resolve("closed_accounts.json"))
        );
    }

    private List<String> loadJsonArray(Path file) {
        if (!Files.isRegularFile(file)) {
            return null;
        }
        try {
            return objectMapper.readValue(file.toFile(), List.class);
        } catch (IOException e) {
            log.warn("Could not load reference data '{}': {}", file, e.getMessage());
            return null;
        }
    }
}
