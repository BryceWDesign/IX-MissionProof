"""Immutable canonical JSON documents for evidence-bearing records."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ix_missionproof.foundation.digests import ContentDigest
from ix_missionproof.foundation.errors import FoundationError
from ix_missionproof.foundation.identifiers import CanonicalKey
from ix_missionproof.foundation.serialization import (
    JsonObject,
    JsonValue,
    canonical_json,
    require_json_value,
)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FoundationError(f"canonical JSON document contains duplicate object key: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> object:
    raise FoundationError(f"canonical JSON document contains invalid numeric constant: {value}")


def _parse_document(value: str) -> JsonValue:
    try:
        parsed = json.loads(
            value,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except json.JSONDecodeError as error:
        raise FoundationError("canonical JSON document must contain valid JSON") from error
    return require_json_value(parsed, field_name="document")


@dataclass(frozen=True, slots=True, order=True)
class CanonicalJsonDocument:
    """An immutable canonical JSON snapshot suitable for hashing and replay."""

    serialized: str

    def __post_init__(self) -> None:
        if not isinstance(self.serialized, str):
            raise FoundationError("serialized document must be text")
        if not self.serialized:
            raise FoundationError("serialized document must not be empty")

        parsed = _parse_document(self.serialized)
        if canonical_json(parsed) != self.serialized:
            raise FoundationError("serialized document must use canonical JSON encoding")

    @classmethod
    def from_value(cls, value: JsonValue) -> CanonicalJsonDocument:
        """Capture a JSON value as an immutable canonical snapshot."""

        return cls(canonical_json(value))

    def to_value(self) -> JsonValue:
        """Return a newly parsed JSON value that cannot mutate this document."""

        return _parse_document(self.serialized)

    def require_object(self) -> JsonObject:
        """Return this document as an object or reject a non-object root."""

        value = self.to_value()
        if not isinstance(value, dict):
            raise FoundationError("canonical JSON document root must be an object")
        return value

    def digest(self, *, domain: CanonicalKey | str) -> ContentDigest:
        """Return a domain-separated digest of the captured JSON value."""

        return ContentDigest.from_payload(self.to_value(), domain=domain)

    def __bytes__(self) -> bytes:
        return self.serialized.encode("utf-8")

    def __str__(self) -> str:
        return self.serialized
