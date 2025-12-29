# Shared Schema Fields

This directory contains reusable schema definitions that can be referenced by receipt schemas using JSON Schema `$ref`.

## Available Shared Schemas

| Schema | Description |
|--------|-------------|
| `privacy_fields.json` | Privacy level, redaction, disclosure proof |
| `offline_fields.json` | Offline generation metadata |
| `economic_fields.json` | SLO status, payment eligibility |
| `lineage_fields.json` | Lineage ID, merkle anchor |

## Usage

Reference shared schemas in your receipt schemas:

```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "proofpack://receipts/my_receipt",
    "allOf": [
        {"$ref": "../shared/privacy_fields.json"},
        {"$ref": "../shared/offline_fields.json"},
        {"$ref": "../shared/economic_fields.json"},
        {
            "type": "object",
            "properties": {
                "my_custom_field": {...}
            }
        }
    ]
}
```

## RNES Compliance

All shared schemas are RNES-compliant and designed to work with the base receipt schema:

- `privacy_fields.json` → RNES-FULL compliance
- `offline_fields.json` → RNES-FULL compliance
- `economic_fields.json` → RNES-FULL compliance
- `lineage_fields.json` → RNES-AUDIT compliance

## Versioning

Shared schemas follow semantic versioning. Breaking changes require new major version.

Current version: v1.0 (part of ProofPack v3.2)
