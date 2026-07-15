package com.payinvestigator.ingest.xml;

import java.math.BigDecimal;

/**
 * Flat representation of one pacs.008.001.08 CdtTrfTxInf, mirroring the
 * columns of the {@code payments} table (plus a few transient fields used
 * only for error detection: instdAmt/instdAmtCcy/xchgRate/creditor address).
 */
public class ParsedPayment {
    public String msgId;
    public String uetr;
    public String instrId;
    public String e2eId;
    public BigDecimal amount;
    public String currency;
    public String settlementDate;
    public String senderBic;
    public String receiverBic;
    public String debtorBic;
    public String creditorBic;
    public String debtorName;
    public String debtorIban;
    public String creditorName;
    public String creditorIban;

    // Transient - used only by error detection, not persisted.
    public BigDecimal instdAmt;
    public String instdAmtCcy;
    public String xchgRate;
    public String creditorCtry;
    public String creditorTwnNm;
    public String creditorStrtNm;
}
