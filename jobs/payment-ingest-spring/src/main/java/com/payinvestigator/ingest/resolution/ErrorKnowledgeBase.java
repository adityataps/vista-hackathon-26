package com.payinvestigator.ingest.resolution;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.DefaultResourceLoader;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.stereotype.Component;
import org.yaml.snakeyaml.Yaml;

import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Loads agent_error_knowledge.yaml (the detection/resolution knowledge base
 * for Use Case A) into an in-memory lookup by error code. This is the
 * "brain" behind {@link ErrorResolutionAgent}: for each code raised by
 * {@link com.payinvestigator.ingest.rules.PaymentErrorDetector}, it supplies
 * the human-readable title, investigation type, and suggested_action.
 *
 * Loaded once at startup (see {@link #load()} caching in
 * {@link ErrorResolutionAgent}) via Spring's resource abstraction, so the
 * path can be {@code classpath:...} (bundled copy, the default) or
 * {@code file:...} (an externally maintained copy) with no code changes.
 */
@Component
public class ErrorKnowledgeBase {

    private static final Logger log = LoggerFactory.getLogger(ErrorKnowledgeBase.class);

    private final ErrorAgentProperties props;
    private final ResourceLoader resourceLoader = new DefaultResourceLoader();

    public ErrorKnowledgeBase(ErrorAgentProperties props) {
        this.props = props;
    }

    @SuppressWarnings("unchecked")
    public Map<String, ErrorKnowledgeEntry> load() {
        Resource resource = resourceLoader.getResource(props.getKnowledgeBasePath());
        Map<String, ErrorKnowledgeEntry> byCode = new LinkedHashMap<>();

        if (!resource.exists()) {
            log.warn("Error-knowledge base not found at '{}' - resolution suggestions will be generic.",
                    props.getKnowledgeBasePath());
            return byCode;
        }

        try (InputStream in = resource.getInputStream()) {
            Yaml yaml = new Yaml();
            Map<String, Object> root = yaml.load(in);
            List<Map<String, Object>> errors = (List<Map<String, Object>>) root.get("errors");
            if (errors == null) {
                return byCode;
            }
            for (Map<String, Object> e : errors) {
                ErrorKnowledgeEntry entry = new ErrorKnowledgeEntry(
                        str(e, "code"),
                        str(e, "title"),
                        str(e, "category"),
                        str(e, "severity"),
                        (List<String>) e.getOrDefault("check_fields", List.of()),
                        str(e, "detection"),
                        (List<String>) e.getOrDefault("reference_data", List.of()),
                        str(e, "investigation_type"),
                        str(e, "suggested_action"),
                        Objects.toString(e.get("auto_repairable"), "unknown")
                );
                byCode.put(entry.code(), entry);
            }
            log.info("Loaded {} error-knowledge entries from '{}'.", byCode.size(), props.getKnowledgeBasePath());
        } catch (Exception ex) {
            log.error("Failed to load error-knowledge base from '{}': {}", props.getKnowledgeBasePath(), ex.getMessage(), ex);
        }
        return byCode;
    }

    private static String str(Map<String, Object> map, String key) {
        Object v = map.get(key);
        return v == null ? null : v.toString();
    }
}
