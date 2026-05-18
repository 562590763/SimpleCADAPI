# ql_select_from

## API Definition

```python
def ql_select_from(items: Sequence[Any], query: Any, name: str = 'QL_List_Selection') -> List[Any]
```

*Source: operations.py*

## Description

Select from an explicit list of feature outputs and record the result.

largest_part = scad.ql_select_one_from(
[box, cylinder, bracket],
scad.ql.query()
.order_by(scad.ql.geo("volume"), desc=True)
.take(1)
.exactly(1),
)

Export works for SimpleCAD CAD objects that have feature ids. Plain
dictionaries or arbitrary Python objects are runtime-only unless they
implement a future export protocol.

## Parameters

### items

- **Description**: Sequence of SimpleCAD feature outputs.

### query

- **Description**: A `simplecadapi.ql.QuerySpec` or a runtime predicate/lambda.

### name

- **Description**: Feature name used in exported history and FreeCAD scripts.

## Returns

List[Any]: Selected feature outputs.
