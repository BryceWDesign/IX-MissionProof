"""Tests for the repository green-check command."""

import os
import sys
from pathlib import Path

from scripts.check_green import (
    clean_build_artifacts,
    green_gates,
    repository_root,
    validation_environment,
)


def test_green_gates_are_complete_and_ordered() -> None:
    gates = green_gates()

    assert tuple(gate.name for gate in gates) == (
        "format",
        "lint",
        "types",
        "tests",
        "package",
    )
    assert all(gate.command[0] == sys.executable for gate in gates)
    assert "--wheel" in gates[-1].command
    assert "--sdist" not in gates[-1].command


def test_repository_root_contains_project_configuration() -> None:
    assert (repository_root() / "pyproject.toml").is_file()


def test_validation_environment_prepends_source_directory() -> None:
    root = Path("repository").resolve()
    environment = validation_environment(root)

    assert environment["PYTHONPATH"].split(os.pathsep)[0] == str(root / "src")
    assert environment["PYTHONUNBUFFERED"] == "1"
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert environment["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"


def test_clean_build_artifacts_removes_only_known_build_directories(tmp_path: Path) -> None:
    package_metadata = tmp_path / "src" / "ix_missionproof.egg-info"
    wheel_output = tmp_path / ".tmp" / "build"
    build_directory = tmp_path / "build"
    retained_file = tmp_path / "src" / "ix_missionproof" / "module.py"

    for directory in (package_metadata, wheel_output, build_directory):
        directory.mkdir(parents=True)
        (directory / "generated.txt").write_text("generated", encoding="utf-8")
    retained_file.parent.mkdir(parents=True)
    retained_file.write_text("retained", encoding="utf-8")

    clean_build_artifacts(tmp_path)

    assert not package_metadata.exists()
    assert not wheel_output.exists()
    assert not build_directory.exists()
    assert retained_file.read_text(encoding="utf-8") == "retained"
