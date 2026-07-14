"""pacs.008 CBPR+ sample generator with configurable business-error injection.

Vista Hackathon - Use Case A (SWIFT Exceptions & Investigations).
All generated messages are schema-valid against the official CBPR+ SR2025 XSDs;
injected errors are BUSINESS errors (invalid IBAN checksum, BIC/IBAN mismatch,
incomplete beneficiary, ...) that pass XSD validation by design.
"""
__version__ = "0.1.0"
