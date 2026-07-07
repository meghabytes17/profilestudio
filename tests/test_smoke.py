"""Smoke tests: the package imports and the CLI stub runs.
Replace with real geometry/golden-image tests as features land.
"""
import subprocess
import sys


def test_package_imports():
    import incoming_profile_utility  # noqa: F401
    assert incoming_profile_utility.__version__


def test_cli_stub_runs():
    result = subprocess.run(
        [sys.executable, "-m", "incoming_profile_utility.main"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
