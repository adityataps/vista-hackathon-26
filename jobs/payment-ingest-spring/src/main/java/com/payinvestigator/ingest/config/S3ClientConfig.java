package com.payinvestigator.ingest.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3ClientBuilder;

import java.net.URI;

@Configuration
@EnableConfigurationProperties(S3IngestProperties.class)
public class S3ClientConfig {

    @Bean
    public S3Client s3Client(S3IngestProperties props) {
        S3ClientBuilder builder = S3Client.builder().region(Region.of(props.getRegion()));
        if (props.getEndpointOverride() != null && !props.getEndpointOverride().isBlank()) {
            // Lets the poller be pointed at LocalStack/MinIO for local development.
            builder.endpointOverride(URI.create(props.getEndpointOverride())).forcePathStyle(true);
        }
        return builder.build();
    }
}
