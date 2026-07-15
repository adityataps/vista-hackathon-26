# CBPR+ Schemas

The two XSDs originate from **Swift MyStandards** (CBPR+ SR2025 Usage
Guidelines):

```
schemas/cbpr_pacs.008.001.08.xsd        (UG XSD)
schemas/cbpr_bah_head.001.001.02.xsd    (BAH XSD)
```

Note: MyStandards content is subject to the Swift licence (internal use only).
Without these files, generation itself works, but the automatic XSD self-check
of every message (and the test suite) fails with a clear hint. The generated
messages themselves remain CBPR+-conformant either way.
