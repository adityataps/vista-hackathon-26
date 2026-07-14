"""XSD validation against the official CBPR+ SR2025 schemas."""
import os

import xmlschema

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "schemas")

_cache = {}


def _schema(name):
    if name not in _cache:
        path = os.path.join(SCHEMA_DIR, name)
        if not os.path.isfile(path):
            raise RuntimeError(
                "CBPR+ XSD fehlt: %s - die MyStandards-Schemas sind lizenzpflichtig "
                "und nicht im oeffentlichen Repo. Siehe schemas/README.md, die zwei "
                "XSD-Dateien manuell in schemas/ ablegen." % path)
        _cache[name] = xmlschema.XMLSchema(path)
    return _cache[name]


def doc_schema():
    return _schema("cbpr_pacs.008.001.08.xsd")


def bah_schema():
    return _schema("cbpr_bah_head.001.001.02.xsd")


def split_fragments(file_content):
    t = file_content
    hdr = t[t.find("<head:AppHdr"):t.find("</head:AppHdr>") + len("</head:AppHdr>")]
    doc = t[t.find("<pacs:Document"):t.find("</pacs:Document>") + len("</pacs:Document>")]
    return hdr, doc


def validate(file_content):
    """Return list of error strings; empty list = fully schema-valid."""
    hdr, doc = split_fragments(file_content)
    errs = []
    for label, frag, schema in (("AppHdr", hdr, bah_schema()),
                                ("Document", doc, doc_schema())):
        for e in schema.iter_errors(frag):
            errs.append("[%s] %s | %s" % (label, e.reason, e.path))
    return errs
