"""Run the complete local quality gate used to determine repository health."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_LOGGER = logging.getLogger("ix_missionproof.green_check")


@dataclass(frozen=True, slots=True)
class Gate:
    """One deterministic repository validation command."""

    name: str
    command: tuple[str, ...]


_GREEN_GATES: Final[tuple[Gate, ...]] = (
    Gate("format", (sys.executable, "-m", "ruff", "format", "--check", ".")),
    Gate("lint", (sys.executable, "-m", "ruff", "check", ".")),
    Gate(
        "types",
        (
            sys.executable,
            "-m",
            "mypy",
            "src",
            "tests",
            "scripts/check_green.py",
        ),
    ),
    Gate("tests", (sys.executable, "-m", "pytest", "-q")),
    Gate(
        "package",
        (
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            ".tmp/build",
        ),
    ),
)


def repository_root() -> Path:
    """Return the repository root regardless of the caller's working directory."""

    return Path(__file__).resolve().parents[1]


def green_gates() -> tuple[Gate, ...]:
    """Return the immutable ordered quality-gate definition."""

    return _GREEN_GATES


def validation_environment(root: Path) -> dict[str, str]:
    """Build a deterministic environment for local and CI validation."""

    environment = os.environ.copy()
    source_path = str(root / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        os.pathsep.join((source_path, existing_pythonpath)) if existing_pythonpath else source_path
    )
    environment["PYTHONUNBUFFERED"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return environment


def clean_build_artifacts(root: Path) -> None:
    """Remove deterministic packaging output before and after validation."""

    for path in (
        root / ".tmp" / "build",
        root / "build",
        root / "src" / "ix_missionproof.egg-info",
    ):
        shutil.rmtree(path, ignore_errors=True)


def run_gate(gate: Gate, *, root: Path, environment: dict[str, str]) -> int:
    """Run one gate and return its process exit code."""

    _LOGGER.info("\n=== %s ===", gate.name.upper())
    completed = subprocess.run(  # noqa: S603
        gate.command,
        cwd=root,
        env=environment,
        check=False,
    )
    return completed.returncode


def main() -> int:
    """Run every gate in order and stop immediately on the first failure."""

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    root = repository_root()
    clean_build_artifacts(root)

    environment = validation_environment(root)
    _LOGGER.info("IX-MissionProof green check: %s", root)

    for gate in green_gates():
        exit_code = run_gate(gate, root=root, environment=environment)
        if exit_code != 0:
            clean_build_artifacts(root)
            _LOGGER.error(
                "\nIX-MissionProof is RED: %s failed with exit code %d.",
                gate.name,
                exit_code,
            )
            return exit_code

    clean_build_artifacts(root)
    _LOGGER.info("\nIX-MissionProof is GREEN: all quality gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
