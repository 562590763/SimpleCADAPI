# ql_select_from_topology

## API Definition

```python
def ql_select_from_topology(sources: Sequence[Tuple[AnyShape, str]], query: Any, name: str = 'QL_Multi_Topology_Selection') -> List[Any]
```

*Source: operations.py*

## Description

Select topology across multiple base shapes and record replay references.

largest_face = scad.ql_select_one_from_topology(
[(left_body, "faces"), (right_body, "faces")],
scad.ql.query()
.order_by(scad.ql.geo("area"), desc=True)
.take(1)
.exactly(1),
)

Lambda predicates are exported as result snapshots: SimpleCAD runs the
lambda, then FreeCAD re-binds the selected face/edge/wire/vertex by
base feature id, topology index, and geometry signature.

## Parameters

### sources

- **Description**: Sequence of `(shape, domain)` pairs. Domains are `faces`, `edges`, `wires`, or `vertices`.

### query

- **Description**: A `simplecadapi.ql.QuerySpec` or a runtime predicate/lambda.

### name

- **Description**: Feature name used in exported history and FreeCAD scripts.

## Returns

List[Any]: Selected topology objects.
