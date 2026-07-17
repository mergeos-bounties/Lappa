# Path Fixture Precision Rules

## `path_length_m` Must Store Full Float Values

When creating or editing sample path fixtures (`fixtures/sample_path_*.json`),
the `path_length_m` field **must store the complete floating-point value**.
Do **not** round or truncate this value.

### Why

Tests verify path length against the fixture using:

```python
assert abs(length - float(data["path_length_m"])) < 1e-6
```

Rounding `path_length_m` will cause assertion failures when the computed
geometric distance differs from the rounded stored value by more than 1 µm.

### Example

✅ Correct: `"path_length_m": 4.23606797749979`
❌ Wrong:   `"path_length_m": 4.24`
❌ Wrong:   `"path_length_m": 4.2`

### How to Compute

Use the same formula as the test fixtures — sum of Euclidean distances between
consecutive points:

```python
import math
length = sum(
    math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
    for p1, p2 in zip(points[:-1], points[1:])
)
```

Store the result with full precision (Python's default float repr).
