"""Canonical serialization, so "identical Decision" is a checkable claim.

Determinism is only testable if two Decisions can be compared byte-for-byte.
That requires one canonical encoding, fixed here and specified in
``docs/CONFORMANCE.md`` so a non-Python implementation can produce the same
bytes.

Pure: no clock, no randomness, no I/O. ``json`` is stdlib serialization only.

Rules (normative):
  * UTF-8, object keys sorted lexicographically by code point
  * no insignificant whitespace — separators are ``,`` and ``:``
  * non-ASCII characters emitted literally, not escaped
  * enum members encode as their string values
  * sequences preserve order (order is evidence, not presentation)
  * absent optional fields encode as JSON ``null``, never omitted
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def to_plain(value: Any) -> Any:
    """Reduce a model, enum, or container to JSON-native types."""
    if isinstance(value, BaseModel):
        return {k: to_plain(v) for k, v in value.model_dump(mode="json").items()}
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    """Encode ``value`` in the canonical form defined above."""
    return json.dumps(
        to_plain(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


__all__ = ["canonical_json", "to_plain"]
