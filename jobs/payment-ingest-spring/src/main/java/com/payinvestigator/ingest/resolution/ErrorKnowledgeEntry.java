package com.payinvestigator.ingest.resolution;

import java.util.List;

/**
 * One entry of the error-knowledge base (agent_error_knowledge.yaml),
 * describing how to detect and resolve a given business error code.
 * Field names mirror the YAML keys (snake_case in YAML, mapped manually
 * in {@link ErrorKnowledgeBase}).
 */
public record ErrorKnowledgeEntry(
        String code,
        String title,
        String category,
        String severity,
        List<String> checkFields,
        String detection,
        List<String> referenceData,
        String investigationType,
        String suggestedAction,
        String autoRepairable
) {
}
