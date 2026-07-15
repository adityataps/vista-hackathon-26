package com.payinvestigator.ingest.resolution;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.payinvestigator.ingest.rules.ErrorHit;
import com.payinvestigator.ingest.xml.ParsedPayment;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.bedrockruntime.BedrockRuntimeClient;
import software.amazon.awssdk.services.bedrockruntime.model.ContentBlock;
import software.amazon.awssdk.services.bedrockruntime.model.ConversationRole;
import software.amazon.awssdk.services.bedrockruntime.model.ConverseRequest;
import software.amazon.awssdk.services.bedrockruntime.model.ConverseResponse;
import software.amazon.awssdk.services.bedrockruntime.model.InferenceConfiguration;
import software.amazon.awssdk.services.bedrockruntime.model.Message;
import software.amazon.awssdk.services.bedrockruntime.model.SystemContentBlock;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * The AI resolution agent for Use Case A: whenever
 * {@link com.payinvestigator.ingest.s3.S3PaymentPoller} detects one or more
 * business errors on an ingested payment, this hands the payment context,
 * the detected errors, and the matching entries from
 * agent_error_knowledge.yaml to Claude Sonnet (via AWS Bedrock) and asks it
 * to reason about root cause and recommend a resolution. Per the
 * human-in-the-loop requirement, the model is instructed to only ever
 * recommend - nothing here executes any payment action.
 *
 * If the Bedrock call fails for any reason (throttling, missing
 * credentials, malformed response, ...), this falls back to the static
 * {@code suggested_action} from the knowledge base so a resolution report is
 * still produced for every detected error.
 */
@Service
public class ErrorResolutionAgent {

    private static final Logger log = LoggerFactory.getLogger(ErrorResolutionAgent.class);

    private final ErrorKnowledgeBase knowledgeBase;
    private final ResolutionSink resolutionSink;
    private final BedrockRuntimeClient bedrockRuntimeClient;
    private final ErrorAgentProperties props;
    private final ObjectMapper objectMapper;

    private volatile Map<String, ErrorKnowledgeEntry> entriesByCode;
    private volatile String systemPrompt;

    public ErrorResolutionAgent(ErrorKnowledgeBase knowledgeBase, ResolutionSink resolutionSink,
                                 BedrockRuntimeClient bedrockRuntimeClient, ErrorAgentProperties props,
                                 ObjectMapper objectMapper) {
        this.knowledgeBase = knowledgeBase;
        this.resolutionSink = resolutionSink;
        this.bedrockRuntimeClient = bedrockRuntimeClient;
        this.props = props;
        this.objectMapper = objectMapper;
    }

    public synchronized void reload() {
        entriesByCode = knowledgeBase.load();
    }

    private Map<String, ErrorKnowledgeEntry> entries() {
        Map<String, ErrorKnowledgeEntry> current = entriesByCode;
        if (current == null) {
            reload();
            current = entriesByCode;
        }
        return current;
    }

    private String systemPrompt() {
        String current = systemPrompt;
        if (current == null) {
            try {
                current = TextResourceLoader.read(props.getSystemPromptPath());
            } catch (Exception e) {
                log.error("Failed to load resolution-agent system prompt from '{}': {}",
                        props.getSystemPromptPath(), e.getMessage(), e);
                current = "You are a payment-error resolution assistant. Respond only with a JSON array "
                        + "of {code, confidence, rationale, recommended_action, requires_human_approval}.";
            }
            systemPrompt = current;
        }
        return current;
    }

    /**
     * Investigates the errors detected for one payment and writes a
     * suggested-resolution report. No-op if {@code hits} is empty.
     */
    public void investigate(String s3Key, Long paymentId, ParsedPayment payment, List<ErrorHit> hits) {
        if (hits == null || hits.isEmpty()) {
            return;
        }

        Map<String, ErrorKnowledgeEntry> byCode = entries();
        List<PaymentResolutionReport.ResolutionSuggestion> suggestions;
        String source;
        try {
            suggestions = invokeModel(payment, hits, byCode);
            source = PaymentResolutionReport.SOURCE_LLM;
        } catch (Exception e) {
            log.error("Bedrock call failed for s3_key={}, falling back to knowledge-base suggestions: {}",
                    s3Key, e.getMessage(), e);
            suggestions = hits.stream().map(hit -> fallbackSuggestion(hit, byCode.get(hit.code())))
                    .collect(Collectors.toList());
            source = PaymentResolutionReport.SOURCE_FALLBACK;
        }

        PaymentResolutionReport report = new PaymentResolutionReport(
                Instant.now(), s3Key, paymentId, payment.msgId, payment.uetr, source, suggestions);

        resolutionSink.write(report);
        log.info("wrote {} resolution suggestions for {} (source={}): {}",
                suggestions.size(), s3Key, source,
                suggestions.stream().map(PaymentResolutionReport.ResolutionSuggestion::code)
                        .collect(Collectors.joining(", ")));
    }

    // ── Bedrock / Claude call ────────────────────────────────────────────────

