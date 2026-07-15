"""Tests for deterministic JSON serialization."""

from typing import cast

import pytest

from ix_missionproof.foundation import (
    FoundationError,
    JsonValue,
    canonical_json,
    canonical_json_bytes,
    require_json_value,
)


def test_canonical_json_is_compact_sorted_and_utf8_safe() -> None:
    payload: JsonValue = {"z": 1, "a": ["évidence", True, None]}

    assert canonical_json(payload) == '{"a":["évidence",true,null],"z":1}'
    assert canonical_json_bytes(payload) == '{"a":["évidence",true,null],"z":1}'.encode()


def test_canonical_json_preserves_array_order() -> None:
    assert canonical_json(["third", "first", "second"]) == '["third","first","second"]'


def test_require_json_value_reports_nested_invalid_type() -> None:
    invalid = cast(JsonValue, {"evidence": ["valid", object()]})

    with pytest.raises(
        FoundationError,
        match=r"payload\.evidence\[1\] contains unsupported JSON value type object",
    ):
        require_json_value(invalid)


def test_canonical_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(FoundationError, match="must not contain a non-finite number"):
        canonical_json([float("inf")])
