package com.payinvestigator.ingest.resolution;

import org.springframework.core.io.DefaultResourceLoader;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/** Tiny helper to read a text resource (system prompt, etc.) via Spring's
 * resource abstraction, so paths can be {@code classpath:} or {@code file:}. */
final class TextResourceLoader {

    private static final ResourceLoader RESOURCE_LOADER = new DefaultResourceLoader();

    private TextResourceLoader() {
    }

    static String read(String location) throws IOException {
        Resource resource = RESOURCE_LOADER.getResource(location);
        try (var in = resource.getInputStream()) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
