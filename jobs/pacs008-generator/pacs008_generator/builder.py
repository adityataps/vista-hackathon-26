"""Build CBPR+ pacs.008 XML (AppHdr + Document) from a transaction dict (tx)."""
from xml.sax.saxutils import escape


def _agt(tag, bic):
    return ("<pacs:%s><pacs:FinInstnId><pacs:BICFI>%s</pacs:BICFI>"
            "</pacs:FinInstnId></pacs:%s>" % (tag, bic, tag))


def _acct(tag, party):
    if party.get("iban"):
        inner = "<pacs:IBAN>%s</pacs:IBAN>" % party["iban"]
    else:
        inner = "<pacs:Othr><pacs:Id>%s</pacs:Id></pacs:Othr>" % party["othr_id"]
    return "<pacs:%s><pacs:Id>%s</pacs:Id></pacs:%s>" % (tag, inner, tag)


def _party(tag, p):
    adr = []
    if p.get("strt"):
        adr.append("<pacs:StrtNm>%s</pacs:StrtNm>" % escape(p["strt"]))
    if p.get("bldgnb"):
        adr.append("<pacs:BldgNb>%s</pacs:BldgNb>" % escape(p["bldgnb"]))
    if p.get("pstcd"):
        adr.append("<pacs:PstCd>%s</pacs:PstCd>" % escape(p["pstcd"]))
    if p.get("twn"):
        adr.append("<pacs:TwnNm>%s</pacs:TwnNm>" % escape(p["twn"]))
    if p.get("ctry"):
        adr.append("<pacs:Ctry>%s</pacs:Ctry>" % p["ctry"])
    pstl = "<pacs:PstlAdr>%s</pacs:PstlAdr>" % "".join(adr) if adr else ""
    return "<pacs:%s><pacs:Nm>%s</pacs:Nm>%s</pacs:%s>" % (
        tag, escape(p["nm"]), pstl, tag)


def build_apphdr(tx):
    return (
        '<head:AppHdr xmlns:head="urn:iso:std:iso:20022:tech:xsd:head.001.001.02">'
        "<head:Fr><head:FIId><head:FinInstnId><head:BICFI>%(fr)s</head:BICFI>"
        "</head:FinInstnId></head:FIId></head:Fr>"
        "<head:To><head:FIId><head:FinInstnId><head:BICFI>%(to)s</head:BICFI>"
        "</head:FinInstnId></head:FIId></head:To>"
        "<head:BizMsgIdr>%(msg_id)s</head:BizMsgIdr>"
        "<head:MsgDefIdr>pacs.008.001.08</head:MsgDefIdr>"
        "<head:BizSvc>swift.cbprplus.03</head:BizSvc>"
        "<head:CreDt>%(cre_dt)s</head:CreDt>"
        "</head:AppHdr>"
    ) % {"fr": tx["instg_bic"], "to": tx["instd_bic"],
         "msg_id": tx["msg_id"], "cre_dt": tx["cre_dt"]}


def build_document(tx):
    parts = []
    parts.append("<pacs:PmtId><pacs:InstrId>%s</pacs:InstrId>"
                 "<pacs:EndToEndId>%s</pacs:EndToEndId>"
                 "<pacs:UETR>%s</pacs:UETR></pacs:PmtId>"
                 % (tx["instr_id"], tx["e2e_id"], tx["uetr"]))
    parts.append('<pacs:IntrBkSttlmAmt Ccy="%s">%s</pacs:IntrBkSttlmAmt>'
                 % (tx["ccy"], tx["amt"]))
    parts.append("<pacs:IntrBkSttlmDt>%s</pacs:IntrBkSttlmDt>" % tx["sttlm_dt"])
    if tx.get("instd_amt"):
        parts.append('<pacs:InstdAmt Ccy="%s">%s</pacs:InstdAmt>'
                     % (tx["instd_ccy"], tx["instd_amt"]))
    if tx.get("xchg_rate"):
        parts.append("<pacs:XchgRate>%s</pacs:XchgRate>" % tx["xchg_rate"])
    parts.append("<pacs:ChrgBr>%s</pacs:ChrgBr>" % tx["chrg_br"])
    parts.append(_agt("InstgAgt", tx["instg_bic"]))
    parts.append(_agt("InstdAgt", tx["instd_bic"]))
    if tx.get("intrmy_bic"):
        parts.append(_agt("IntrmyAgt1", tx["intrmy_bic"]))
    parts.append(_party("Dbtr", tx["dbtr"]))
    parts.append(_acct("DbtrAcct", tx["dbtr"]))
    parts.append(_agt("DbtrAgt", tx["dbtr_agt_bic"]))
    parts.append(_agt("CdtrAgt", tx["cdtr_agt_bic"]))
    parts.append(_party("Cdtr", tx["cdtr"]))
    parts.append(_acct("CdtrAcct", tx["cdtr"]))
    if tx.get("rmt_ustrd"):
        parts.append("<pacs:RmtInf><pacs:Ustrd>%s</pacs:Ustrd></pacs:RmtInf>"
                     % escape(tx["rmt_ustrd"]))
    return (
        '<pacs:Document xmlns:pacs="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">'
        "<pacs:FIToFICstmrCdtTrf><pacs:GrpHdr>"
        "<pacs:MsgId>%(msg_id)s</pacs:MsgId><pacs:CreDtTm>%(cre_dt)s</pacs:CreDtTm>"
        "<pacs:NbOfTxs>1</pacs:NbOfTxs>"
        "<pacs:SttlmInf><pacs:SttlmMtd>INDA</pacs:SttlmMtd></pacs:SttlmInf>"
        "</pacs:GrpHdr><pacs:CdtTrfTxInf>%(tx)s</pacs:CdtTrfTxInf>"
        "</pacs:FIToFICstmrCdtTrf></pacs:Document>"
    ) % {"msg_id": tx["msg_id"], "cre_dt": tx["cre_dt"], "tx": "".join(parts)}


def build_file_content(tx, comment=""):
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    if comment:
        head += "<!-- %s -->\n" % comment.replace("--", "-")
    return head + build_apphdr(tx) + "\n" + build_document(tx) + "\n"
