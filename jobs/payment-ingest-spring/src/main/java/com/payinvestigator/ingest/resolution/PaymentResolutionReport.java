package com.payinvestigator.ingest.resolution;

import java.time.Instant;
import java.util.List;

/**
 * One agent run's output for a single ingested payment: which errors were
 * detected, and the Claude-generated suggested resolution for each.
 */
public record PaymentResolutionReport(
        Instant timestamp,
        String s3Key,
        Long paymentId,
        String msgId,
        String uetr,
        String source,
        List<ResolutionSuggestion> suggestions
) {

    /** {@code source} values: identifies whether the suggestions came from
     * the Claude Sonnet model or a static knowledge-base fallback (used
     * when the LLM call fails, so the pipeline never silently drops a
     * detected error without at least a baseline recommendation). */
    public static final String SOURCE_LLM = "claude-sonnet";
    public static final String SOURCE_FALLBACK = "knowledge_base_fallback";

    public record ResolutionSuggestion(
            String code,
            String title,
            String severity,
            String investigationType,
            String evidence,
            Double confidence,
            String rationale,
            String recommendedAction,
            String autoRepairable,
            boolean requiresHumanApproval
    ) {
    }
}
