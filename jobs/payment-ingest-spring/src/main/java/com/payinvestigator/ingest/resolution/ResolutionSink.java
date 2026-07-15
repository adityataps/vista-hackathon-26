package com.payinvestigator.ingest.resolution;

/**
 * Destination for {@link PaymentResolutionReport}s produced by
 * {@link ErrorResolutionAgent}. Kept as an interface so the delivery target
 * can change later (e.g. from a local log file to a queue, a REST callback,
 * or a dedicated DB table) without touching the agent or its callers -
 * only a new implementation needs to be wired up in place of
 * {@link FileResolutionSink}.
 */
public interface ResolutionSink {

    void write(PaymentResolutionReport report);
}
