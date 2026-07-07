"""Smoke tests: package imports and CLI stub runs."""
import subprocess
import sys


def test_package_imports():
    import incoming_profile_utility  # noqa: F401
    assert incoming_profile_utility.__version__
