package com.payinvestigator.ingest;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Simple Spring Boot service that polls a configured S3 bucket/prefix for
 * new pacs.008 payment files, maps them to the payments table, runs error
 * detection against agent_error_knowledge.yaml's rules, and persists the
 * result to Postgres. Schema is managed by Liquibase (see
 * resources/db/changelog) - the payments table is created automatically on
 * first startup if it doesn't already exist.
 */
@SpringBootApplication
@EnableScheduling
public class IngestApplication {

    public static void main(String[] args) {
        SpringApplication.run(IngestApplication.class, args);
    }
}
