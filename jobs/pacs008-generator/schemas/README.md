# CBPR+ Schemas (nicht im oeffentlichen Repo)

Die zwei benoetigten XSDs stammen aus **Swift MyStandards** (CBPR+ SR2025 Usage
Guidelines) und unterliegen der MyStandards-Lizenz (nur interner Gebrauch) —
deshalb sind sie hier **nicht eingecheckt**.

Vor dem ersten Lauf diese zwei Dateien in diesen Ordner legen
(Quelle: internes Team-Repo `subscript-jpg/vista-hackathon-2026` oder Michel):

```
schemas/cbpr_pacs.008.001.08.xsd        (UG-XSD  "..._iso15.xsd")
schemas/cbpr_bah_head.001.001.02.xsd    (BAH-XSD "bah_..._iso15enriched.xsd")
```

Ohne die Dateien funktioniert die Generierung technisch, aber der automatische
XSD-Self-Check jeder Meldung (und die Test-Suite) schlaegt mit einem klaren
Hinweis fehl. Die erzeugten Meldungen selbst sind unveraendert CBPR+-konform.
