#!/usr/bin/env python3
"""Script to get, set, or bump the Splunk app version consistently across all files."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_CONF_FILE = ROOT_DIR / "jinja_formatter" / "default" / "app.conf"
APP_MANIFEST_FILE = ROOT_DIR / "jinja_formatter" / "app.manifest"
PYPROJECT_FILE = ROOT_DIR / "pyproject.toml"

SEMVER_REGEX = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


def get_current_version() -> str:
    """Read the current version from app.conf."""
    if not APP_CONF_FILE.is_file():
        raise FileNotFoundError(f"Missing {APP_CONF_FILE}")

    content = APP_CONF_FILE.read_text(encoding="utf-8")
    match = re.search(r"(?m)^\s*version\s*=\s*([0-9A-Za-z.-]+)", content)
    if not match:
        raise ValueError(f"Could not find version property in {APP_CONF_FILE}")
    return match.group(1).strip()


def calculate_next_version(current_version: str, bump_type: str) -> str:
    """Calculate next version based on bump type (patch, minor, major)."""
    match = SEMVER_REGEX.match(current_version)
    if not match:
        raise ValueError(
            f"Current version '{current_version}' does not match SemVer/Splunk format Major.Minor.Revision"
        )

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))

    bump_type = bump_type.lower()
    if bump_type in ("patch", "revision"):
        patch += 1
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"Unknown bump type '{bump_type}'. Choose from: patch, minor, major")

    return f"{major}.{minor}.{patch}"


def update_app_conf(new_version: str):
    """Update version in app.conf in both [id] and [launcher] stanzas."""
    content = APP_CONF_FILE.read_text(encoding="utf-8")

    # Replace version = ... lines
    updated_content = re.sub(
        r"(?m)^(\s*version\s*=\s*).*$",
        rf"\g<1>{new_version}",
        content,
    )
    APP_CONF_FILE.write_text(updated_content, encoding="utf-8")


def update_app_manifest(new_version: str):
    """Update version in app.manifest."""
    if not APP_MANIFEST_FILE.is_file():
        return

    content = APP_MANIFEST_FILE.read_text(encoding="utf-8")
    data = json.loads(content)
    try:
        data["info"]["id"]["version"] = new_version
    except KeyError:
        # Fallback to regex if manifest structure is atypical
        updated_content = re.sub(
            r'("version"\s*:\s*)"[^"]*"',
            rf'\1"{new_version}"',
            content,
            count=1,
        )
        APP_MANIFEST_FILE.write_text(updated_content, encoding="utf-8")
        return

    APP_MANIFEST_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_pyproject(new_version: str):
    """Update version in pyproject.toml."""
    if not PYPROJECT_FILE.is_file():
        return

    content = PYPROJECT_FILE.read_text(encoding="utf-8")
    updated_content = re.sub(
        r'(?m)^(\s*version\s*=\s*)"[^"]*"',
        rf'\g<1>"{new_version}"',
        content,
    )
    PYPROJECT_FILE.write_text(updated_content, encoding="utf-8")


def sync_lockfile():
    """Sync lockfile if uv is available."""
    if shutil.which("uv"):
        try:
            subprocess.run(["uv", "lock"], cwd=str(ROOT_DIR), check=True, capture_output=True)
        except Exception:
            pass


def set_version(new_version: str) -> str:
    """Validate and set new version across all project files."""
    if not SEMVER_REGEX.match(new_version):
        raise ValueError(
            f"Invalid version '{new_version}'. Splunk AppInspect requires Major.Minor.Revision format (e.g. 1.0.7)"
        )

    current_version = get_current_version()
    if current_version == new_version:
        print(f"Version is already {new_version}")
        return new_version

    print(f"Updating version: {current_version} -> {new_version}")

    update_app_conf(new_version)
    print(f"  Updated: {APP_CONF_FILE.relative_to(ROOT_DIR)}")

    update_app_manifest(new_version)
    print(f"  Updated: {APP_MANIFEST_FILE.relative_to(ROOT_DIR)}")

    update_pyproject(new_version)
    print(f"  Updated: {PYPROJECT_FILE.relative_to(ROOT_DIR)}")

    sync_lockfile()
    print(f"Successfully updated version to {new_version}")
    return new_version


def main():
    parser = argparse.ArgumentParser(description="Manage Splunk app version consistently")
    parser.add_argument(
        "target",
        nargs="?",
        help="Target version (e.g. 1.0.7) or bump type (patch, minor, major)",
    )
    parser.add_argument(
        "--bump",
        choices=["patch", "minor", "major"],
        help="Bump version by patch, minor, or major",
    )
    parser.add_argument(
        "--current",
        action="store_true",
        help="Print the current version and exit",
    )

    args = parser.parse_args()
    current_version = get_current_version()

    if args.current or (not args.target and not args.bump):
        print(current_version)
        return

    bump_type = args.bump
    target_version = args.target

    if target_version in ("patch", "minor", "major"):
        bump_type = target_version
        target_version = None

    if bump_type:
        new_version = calculate_next_version(current_version, bump_type)
    elif target_version:
        new_version = target_version
    else:
        print(current_version)
        return

    set_version(new_version)


if __name__ == "__main__":
    main()