    private List<PaymentResolutionReport.ResolutionSuggestion> invokeModel(
            ParsedPayment payment, List<ErrorHit> hits, Map<String, ErrorKnowledgeEntry> byCode) throws Exception {

        String userPayload = buildUserPayload(payment, hits, byCode);

        ConverseRequest request = ConverseRequest.builder()
                .modelId(props.getModelId())
                .system(SystemContentBlock.builder().text(systemPrompt()).build())
                .messages(Message.builder()
                        .role(ConversationRole.USER)
                        .content(ContentBlock.fromText(userPayload))
                        .build())
                .inferenceConfig(InferenceConfiguration.builder()
                        .maxTokens(props.getMaxTokens())
                        .temperature((float) props.getTemperature())
                        .build())
                .build();

        ConverseResponse response = bedrockRuntimeClient.converse(request);
        String text = response.output().message().content().get(0).text();
        return parseModelResponse(text, hits, byCode);
    }

    private String buildUserPayload(ParsedPayment payment, List<ErrorHit> hits,
                                     Map<String, ErrorKnowledgeEntry> byCode) throws Exception {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("payment", paymentFields(payment));

        List<Map<String, String>> detectedErrors = new ArrayList<>();
        List<Object> knowledgeBaseEntries = new ArrayList<>();
        for (ErrorHit hit : hits) {
            Map<String, String> e = new LinkedHashMap<>();
            e.put("code", hit.code());
            e.put("evidence", hit.message());
            detectedErrors.add(e);

            ErrorKnowledgeEntry entry = byCode.get(hit.code());
            if (entry != null) {
                knowledgeBaseEntries.add(entry);
            }
        }
        payload.put("detected_errors", detectedErrors);
        payload.put("knowledge_base", knowledgeBaseEntries);

        return objectMapper.writeValueAsString(payload);
    }

    private Map<String, Object> paymentFields(ParsedPayment p) {
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put("msg_id", p.msgId);
        fields.put("uetr", p.uetr);
        fields.put("instr_id", p.instrId);
        fields.put("e2e_id", p.e2eId);
        fields.put("amount", p.amount);
        fields.put("currency", p.currency);
        fields.put("settlement_date", p.settlementDate);
        fields.put("sender_bic", p.senderBic);
        fields.put("receiver_bic", p.receiverBic);
        fields.put("debtor_bic", p.debtorBic);
        fields.put("creditor_bic", p.creditorBic);
        fields.put("debtor_name", p.debtorName);
        fields.put("debtor_iban", p.debtorIban);
        fields.put("creditor_name", p.creditorName);
        fields.put("creditor_iban", p.creditorIban);
        return fields;
    }

    /** Parses the model's JSON-array response, tolerating an accidental
     * markdown code fence around it. Falls back to a per-code knowledge-base
     * suggestion for any detected error the model didn't return a row for. */
    private List<PaymentResolutionReport.ResolutionSuggestion> parseModelResponse(
            String text, List<ErrorHit> hits, Map<String, ErrorKnowledgeEntry> byCode) throws Exception {

        String cleaned = text.strip();
        if (cleaned.startsWith("```")) {
            cleaned = cleaned.replaceFirst("^```(json)?", "").replaceFirst("```$", "").strip();
        }

        JsonNode arr = objectMapper.readTree(cleaned);
        Map<String, JsonNode> byCodeFromModel = new LinkedHashMap<>();
        if (arr.isArray()) {
            for (JsonNode node : arr) {
                if (node.hasNonNull("code")) {
                    byCodeFromModel.put(node.get("code").asText(), node);
                }
            }
        }

        List<PaymentResolutionReport.ResolutionSuggestion> suggestions = new ArrayList<>();
        for (ErrorHit hit : hits) {
            ErrorKnowledgeEntry entry = byCode.get(hit.code());
            JsonNode modelNode = byCodeFromModel.get(hit.code());
            if (modelNode == null) {
                log.warn("Model response did not include a suggestion for code '{}' - using knowledge-base fallback.", hit.code());
                suggestions.add(fallbackSuggestion(hit, entry));
                continue;
            }
            suggestions.add(new PaymentResolutionReport.ResolutionSuggestion(
                    hit.code(),
                    entry != null ? entry.title() : null,
                    entry != null ? entry.severity() : "unknown",
                    entry != null ? entry.investigationType() : "Manual review",
                    hit.message(),
                    modelNode.hasNonNull("confidence") ? modelNode.get("confidence").asDouble() : null,
                    modelNode.hasNonNull("rationale") ? modelNode.get("rationale").asText() : null,
                    modelNode.hasNonNull("recommended_action") ? modelNode.get("recommended_action").asText()
                            : (entry != null ? entry.suggestedAction() : "Route to a human analyst for manual investigation."),
                    entry != null ? entry.autoRepairable() : "unknown",
                    true
            ));
        }
        return suggestions;
    }

    private PaymentResolutionReport.ResolutionSuggestion fallbackSuggestion(ErrorHit hit, ErrorKnowledgeEntry entry) {
        if (entry == null) {
            log.warn("No knowledge-base entry found for error code '{}' - falling back to a generic suggestion.", hit.code());
            return new PaymentResolutionReport.ResolutionSuggestion(
                    hit.code(), null, "unknown", "Manual review", hit.message(),
                    null, "No knowledge-base entry or model output available for this code.",
                    "Route to a human analyst for manual investigation.", "unknown", true
            );
        }
        return new PaymentResolutionReport.ResolutionSuggestion(
                entry.code(), entry.title(), entry.severity(), entry.investigationType(), hit.message(),
                null, "Static knowledge-base suggestion (LLM unavailable).",
                entry.suggestedAction(), entry.autoRepairable(), true
        );
    }
}
