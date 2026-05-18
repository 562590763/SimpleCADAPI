from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional


Predicate = Callable[[Any], bool]
KeyFn = Callable[[Any], Any]


def _get_tags(obj: Any) -> List[str]:
    """Read the tag list from an object.

    Args:
        obj: Any object. Reads `get_tags()` first, then `_tags`.

    Returns:
        List[str]: Tag list, or an empty list if not found.
    """
    if hasattr(obj, "get_tags"):
        try:
            return list(obj.get_tags())
        except Exception:
            return []
    tags = getattr(obj, "_tags", None)
    if tags is None:
        return []
    return list(tags)


def _get_metadata_root(obj: Any) -> dict:
    """Read the metadata dictionary from an object.

    Args:
        obj: Any object. Reads `_metadata` when available.

    Returns:
        dict: Root metadata dictionary, or an empty dict if not found.
    """
    root = getattr(obj, "_metadata", None)
    if isinstance(root, dict):
        return root
    return {}


def _lookup_metadata(obj: Any, path: str) -> Any:
    """Read object metadata by dotted path.

    Args:
        obj: Any object.
        path: Dot-separated path, for example `geo.type`.

    Returns:
        Any: Matched value, or None if not found.
    """
    if not isinstance(path, str) or not path:
        return None
    segments = path.split(".")
    current: Any = _get_metadata_root(obj)
    for seg in segments:
        if isinstance(current, dict) and seg in current:
            current = current[seg]
        else:
            return None
    return current


def tag(pattern: str) -> Predicate:
    """Build a tag-based predicate.

    Args:
        pattern: Tag matching pattern. Supports a trailing `*` wildcard.

    Returns:
        Callable[[Any], bool]: Predicate function.

    Raises:
        TypeError: If pattern is not a string.
        ValueError: If the wildcard position is invalid.

    Usage:
        `Q.tag("face.top")` or `Q.tag("role.*")`.

    Examples:
        pred = Q.tag("role.*")
        matched = pred(obj)
    """
    if not isinstance(pattern, str):
        raise TypeError("pattern must be a string")

    pattern = pattern.strip()
    if "*" in pattern and not pattern.endswith("*"):
        raise ValueError("only trailing '*' wildcard is supported")

    if pattern.endswith("*"):
        prefix = pattern[:-1]

        def _predicate(obj: Any) -> bool:
            return any(tag.startswith(prefix) for tag in _get_tags(obj))

        setattr(_predicate, "_ql_expr", {"op": "tag", "pattern": pattern})
        return _predicate

    def _predicate(obj: Any) -> bool:
        return pattern in _get_tags(obj)

    setattr(_predicate, "_ql_expr", {"op": "tag", "pattern": pattern})
    return _predicate


def meta(path: str, op: str, value: Any) -> Predicate:
    """Build a metadata-based predicate.

    Args:
        path: Metadata path, for example `geo.type`.
        op: Comparison operator. Supports `==`, `!=`, `>`, `>=`, `<`, and `<=`.
        value: Comparison target value.

    Returns:
        Callable[[Any], bool]: Predicate function.

    Raises:
        TypeError: If op is not a string.
        ValueError: If the operator is unsupported.

    Usage:
        Q.meta("geo.type", "==", "box")

    Examples:
        pred = Q.meta("geo.size.x", ">", 1.0)
        matched = pred(obj)
    """
    if not isinstance(op, str):
        raise TypeError("op must be a string")

    op = op.strip()

    def _predicate(obj: Any) -> bool:
        actual = _lookup_metadata(obj, path)
        if op == "==":
            return actual == value
        if op == "!=":
            return actual != value
        if actual is None:
            return False
        try:
            if op == ">":
                return actual > value
            if op == ">=":
                return actual >= value
            if op == "<":
                return actual < value
            if op == "<=":
                return actual <= value
        except Exception:
            return False
        raise ValueError(f"unsupported op: {op}")

    setattr(_predicate, "_ql_expr", {"op": "meta", "path": path, "cmp": op, "value": value})
    return _predicate


def value(path: str, default: Any = None) -> KeyFn:
    """Build a value getter for sorting or projection.

    Args:
        path: Metadata path, for example `geo.height`.
        default: Default value when lookup fails.

    Returns:
        Callable[[Any], Any]: Getter function.

    Usage:
        Q.select(items).order_by(Q.value("geo.height"))

    Examples:
        key = Q.value("geo.height", 0.0)
        height = key(obj)
    """

    def _getter(obj: Any) -> Any:
        actual = _lookup_metadata(obj, path)
        if actual is not None:
            return actual

        if path.startswith("geo."):
            remainder = path.split(".", 1)[1]
            if "." not in remainder:
                if remainder == "area" and hasattr(obj, "get_area"):
                    try:
                        return obj.get_area()
                    except Exception:
                        return default
                if remainder == "length" and hasattr(obj, "get_length"):
                    try:
                        return obj.get_length()
                    except Exception:
                        return default
                if remainder == "volume" and hasattr(obj, "get_volume"):
                    try:
                        return obj.get_volume()
                    except Exception:
                        return default
        return default

    setattr(_getter, "_ql_expr", {"op": "value", "path": path, "default": default})
    return _getter


def geo(field: str, default: Any = None) -> KeyFn:
    """Convenience builder for a `geo` metadata getter.

    Args:
        field: `geo` field name, such as `type` or `height`.
        default: Default value when lookup fails.

    Returns:
        Callable[[Any], Any]: Getter function.

    Usage:
        Q.select(items).order_by(Q.geo("height"))
    """
    getter = value(f"geo.{field}", default)
    setattr(getter, "_ql_expr", {"op": "geo", "field": field, "default": default})
    return getter


