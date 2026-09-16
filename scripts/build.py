#!/usr/bin/env python3
"""Build, vendor, and package script for Splunk Jinja2 Formatter app."""

import argparse
import configparser
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_SOURCE_DIR = ROOT_DIR / "jinja_formatter"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"
APP_CONF_FILE = APP_SOURCE_DIR / "default" / "app.conf"
APP_DIST_DIR = ROOT_DIR / "dist"
OUTPUT_DIR = ROOT_DIR / "app"


def get_app_version() -> str:
    """Extract version from app.conf."""
    config = configparser.ConfigParser()
    config.read(APP_CONF_FILE)
    try:
        return config.get("id", "version")
    except Exception:
        try:
            return config.get("launcher", "version")
        except Exception:
            return "1.0.0"


def find_installer():
    """Find uv or pip command."""
    if shutil.which("uv"):
        return ["uv", "pip", "install", "--link-mode=copy"]
    if shutil.which("pip"):
        return ["pip", "install", "--no-compile"]
    raise RuntimeError("Neither 'uv' nor 'pip' executable found.")


def sanitize_lib_directory(lib_dir: Path):
    """Remove metadata, compilation artifacts, and non-pure files that trigger AppInspect warnings."""
    print(f"Sanitizing library directory: {lib_dir}")

    # Remove unwanted top-level entries
    for item in lib_dir.iterdir():
        if item.name.endswith((".dist-info", ".egg-info", ".lock")) or item.name == "__pycache__":
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    # Clean subdirectories recursively
    for root, dirs, files in os.walk(lib_dir, topdown=True):
        # Remove __pycache__ and test dirs
        for d in list(dirs):
            if d in ("__pycache__", "tests", "test"):
                shutil.rmtree(Path(root) / d)
                dirs.remove(d)

        for f in files:
            p = Path(root) / f
            # Remove C sources, compiled binaries, bytecode, and documentation files in lib
            if f.endswith((".c", ".h", ".so", ".dylib", ".pyd", ".pyc", ".pyo")):
                p.unlink()

    # Normalize file and folder permissions (644 for files, 755 for dirs)
    for root, dirs, files in os.walk(lib_dir):
        os.chmod(root, 0o755)
        for f in files:
            os.chmod(Path(root) / f, 0o644)


def vendor_dependencies(target_lib_dir: Path):
    """Install dependencies into target_lib_dir and sanitize them."""
    if not REQUIREMENTS_FILE.is_file():
        raise FileNotFoundError(f"Missing {REQUIREMENTS_FILE}")

    target_lib_dir.mkdir(parents=True, exist_ok=True)

    cmd = find_installer() + ["--target", str(target_lib_dir), "-r", str(REQUIREMENTS_FILE)]
    print(f"Installing dependencies via: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    sanitize_lib_directory(target_lib_dir)
    print("Dependencies vendored and sanitized successfully.")


def clean():
    """Clean all build and temporary artifacts."""
    print("Cleaning build directories and vendor libs...")
    for path in [APP_SOURCE_DIR / "lib", APP_DIST_DIR, ROOT_DIR / "lib"]:
        if path.exists():
            shutil.rmtree(path)
            print(f"Removed {path}")

    # Remove temporary files
    for root, dirs, files in os.walk(ROOT_DIR):
        for d in list(dirs):
            if d in ("__pycache__", ".pytest_cache"):
                shutil.rmtree(Path(root) / d)
                dirs.remove(d)
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                Path(root, f).unlink()


def package():
    """Build a clean, AppInspect-ready Splunk app tarball."""
    version = get_app_version()
    print(f"Packaging jinja_formatter version {version}...")

    clean_staging_dir = APP_DIST_DIR / "jinja_formatter"
    if APP_DIST_DIR.exists():
        shutil.rmtree(APP_DIST_DIR)

    clean_staging_dir.mkdir(parents=True)

    ignore_patterns = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store")

    # Copy app contents
    shutil.copytree(APP_SOURCE_DIR / "bin", clean_staging_dir / "bin", ignore=ignore_patterns)
    shutil.copytree(APP_SOURCE_DIR / "default", clean_staging_dir / "default", ignore=ignore_patterns)

    if (APP_SOURCE_DIR / "metadata").is_dir():
        shutil.copytree(APP_SOURCE_DIR / "metadata", clean_staging_dir / "metadata", ignore=ignore_patterns)

    if (APP_SOURCE_DIR / "README.md").is_file():
        shutil.copy2(APP_SOURCE_DIR / "README.md", clean_staging_dir / "README.md")
    if (APP_SOURCE_DIR / "app.manifest").is_file():
        shutil.copy2(APP_SOURCE_DIR / "app.manifest", clean_staging_dir / "app.manifest")

    # Vendor dependencies into staging
    vendor_dependencies(clean_staging_dir / "lib")

    # Set proper permissions across all files and directories in staging
    for root, dirs, files in os.walk(clean_staging_dir):
        os.chmod(root, 0o755)
        for f in files:
            p = Path(root) / f
            os.chmod(p, 0o644)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tarball_path = OUTPUT_DIR / f"jinja_formatter-{version}.tar.gz"

    print(f"Creating archive at {tarball_path}...")
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(clean_staging_dir, arcname="jinja_formatter")

    print(f"Successfully created: {tarball_path} ({tarball_path.stat().st_size} bytes)")
    return tarball_path


def inspect(tarball: Path = None):
    """Run splunk-appinspect against the latest package."""
    if tarball is None:
        version = get_app_version()
        tarball = OUTPUT_DIR / f"jinja_formatter-{version}.tar.gz"

    if not tarball.is_file():
        tarball = package()

    # Check for pre-installed splunk-appinspect
    appinspect_cmd = shutil.which("splunk-appinspect")
    if not appinspect_cmd:
        local_bin = Path.home() / ".local" / "bin" / "splunk-appinspect"
        if local_bin.is_file():
            appinspect_cmd = str(local_bin)

    if appinspect_cmd:
        cmd = [appinspect_cmd, "inspect", str(tarball), "--mode=precert"]
    elif shutil.which("uv"):
        # Ephemeral execution with zero prior installation via uv
        cmd = ["uv", "tool", "run", "--python", "3.11", "splunk-appinspect", "inspect", str(tarball), "--mode=precert"]
    else:
        print("Neither splunk-appinspect nor uv was found. Install uv (https://astral.sh/uv) or splunk-appinspect.")
        sys.exit(1)

    print(f"Running AppInspect: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        sys.exit(res.returncode)


def main():
    parser = argparse.ArgumentParser(description="Splunk app build and dependency manager")
    parser.add_argument("--vendor", action="store_true", help="Vendor dependencies into jinja_formatter/lib")
    parser.add_argument("--package", action="store_true", help="Package app into app/*.tar.gz")
    parser.add_argument("--clean", action="store_true", help="Clean build directories and vendor lib")
    parser.add_argument("--inspect", action="store_true", help="Run splunk-appinspect on package")

    args = parser.parse_args()

    if args.clean:
        clean()
    elif args.vendor:
        vendor_dependencies(APP_SOURCE_DIR / "lib")
    elif args.package:
        package()
    elif args.inspect:
        inspect()
    else:
        # Default: package
        package()


if __name__ == "__main__":
    main()
