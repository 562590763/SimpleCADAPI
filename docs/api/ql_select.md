# ql_select

## API Definition

```python
def ql_select(shape: AnyShape, domain: str, query: Any, name: str = 'QL_Selection') -> List[Any]
```

*Source: operations.py*

## Description

Select topology with QL and record the selected CAD objects as a feature.

top_face = scad.ql_select_one(
cylinder,
"faces",
scad.ql.query()
.where(scad.ql.tag("extrusion end face"))
.take(1)
.exactly(1),
name="Selected_Extrusion_Top_Face",
)

Lambdas are supported as snapshot selections:

selected_edges = scad.ql_select(
body,
"edges",
lambda edge: edge.get_length() > 10.0,
)

The lambda runs when the SimpleCAD script runs. FreeCAD export does
not re-run arbitrary Python lambdas; it re-binds the selected result
using topology indices and geometry signatures.

## Parameters

### shape

- **Description**: Base SimpleCAD shape to select from.

### domain

- **Description**: Topology domain: `faces`, `edges`, `wires`, or `vertices`.

### query

- **Description**: A `simplecadapi.ql.QuerySpec` or a runtime predicate/lambda.

### name

- **Description**: Feature name used in exported history and FreeCAD scripts.

## Returns

List[Any]: Selected topology objects.
