package com.payinvestigator.ingest.config;

import com.payinvestigator.ingest.resolution.ErrorAgentProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.bedrockruntime.BedrockRuntimeClient;

/**
 * AWS Bedrock Runtime client used by {@link com.payinvestigator.ingest.resolution.ErrorResolutionAgent}
 * to invoke the Claude Sonnet model (see {@code payment-ingest.error-agent.model-id}).
 * Credentials come from the standard AWS default credential provider chain
 * (env vars / instance profile / SSO), same as {@link S3ClientConfig}.
 */
@Configuration
public class BedrockClientConfig {

    @Bean
    public BedrockRuntimeClient bedrockRuntimeClient(ErrorAgentProperties props) {
        return BedrockRuntimeClient.builder()
                .region(Region.of(props.getBedrockRegion()))
                .build();
    }
}
