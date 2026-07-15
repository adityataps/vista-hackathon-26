package com.payinvestigator.ingest.xml;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;

import javax.xml.XMLConstants;
import javax.xml.namespace.NamespaceContext;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.xpath.XPath;
import javax.xml.xpath.XPathConstants;
import javax.xml.xpath.XPathFactory;
import java.io.StringReader;
import java.math.BigDecimal;
import java.util.Iterator;
import java.util.regex.Pattern;

/**
 * Parses a pacs.008.001.08 (FIToFICstmrCdtTrf) message - the same shape as
 * the files under jobs/pacs008-generator/aws sample output and
 * jobs/payment-ingest/handler.py's Python mapper - into a {@link ParsedPayment}.
 *
 * The source files contain an XML declaration, a generator comment, and two
 * sibling root elements (head:AppHdr, pacs:Document), which isn't valid
 * standalone XML - we strip the declaration/comment and wrap the rest in a
 * synthetic root before parsing.
 */
public final class Pacs008Parser {

    private static final String HEAD_NS = "urn:iso:std:iso:20022:tech:xsd:head.001.001.02";
    private static final String PACS_NS = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08";

    private static final Pattern XML_DECL = Pattern.compile("<\\?xml[^?]*\\?>");
    private static final Pattern COMMENT = Pattern.compile("<!--.*?-->", Pattern.DOTALL);

    private Pacs008Parser() {
    }

    public static class MalformedPaymentFileException extends RuntimeException {
        public MalformedPaymentFileException(String message, Throwable cause) {
            super(message, cause);
        }

        public MalformedPaymentFileException(String message) {
            super(message);
        }
    }

    public static ParsedPayment parse(String rawXml) {
        Document doc = parseDocument(rawXml);
        XPath xpath = newXPath();

        try {
            Node cdtTrfTxInf = (Node) xpath.evaluate("//*[local-name()='CdtTrfTxInf']", doc, XPathConstants.NODE);
            if (cdtTrfTxInf == null) {
                throw new MalformedPaymentFileException("Missing CdtTrfTxInf element");
            }

            ParsedPayment p = new ParsedPayment();
            p.msgId = text(xpath, doc, "//*[local-name()='BizMsgIdr']");
            p.uetr = text(xpath, cdtTrfTxInf, "*[local-name()='PmtId']/*[local-name()='UETR']");
            p.instrId = text(xpath, cdtTrfTxInf, "*[local-name()='PmtId']/*[local-name()='InstrId']");
            p.e2eId = text(xpath, cdtTrfTxInf, "*[local-name()='PmtId']/*[local-name()='EndToEndId']");

            Element amtEl = (Element) xpath.evaluate("*[local-name()='IntrBkSttlmAmt']", cdtTrfTxInf, XPathConstants.NODE);
            p.amount = decimal(amtEl);
            p.currency = amtEl != null ? amtEl.getAttribute("Ccy") : null;

            Element instdAmtEl = (Element) xpath.evaluate("*[local-name()='InstdAmt']", cdtTrfTxInf, XPathConstants.NODE);
            p.instdAmt = decimal(instdAmtEl);
            p.instdAmtCcy = instdAmtEl != null ? instdAmtEl.getAttribute("Ccy") : null;
            p.xchgRate = text(xpath, cdtTrfTxInf, "*[local-name()='XchgRate']");

            p.settlementDate = text(xpath, cdtTrfTxInf, "*[local-name()='IntrBkSttlmDt']");
            p.senderBic = text(xpath, doc, "//*[local-name()='Fr']/*[local-name()='FIId']/*[local-name()='FinInstnId']/*[local-name()='BICFI']");
            p.receiverBic = text(xpath, doc, "//*[local-name()='To']/*[local-name()='FIId']/*[local-name()='FinInstnId']/*[local-name()='BICFI']");
            p.debtorBic = text(xpath, cdtTrfTxInf, "*[local-name()='DbtrAgt']/*[local-name()='FinInstnId']/*[local-name()='BICFI']");
            p.creditorBic = text(xpath, cdtTrfTxInf, "*[local-name()='CdtrAgt']/*[local-name()='FinInstnId']/*[local-name()='BICFI']");

            p.debtorName = text(xpath, cdtTrfTxInf, "*[local-name()='Dbtr']/*[local-name()='Nm']");
            String debtorIban = text(xpath, cdtTrfTxInf, "*[local-name()='DbtrAcct']/*[local-name()='Id']/*[local-name()='IBAN']");
            p.debtorIban = debtorIban != null ? debtorIban
                    : text(xpath, cdtTrfTxInf, "*[local-name()='DbtrAcct']/*[local-name()='Id']/*[local-name()='Othr']/*[local-name()='Id']");

            p.creditorName = text(xpath, cdtTrfTxInf, "*[local-name()='Cdtr']/*[local-name()='Nm']");
            String creditorIban = text(xpath, cdtTrfTxInf, "*[local-name()='CdtrAcct']/*[local-name()='Id']/*[local-name()='IBAN']");
            p.creditorIban = creditorIban != null ? creditorIban
                    : text(xpath, cdtTrfTxInf, "*[local-name()='CdtrAcct']/*[local-name()='Id']/*[local-name()='Othr']/*[local-name()='Id']");

            p.creditorCtry = text(xpath, cdtTrfTxInf, "*[local-name()='Cdtr']/*[local-name()='PstlAdr']/*[local-name()='Ctry']");
            p.creditorTwnNm = text(xpath, cdtTrfTxInf, "*[local-name()='Cdtr']/*[local-name()='PstlAdr']/*[local-name()='TwnNm']");
            p.creditorStrtNm = text(xpath, cdtTrfTxInf, "*[local-name()='Cdtr']/*[local-name()='PstlAdr']/*[local-name()='StrtNm']");

            if (p.uetr == null || p.uetr.isBlank()) {
                throw new MalformedPaymentFileException("Missing PmtId/UETR - cannot process payment");
            }
            return p;
        } catch (javax.xml.xpath.XPathExpressionException e) {
            throw new MalformedPaymentFileException("XPath evaluation failed: " + e.getMessage(), e);
        }
    }

