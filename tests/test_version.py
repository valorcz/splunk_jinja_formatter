import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from version import calculate_next_version, SEMVER_REGEX


def test_semver_regex():
    assert SEMVER_REGEX.match("1.0.6") is not None
    assert SEMVER_REGEX.match("2.15.0") is not None
    assert SEMVER_REGEX.match("1.0") is None
    assert SEMVER_REGEX.match("invalid") is None


def test_calculate_next_version():
    assert calculate_next_version("1.0.6", "patch") == "1.0.7"
    assert calculate_next_version("1.0.6", "minor") == "1.1.0"
    assert calculate_next_version("1.0.6", "major") == "2.0.0"

    with pytest.raises(ValueError):
        calculate_next_version("1.0.6", "invalid")
