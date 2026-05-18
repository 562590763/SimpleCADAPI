# select

## API Definition

```python
def select(items: Iterable[Any]) -> Query
```

*Source: ql.py*

## Description

Create a runtime query object.

Q.select(items).where(Q.tag("face.top")).first()

This helper is for runtime Python filtering. It can query arbitrary
iterables and can use custom lambdas, but the selection itself is not
recorded as a feature-history node and is not directly replayed during
FreeCAD export.

For CAD selections that must be used by later modeling operations and
exported to FreeCAD, use `scad.ql_select`,
`scad.ql_select_one`, `scad.ql_select_from`, or
`scad.ql_select_from_topology`. Those APIs execute the query in
SimpleCAD and export a snapshot of the selected CAD objects.

## Parameters

### items

- **Description**: Any iterable.

## Returns

Query: Query object.
