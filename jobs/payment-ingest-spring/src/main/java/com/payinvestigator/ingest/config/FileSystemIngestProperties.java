package com.payinvestigator.ingest.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Binds the {@code payment-ingest.filesystem.*} keys, used when
 * {@code payment-ingest.source=filesystem} - lets the poller watch a local
 * directory instead of S3, for running/demoing the service without any AWS
 * dependency (Postgres is still required).
 */
@ConfigurationProperties(prefix = "payment-ingest.filesystem")
public class FileSystemIngestProperties {

    /** Root directory to watch, e.g. "C:/Users/u727254/Desktop/VISTA - hack/payment-drop". */
    private String watchDir = "./payment-drop";

    /** Subfolder (under watchDir) that payment XML files are dropped into. */
    private String paymentsSubdir = "payments";

    /** Optional subfolder (under watchDir) with local reference data:
     * bic_directory.json / watchlist.json / closed_accounts.json (JSON
     * arrays of strings, same shape as the S3 reference-data objects).
     * Leave the files absent to disable those specific checks. */
    private String referenceDataSubdir = "reference";

    /** How often (ms) to re-scan watchDir/paymentsSubdir for new files. */
    private long pollIntervalMs = 5_000;

    public String getWatchDir() {
        return watchDir;
    }

    public void setWatchDir(String watchDir) {
        this.watchDir = watchDir;
    }

    public String getPaymentsSubdir() {
        return paymentsSubdir;
    }

    public void setPaymentsSubdir(String paymentsSubdir) {
        this.paymentsSubdir = paymentsSubdir;
    }

    public String getReferenceDataSubdir() {
        return referenceDataSubdir;
    }

    public void setReferenceDataSubdir(String referenceDataSubdir) {
        this.referenceDataSubdir = referenceDataSubdir;
    }

    public long getPollIntervalMs() {
        return pollIntervalMs;
    }

    public void setPollIntervalMs(long pollIntervalMs) {
        this.pollIntervalMs = pollIntervalMs;
    }
}
