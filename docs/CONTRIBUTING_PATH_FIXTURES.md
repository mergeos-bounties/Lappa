# Contributing Path Fixtures

## Overview

This document describes the rules and conventions for contributing path fixtures to Lappa.

## Precision Rules

### path_length_m

The `path_length_m` field must store the **full float value** (not rounded) so that tests pass.

**Correct:**
```json
{
  "path_length_m": 12.3456789012345
}
```

**Incorrect:**
```json
{
  "path_length_m": 12.35
}
```

### Why Precision Matters

1. **Test Stability**: Tests compare exact values, so rounding causes flaky failures
2. **Reproducibility**: Full precision ensures consistent results across environments
3. **Scientific Accuracy**: Robot navigation requires high precision for safety

### Precision Guidelines

| Field | Required Precision | Example |
|-------|-------------------|---------|
| path_length_m | 10+ decimal places | 12.3456789012345 |
| coordinates (x, y, z) | 6+ decimal places | 1.234567 |
| angles (yaw, pitch, roll) | 6+ decimal places | 0.123456 |
| timestamps | ISO 8601 full | 2024-01-15T10:30:00.000000Z |

## Fixture Structure

```json
{
  "id": "unique_fixture_id",
  "name": "Human-readable name",
  "description": "What this fixture tests",
  "path": [
    {"x": 0.0, "y": 0.0, "z": 0.0},
    {"x": 1.0, "y": 0.0, "z": 0.0}
  ],
  "path_length_m": 1.0000000000000,
  "metadata": {
    "created_by": "contributor",
    "created_at": "2024-01-15T10:30:00.000000Z",
    "purpose": "testing"
  }
}
```

## Testing Requirements

Before submitting a fixture:

1. **Validate JSON**: Ensure valid JSON structure
2. **Check Precision**: Verify all float fields have sufficient precision
3. **Run Tests**: Execute `pytest tests/` to confirm no regressions
4. **Document Purpose**: Explain what the fixture tests in the PR description

## Common Mistakes

### Mistake 1: Rounded path_length_m
```json
// ❌ Wrong
"path_length_m": 10.0

// ✅ Correct
"path_length_m": 10.0000000000000
```

### Mistake 2: Integer coordinates
```json
// ❌ Wrong
{"x": 1, "y": 2, "z": 0}

// ✅ Correct
{"x": 1.000000, "y": 2.000000, "z": 0.000000}
```

### Mistake 3: Missing metadata
```json
// ❌ Wrong
{
  "id": "test",
  "path": []
}

// ✅ Correct
{
  "id": "test",
  "name": "Test fixture",
  "description": "Tests empty path edge case",
  "path": [],
  "metadata": {
    "created_by": "contributor",
    "purpose": "testing"
  }
}
```

## PR Checklist

- [ ] JSON is valid
- [ ] path_length_m has 10+ decimal places
- [ ] Coordinates have 6+ decimal places
- [ ] Metadata includes created_by and purpose
- [ ] Tests pass locally
- [ ] PR description explains fixture purpose

## Questions?

Open an issue or comment on the PR for clarification.
