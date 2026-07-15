"""Canonical human-readable identifiers for MissionProof records."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ix_missionproof.foundation.errors import FoundationError
from ix_missionproof.foundation.text import require_text

_KEY_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")
_VALID_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True, order=True)
class CanonicalKey:
    """A stable lowercase key with hyphen-separated alphanumeric segments."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise FoundationError("canonical key value must be text")
        if not _VALID_KEY_PATTERN.fullmatch(self.value):
            raise FoundationError(
                "canonical key must contain lowercase alphanumeric segments separated by hyphens"
            )

    @classmethod
    def from_text(cls, value: str, *, field_name: str) -> CanonicalKey:
        """Construct a canonical key from normalized human-readable text."""

        text = require_text(value, field_name=field_name).lower()
        collapsed = _KEY_SEPARATOR_PATTERN.sub("-", text).strip("-")
        if not collapsed:
            raise FoundationError(f"{field_name} must contain an alphanumeric character")
        return cls(collapsed)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class ScopedIdentifier:
    """A canonical identifier composed of a namespace and local key."""

    namespace: CanonicalKey
    key: CanonicalKey

    @classmethod
    def create(
        cls,
        *,
        namespace: str,
        key: str,
        namespace_field: str = "namespace",
        key_field: str = "key",
    ) -> ScopedIdentifier:
        """Create a normalized scoped identifier from text values."""

        return cls(
            namespace=CanonicalKey.from_text(namespace, field_name=namespace_field),
            key=CanonicalKey.from_text(key, field_name=key_field),
        )

    @classmethod
    def parse(cls, value: str, *, field_name: str = "identifier") -> ScopedIdentifier:
        """Parse the canonical ``namespace:key`` representation."""

        normalized = require_text(value, field_name=field_name)
        namespace, separator, key = normalized.partition(":")
        if separator != ":" or not namespace or not key or ":" in key:
            raise FoundationError(f"{field_name} must use the form namespace:key")
        return cls.create(
            namespace=namespace,
            key=key,
            namespace_field=f"{field_name} namespace",
            key_field=f"{field_name} key",
        )

    def __str__(self) -> str:
        return f"{self.namespace}:{self.key}"
