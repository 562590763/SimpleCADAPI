# ql_select_one

## API Definition

```python
def ql_select_one(shape: AnyShape, domain: str, query: Any, name: str = 'QL_Selection') -> Any
```

*Source: operations.py*

## Description

Select exactly one topology item with `ql_select`.

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

Any: The single selected topology object.
