package com.payinvestigator.ingest.db;

import com.payinvestigator.ingest.xml.ParsedPayment;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.jdbc.core.JdbcTemplate;

import java.math.BigDecimal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PaymentRepositoryInsertBehaviorTest {

    @Test
    @SuppressWarnings("unchecked")
    void insertReturnsGeneratedIdAndDoesNotUseMsgIdConflictSuppression() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.query(
                contains("RETURNING id"),
                any(org.springframework.jdbc.core.PreparedStatementSetter.class),
                any(org.springframework.jdbc.core.ResultSetExtractor.class)
        )).thenReturn(List.of(101L));

        PaymentRepository repository = new PaymentRepository(jdbcTemplate);

        ParsedPayment payment = new ParsedPayment();
        payment.msgId = "msg-1";
        payment.uetr = "uetr-1";
        payment.instrId = "instr-1";
        payment.e2eId = "e2e-1";
        payment.amount = new BigDecimal("12.34");
        payment.currency = "USD";
        payment.settlementDate = "2026-07-15";
        payment.senderBic = "AAAAUS33";
        payment.receiverBic = "BBBBUS33";
        payment.debtorBic = "CCCCUS33";
        payment.creditorBic = "DDDDUS33";
        payment.debtorName = "Debtor Name";
        payment.debtorIban = "DE89370400440532013000";
        payment.creditorName = "Creditor Name";
        payment.creditorIban = "GB29NWBK60161331926819";

        Long id = repository.insert("payments/duplicate.xml", payment, false, true, "DUPLICATE_UETR", "<xml/>");

        assertNotNull(id);
        assertEquals(101L, id);
        ArgumentCaptor<String> sqlCaptor = ArgumentCaptor.forClass(String.class);
        verify(jdbcTemplate).query(
                sqlCaptor.capture(),
                any(org.springframework.jdbc.core.PreparedStatementSetter.class),
                any(org.springframework.jdbc.core.ResultSetExtractor.class)
        );
        assertFalse(sqlCaptor.getValue().contains("ON CONFLICT (msg_id) DO NOTHING"));
    }
}


