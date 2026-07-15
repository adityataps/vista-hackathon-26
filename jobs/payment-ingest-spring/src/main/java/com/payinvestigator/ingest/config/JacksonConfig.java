package com.payinvestigator.ingest.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Provides a shared {@link ObjectMapper} bean. This project does not depend
 * on spring-web/spring-boot-starter-json, so Spring Boot's automatic
 * Jackson2ObjectMapperBuilder-based autoconfiguration never kicks in and no
 * ObjectMapper bean gets created by default. Several beans
 * (ErrorResolutionAgent, ReferenceDataLoader, LocalReferenceDataLoader)
 * require one via constructor injection, so it's declared explicitly here.
 */
@Configuration
public class JacksonConfig {

    @Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper();
    }
}

