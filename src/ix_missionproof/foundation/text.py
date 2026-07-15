"""Strict text normalization shared across MissionProof domains."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ix_missionproof.foundation.errors import FoundationError

_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Trim text and collapse every internal whitespace run to one space."""

    if not isinstance(value, str):
        raise FoundationError("value must be text")
    return _WHITESPACE_PATTERN.sub(" ", value.strip())


def require_text(value: str, *, field_name: str) -> str:
    """Return normalized non-empty text for a required field."""

    if not isinstance(field_name, str):
        raise FoundationError("field_name must be text")
    normalized_field_name = normalize_text(field_name)
    if not normalized_field_name:
        raise FoundationError("field_name must not be empty")

    normalized = normalize_text(value)
    if not normalized:
        raise FoundationError(f"{normalized_field_name} must not be empty")
    return normalized


def require_optional_text(value: str | None, *, field_name: str) -> str | None:
    """Normalize optional text while preserving an omitted value as ``None``."""

    if value is None:
        return None
    return require_text(value, field_name=field_name)


def normalize_labels(values: Iterable[str], *, field_name: str = "labels") -> tuple[str, ...]:
    """Normalize and de-duplicate labels while preserving declaration order."""

    normalized_field_name = require_text(field_name, field_name="field_name")
    labels: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        label = require_text(value, field_name=f"{normalized_field_name}[{index}]").lower()
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return tuple(labels)
