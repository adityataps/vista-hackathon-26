package com.payinvestigator.ingest.rules;

/** One rule violation: an error code (matching
 * jobs/pacs008-generator/agent_error_knowledge.yaml) plus a human-readable
 * explanation of the specific values that triggered it. */
public record ErrorHit(String code, String message) {
    @Override
    public String toString() {
        return code + ": " + message;
    }
}
