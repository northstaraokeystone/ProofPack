# Contributing to RNES

## Proposing Changes

RNES follows a structured change process to ensure stability while allowing evolution.

### Change Categories

| Category | Process | Timeline |
|----------|---------|----------|
| Clarification | PR with rationale | 1 week review |
| New optional field | RFC + PR | 2 week review |
| New required field | RFC + migration path | 4 week review |
| Breaking change | RFC + 2 version notice | 8 week review |

### RFC Process

1. **Draft**: Create `rfcs/NNNN-title.md` with:
   - Problem statement
   - Proposed solution
   - Backward compatibility analysis
   - Migration path (if breaking)

2. **Review**: Open PR, tag maintainers
   - Discussion period based on category
   - Minimum 2 maintainer approvals required

3. **Implementation**: After approval:
   - Update RNES_v1.md (or create v2.md if breaking)
   - Update JSON schemas
   - Update validation scripts
   - Add test cases

## Schema Contributions

### Adding a New Receipt Type

1. Create schema in `schemas/` following `_base.schema.json`
2. Include all RNES-CORE fields
3. Add validation tests
4. Document in RNES spec

### Schema Format

```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "rnes://receipts/your_type",
    "allOf": [
        {"$ref": "receipt_base.schema.json"},
        {
            "type": "object",
            "properties": {
                "your_field": {...}
            }
        }
    ]
}
```

## Validation Suite

All changes must pass:

```bash
# Core validation
./validate.sh

# Schema validation
python -m jsonschema -i test_receipt.json schemas/your_type.schema.json

# Interop tests
pytest tests/test_interop.py
```

## Maintainers

- Keystone Research Lab (primary)

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0.

---

*Questions? Open an issue with the `question` label.*