    private static Document parseDocument(String rawXml) {
        String withoutDecl = XML_DECL.matcher(rawXml).replaceFirst("");
        String withoutComment = COMMENT.matcher(withoutDecl).replaceAll("");
        String wrapped = "<root xmlns:head=\"" + HEAD_NS + "\" xmlns:pacs=\"" + PACS_NS + "\">"
                + withoutComment.strip() + "</root>";

        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            // Harden against XXE / external entities.
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
            factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            factory.setXIncludeAware(false);
            factory.setExpandEntityReferences(false);
            factory.setNamespaceAware(true);

            DocumentBuilder builder = factory.newDocumentBuilder();
            return builder.parse(new InputSource(new StringReader(wrapped)));
        } catch (Exception e) {
            throw new MalformedPaymentFileException("Could not parse XML: " + e.getMessage(), e);
        }
    }

    private static XPath newXPath() {
        XPath xpath = XPathFactory.newInstance().newXPath();
        // local-name() based expressions above don't strictly need a prefix
        // resolver, but keep a no-op one in case any caller adds prefixed paths.
        xpath.setNamespaceContext(new NamespaceContext() {
            @Override
            public String getNamespaceURI(String prefix) {
                if ("head".equals(prefix)) return HEAD_NS;
                if ("pacs".equals(prefix)) return PACS_NS;
                return XMLConstants.NULL_NS_URI;
            }

            @Override
            public String getPrefix(String namespaceURI) {
                return null;
            }

            @Override
            public Iterator<String> getPrefixes(String namespaceURI) {
                return null;
            }
        });
        return xpath;
    }

    private static String text(XPath xpath, Object context, String expr) throws javax.xml.xpath.XPathExpressionException {
        Node node = (Node) xpath.evaluate(expr, context, XPathConstants.NODE);
        if (node == null || node.getTextContent() == null) {
            return null;
        }
        String value = node.getTextContent().strip();
        return value.isEmpty() ? null : value;
    }

    private static BigDecimal decimal(Element el) {
        if (el == null || el.getTextContent() == null) {
            return null;
        }
        String value = el.getTextContent().strip();
        return value.isEmpty() ? null : new BigDecimal(value);
    }
}
