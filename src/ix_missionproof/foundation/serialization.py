"""Deterministic JSON serialization for replayable MissionProof records."""

from __future__ import annotations

import json
import math
from typing import TypeAlias, cast

from ix_missionproof.foundation.errors import FoundationError

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonArray: TypeAlias = list["JsonValue"]
JsonObject: TypeAlias = dict[str, "JsonValue"]
JsonValue: TypeAlias = JsonPrimitive | JsonArray | JsonObject


def _validate_json_value(value: object, *, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FoundationError(f"{path} must not contain a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise FoundationError(f"{path} must contain only text object keys")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise FoundationError(f"{path} contains unsupported JSON value type {type(value).__name__}")


def require_json_value(value: object, *, field_name: str = "payload") -> JsonValue:
    """Validate and return a value composed only of supported JSON types."""

    _validate_json_value(value, path=field_name)
    return cast(JsonValue, value)


def canonical_json(payload: JsonValue) -> str:
    """Encode JSON data deterministically for evidence records and digests."""

    require_json_value(payload)
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_json_bytes(payload: JsonValue) -> bytes:
    """Return the UTF-8 bytes of the canonical JSON representation."""

    return canonical_json(payload).encode("utf-8")