def and_(*predicates: Predicate) -> Predicate:
    """Build an AND-composed predicate.

    Args:
        *predicates: Any number of predicates.

    Returns:
        Callable[[Any], bool]: Combined predicate.

    Usage:
        Q.and_(Q.tag("face.top"), Q.tag("role.mounting_surface"))
    """

    def _predicate(obj: Any) -> bool:
        for pred in predicates:
            if not pred(obj):
                return False
        return True

    setattr(
        _predicate,
        "_ql_expr",
        {
            "op": "and",
            "children": [getattr(pred, "_ql_expr", None) for pred in predicates],
        },
    )
    return _predicate


def or_(*predicates: Predicate) -> Predicate:
    """Build an OR-composed predicate.

    Args:
        *predicates: Any number of predicates.

    Returns:
        Callable[[Any], bool]: Combined predicate.

    Usage:
        Q.or_(Q.tag("face.top"), Q.tag("face.bottom"))
    """

    def _predicate(obj: Any) -> bool:
        for pred in predicates:
            if pred(obj):
                return True
        return False

    setattr(
        _predicate,
        "_ql_expr",
        {
            "op": "or",
            "children": [getattr(pred, "_ql_expr", None) for pred in predicates],
        },
    )
    return _predicate


def not_(predicate: Predicate) -> Predicate:
    """Build a NOT predicate.

    Args:
        predicate: A single predicate.

    Returns:
        Callable[[Any], bool]: Negated predicate.

    Usage:
        Q.not_(Q.tag("state.*"))
    """

    def _predicate(obj: Any) -> bool:
        return not predicate(obj)

    setattr(
        _predicate,
        "_ql_expr",
        {"op": "not", "child": getattr(predicate, "_ql_expr", None)},
    )
    return _predicate


class QuerySpec:
    """Serializable query description that can also run in Python."""

    def __init__(
        self,
        predicates: Optional[List[Predicate]] = None,
        orderings: Optional[List[tuple[KeyFn, bool]]] = None,
        count: Optional[int] = None,
        exact_count: Optional[int] = None,
    ):
        self._predicates = list(predicates or [])
        self._orderings = list(orderings or [])
        self._count = count
        self._exact_count = exact_count

    def where(self, predicate: Predicate) -> "QuerySpec":
        return QuerySpec(
            self._predicates + [predicate],
            self._orderings,
            self._count,
            self._exact_count,
        )

    def order_by(self, key: KeyFn, desc: bool = False) -> "QuerySpec":
        return QuerySpec(
            self._predicates,
            self._orderings + [(key, desc)],
            self._count,
            self._exact_count,
        )

    def limit(self, count: int) -> "QuerySpec":
        return QuerySpec(self._predicates, self._orderings, count, self._exact_count)

    def take(self, count: int) -> "QuerySpec":
        return self.limit(count)

    def exactly(self, count: int) -> "QuerySpec":
        return QuerySpec(self._predicates, self._orderings, self._count, count)

    def resolve(self, items: Iterable[Any]) -> List[Any]:
        result = list(items)
        for predicate in self._predicates:
            result = [item for item in result if predicate(item)]
        for key, desc in self._orderings:
            def _safe_key(obj: Any):
                value = key(obj)
                return (value is None, value)

            result = sorted(result, key=_safe_key, reverse=desc)
        if self._count is not None:
            result = result[: max(self._count, 0)]
        if self._exact_count is not None and len(result) != self._exact_count:
            raise ValueError(
                f"query expected exactly {self._exact_count} result(s), got {len(result)}"
            )
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "where": [getattr(pred, "_ql_expr", None) for pred in self._predicates],
            "order_by": [
                {"key": getattr(key, "_ql_expr", None), "desc": desc}
                for key, desc in self._orderings
            ],
            "limit": self._count,
            "exactly": self._exact_count,
        }


def query() -> QuerySpec:
    """Create a serializable query spec for exportable topology selections."""
    return QuerySpec()


class Query:
    def __init__(self, items: Iterable[Any]):
        """Create a query object.

        Args:
            items: Any iterable.
        """
        self._items = list(items)

    def where(self, predicate: Predicate) -> "Query":
        """Filter objects with a predicate.

        Args:
            predicate: Filter predicate.

        Returns:
            Query: New query object.
        """
        return Query([item for item in self._items if predicate(item)])

    def order_by(self, key: KeyFn, desc: bool = False) -> "Query":
        """Sort by key.

        Args:
            key: Getter function.
            desc: Whether to sort in descending order.

        Returns:
            Query: New query object.
        """

        def _safe_key(obj: Any):
            value = key(obj)
            return (value is None, value)

        return Query(sorted(self._items, key=_safe_key, reverse=desc))

    def limit(self, count: int) -> "Query":
        """Limit the number of returned items.

        Args:
            count: Maximum number of items.

        Returns:
            Query: New query object.
        """
        if count <= 0:
            return Query([])
        return Query(self._items[:count])

    def first(self) -> Optional[Any]:
        """Return the first item.

        Returns:
            Optional[Any]: First item or None.
        """
        return self._items[0] if self._items else None

    def all(self) -> List[Any]:
        """Return all results.

        Returns:
            List[Any]: Result list.
        """
        return list(self._items)


def select(items: Iterable[Any]) -> Query:
    """Create a runtime query object.

    Args:
        items: Any iterable.

    Returns:
        Query: Query object.

    Usage:
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
    """
    return Query(items)
