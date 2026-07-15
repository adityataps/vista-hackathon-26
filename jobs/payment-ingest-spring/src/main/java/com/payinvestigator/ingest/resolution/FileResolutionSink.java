package com.payinvestigator.ingest.resolution;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.format.DateTimeFormatter;

/**
 * Default {@link ResolutionSink}: appends each report as a human-readable
 * text block to a local log file (path from
 * {@code payment-ingest.error-agent.resolution-log-path}). Parent
 * directories are created on demand. This is intentionally the simplest
 * possible sink to get the agent's output visible during the hackathon demo
 * - swap in another {@link ResolutionSink} bean to route resolutions
 * elsewhere (ticketing system, API, DB table) later.
 */
@Component
public class FileResolutionSink implements ResolutionSink {

    private static final Logger log = LoggerFactory.getLogger(FileResolutionSink.class);
    private static final DateTimeFormatter TS_FORMAT = DateTimeFormatter.ISO_INSTANT;

    private final ErrorAgentProperties props;

    public FileResolutionSink(ErrorAgentProperties props) {
        this.props = props;
    }

    @Override
    public synchronized void write(PaymentResolutionReport report) {
        Path path = Path.of(props.getResolutionLogPath());
        try {
            if (path.getParent() != null) {
                Files.createDirectories(path.getParent());
            }
            String block = render(report);
            Files.writeString(path, block, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException e) {
            log.error("Failed to write error-resolution report to '{}': {}", path, e.getMessage(), e);
        }
    }

    private String render(PaymentResolutionReport report) {
        StringBuilder sb = new StringBuilder();
        sb.append("=".repeat(80)).append(System.lineSeparator());
        sb.append("timestamp=").append(TS_FORMAT.format(report.timestamp()))
                .append(" s3_key=").append(report.s3Key())
                .append(" payment_id=").append(report.paymentId())
                .append(" msg_id=").append(report.msgId())
                .append(" uetr=").append(report.uetr())
                .append(" source=").append(report.source())
                .append(System.lineSeparator());

        int i = 1;
        for (PaymentResolutionReport.ResolutionSuggestion s : report.suggestions()) {
            sb.append("  [").append(i++).append("] ").append(s.code())
                    .append(" - ").append(s.title() != null ? s.title() : "(unknown error code)")
                    .append(" | severity=").append(s.severity())
                    .append(" | investigation_type=").append(s.investigationType())
                    .append(" | confidence=").append(s.confidence() != null ? s.confidence() : "n/a")
                    .append(System.lineSeparator());
            sb.append("      evidence: ").append(s.evidence()).append(System.lineSeparator());
            if (s.rationale() != null) {
                sb.append("      rationale: ").append(s.rationale()).append(System.lineSeparator());
            }
            sb.append("      recommended_action: ").append(s.recommendedAction()).append(System.lineSeparator());
            sb.append("      auto_repairable: ").append(s.autoRepairable()).append(System.lineSeparator());
            sb.append("      requires_human_approval: ").append(s.requiresHumanApproval()).append(System.lineSeparator());
        }
        sb.append(System.lineSeparator());
        return sb.toString();
    }
}
