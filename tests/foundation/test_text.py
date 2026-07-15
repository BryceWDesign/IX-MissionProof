"""Tests for strict text normalization."""

import pytest

from ix_missionproof.foundation import (
    FoundationError,
    normalize_labels,
    normalize_text,
    require_optional_text,
    require_text,
)


def test_normalize_text_collapses_all_whitespace() -> None:
    assert normalize_text("  evidence\n\tbefore   authority  ") == "evidence before authority"


def test_require_text_rejects_empty_content() -> None:
    with pytest.raises(FoundationError, match="summary must not be empty"):
        require_text(" \n ", field_name="summary")


def test_require_optional_text_preserves_none() -> None:
    assert require_optional_text(None, field_name="note") is None
    assert require_optional_text("  human   review ", field_name="note") == "human review"


def test_normalize_labels_preserves_first_occurrence_order() -> None:
    assert normalize_labels((" Safety ", "Evidence", "safety", "Human Review")) == (
        "safety",
        "evidence",
        "human review",
    )
