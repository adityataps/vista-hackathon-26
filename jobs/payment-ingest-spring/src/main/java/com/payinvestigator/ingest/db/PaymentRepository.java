package com.payinvestigator.ingest.db;

import com.payinvestigator.ingest.xml.ParsedPayment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.Date;
import java.sql.Types;
import java.util.List;
import java.util.Set;

/**
 * Persists parsed payments into the {@code payments} table (schema managed
 * by Liquibase, see resources/db/changelog). Mirrors the columns/semantics
 * of jobs/payment-ingest/handler.py's Python insert so both ingestion paths
 * stay compatible with the same table.
 */
@Repository
public class PaymentRepository {

    private final JdbcTemplate jdbcTemplate;

    public PaymentRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /** All s3_key values already ingested, to let the poller skip re-processing. */
    public Set<String> findAllIngestedS3Keys() {
        return Set.copyOf(jdbcTemplate.queryForList("SELECT s3_key FROM payments", String.class));
    }

    /** Existing UETRs matching the given one - feeds the DUPLICATE_UETR check
     * before insert. Returns an empty list if uetr is null. */
    public List<String> findExistingUetrs(String uetr) {
        if (uetr == null) {
            return List.of();
        }
        return jdbcTemplate.queryForList("SELECT uetr FROM payments WHERE uetr = ?", String.class, uetr);
    }

    /** Inserts one payment row and returns the generated id.
     * Duplicate business payments are intentionally persisted as separate rows
     * (new id each time) so duplicate-detection errors can be tracked and
     * resolved without creating poller reprocessing loops.
     */
    public Long insert(String s3Key, ParsedPayment p, boolean isFaulty, boolean hasError, String errorMsg, String rawXml) {
        String sql = """
                INSERT INTO payments (
                    s3_key, msg_id, uetr, instr_id, e2e_id,
                    amount, currency, settlement_date,
                    sender_bic, receiver_bic, debtor_bic, creditor_bic,
                    debtor_name, debtor_iban, creditor_name, creditor_iban,
                    is_faulty, raw_xml, has_error, error_msg
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """;

        List<Long> ids = jdbcTemplate.query(sql, ps -> {
            ps.setString(1, s3Key);
            ps.setString(2, p.msgId);
            ps.setString(3, p.uetr);
            ps.setString(4, p.instrId);
            ps.setString(5, p.e2eId);
            if (p.amount != null) {
                ps.setBigDecimal(6, p.amount);
            } else {
                ps.setNull(6, Types.NUMERIC);
            }
            ps.setString(7, p.currency);
            if (p.settlementDate != null) {
                ps.setDate(8, Date.valueOf(p.settlementDate));
            } else {
                ps.setNull(8, Types.DATE);
            }
            ps.setString(9, p.senderBic);
            ps.setString(10, p.receiverBic);
            ps.setString(11, p.debtorBic);
            ps.setString(12, p.creditorBic);
            ps.setString(13, p.debtorName);
            ps.setString(14, p.debtorIban);
            ps.setString(15, p.creditorName);
            ps.setString(16, p.creditorIban);
            ps.setBoolean(17, isFaulty);
            ps.setString(18, rawXml);
            ps.setBoolean(19, hasError);
            ps.setString(20, errorMsg);
        }, rs -> {
            List<Long> result = new java.util.ArrayList<>();
            while (rs.next()) {
                result.add(rs.getLong("id"));
            }
            return result;
        });

        if (ids == null || ids.isEmpty()) {
            return null;
        }
        return ids.get(0);
    }
}
