# make_torus_rsolid

## API Definition

```python
def make_torus_rsolid(radius1: float, radius2: float, center: Tuple[float, float, float] = (0, 0, 0), axis: Tuple[float, float, float] = (0, 0, 1)) -> Solid
```

*Source: operations.py*

## Description

Create a torus (donut) solid.

## Parameters

### radius1

- **Description**: Major radius (distance from center to tube center)

### radius2

- **Description**: Minor radius (tube radius)

### center

- **Description**: Center point of the torus

### axis

- **Description**: Normal axis of the torus (default: Z-axis)

## Returns

A Solid representing a torus

## Raises

- **ValueError**: If radius1 <= radius2 or if radius2 <= 0

## Examples

```python
>>> torus = make_torus_rsolid(radius1=20, radius2=5)
```
