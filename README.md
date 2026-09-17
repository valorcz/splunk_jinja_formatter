# Splunk Jinja2 Formatter

A Splunk app providing the `jinja2format` custom streaming search command to format events using Jinja2 templates -- supporting inline strings, event-field templates, and **Splunk KV Store-backed templates with multi-tenant inheritance** (`{% extends %}`, `{% block %}`, `{% include %}`).

- **Command User Guide & Examples**: See [jinja_formatter/README.md](jinja_formatter/README.md).
- **Template Inheritance & KV Store Deep Dive**: See [docs/template_inheritance.md](docs/template_inheritance.md).

---

## Architecture & Design

The command is implemented as a Splunk Custom Search Command V2 (`StreamingCommand`) located at [`jinja_formatter/bin/jinja2formatter.py`](jinja_formatter/bin/jinja2formatter.py):

- **Sandboxed Execution**: Templates are executed within a `jinja2.sandbox.SandboxedEnvironment`, preventing unauthorized Python introspection, class hierarchy traversal (`__class__`, `__subclasses__`), or arbitrary code execution.
- **KV Store Loader & Multi-Tenancy**: The `SplunkKVStoreLoader` resolves templates from the `jinja_templates` KV Store collection using scoped lookup hierarchy (`<calling_app>` -> `global` fallback) or explicit cross-app referencing (`<target_app>:<template_name>`).
- **Template AST & Source Caching**: Template sources fetched from the KV Store are cached in memory per search, and compiled Jinja ASTs are cached via `@functools.lru_cache(maxsize=512)`. When streaming thousands of search events, parsing overhead is eliminated.
- **Custom Filters & Globals**:
  - Filters: `strftime`, `fromjson`, `tolist`, `toyaml`, `b64encode`, `b64decode`, `avg`.
  - Globals: `zip`, `zip_longest`, `enumerate`.
- **Fault Tolerance**: The `on_error` option (`message`, `null`, `fail`) allows users to control failure semantics on syntax or runtime rendering errors.

---

## Development & Build Workflow

This project uses [uv](https://github.com/astral-sh/uv) (or standard `pip`) and an automated build script to eliminate manual package downloads and ensure clean AppInspect compliance.

### Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`
- Docker & Docker Compose (for local Splunk testing)

### Quick Start

```bash
# 1. Install dev dependencies & sync environment
make init

# 2. Run test suite
make test

# 3. Build an AppInspect-ready release package
make package
# Generates: app/jinja_formatter-<version>.tar.gz
```

---

## Dependency Management

Dependencies are declared in `pyproject.toml` and pinned in `requirements.txt`.

Third-party dependencies are **never** committed to Git. Instead, they are automated:
- **For local testing/Docker**: `make vendor` (or starting docker with `make up` / `make start`) installs dependencies into `jinja_formatter/lib/`.
- **For packaging**: `make package` installs dependencies into a clean build staging folder, strips all metadata (`*.dist-info`, `RECORD`, `__pycache__`, compiled C files), normalizes file permissions (`644` for files, `755` for directories), and creates the `.tar.gz` archive in `app/`.

---

## Version Management

The app version is tracked synchronously across:
- `jinja_formatter/default/app.conf`
- `jinja_formatter/app.manifest`
- `pyproject.toml`

Use the automated versioning commands to inspect or bump versions:

```bash
# View current version
make version

# Bump version using SemVer rules
make bump-patch   # 1.1.0 -> 1.1.1
make bump-minor   # 1.1.0 -> 1.2.0
make bump-major   # 1.1.0 -> 2.0.0

# Or set an explicit version
make set-version V=1.1.2
```

---

## App Inspection

Run Splunk AppInspect against the packaged app:

```bash
make inspect
```

*Zero-setup*: If `splunk-appinspect` is not installed locally, `make inspect` automatically runs it ephemerally via `uv tool run --python 3.11 splunk-appinspect` with no manual installation needed.

You can also run it directly via CLI at any time:

```bash
uvx --python 3.11 splunk-appinspect inspect app/jinja_formatter-<version>.tar.gz --mode=precert
```

---

## Testing Suite

Tests are located in `tests/` and run with `pytest`:

```bash
make test
```

The test suite covers:
- **`tests/test_command.py`**: Search command options, result fields, dynamic vs literal templates, error handling modes (`message`, `null`, `fail`), and sandbox security.
- **`tests/test_filters.py`**: Unit tests for all custom filters (`strftime`, `fromjson`, `tolist`, `toyaml`, `b64encode`, `b64decode`, `avg`) and global functions.
- **`tests/test_extensive.py`**: End-to-end multi-feature templates combining YAML, JSON, zip loops, and Czech Unicode base64 decoding.
- **`tests/test_docker_live.py`**: Live Splunk search execution against the local Docker instance via Splunk REST API (`/services/search/jobs/export`).
- **`tests/test_version.py`**: SemVer validation and version sync integrity.

---

## Local Development in Docker

Docker testing uses a clean, package-based workflow that decouples the container from the host filesystem. This prevents container processes from changing file ownership or writing `__pycache__` artifacts to your Git workspace:

```bash
# Start Splunk, wait for healthcheck, and automatically deploy the packaged app
make start

# Deploy code updates to the running container without restarting (~2s)
make deploy

# Access Splunk Web
# http://localhost:8000 (admin / changed!)

# Stop Splunk
make down
```

---

## Makefile Reference

| Target | Description |
|:---|:---|
| `make init` | Create virtual environment and install dev dependencies with `uv`. |
| `make test` | Run pytest suite across unit and live Docker integration tests. |
| `make version` | Display current app version across all manifests. |
| `make bump-patch` | Increment patch version (e.g. `1.1.0` -> `1.1.1`). |
| `make bump-minor` | Increment minor version (e.g. `1.1.0` -> `1.2.0`). |
| `make bump-major` | Increment major version (e.g. `1.1.0` -> `2.0.0`). |
| `make set-version V=x.y.z` | Set an explicit version across all manifests. |
| `make vendor` | Vendor dependencies into `jinja_formatter/lib/` for local development. |
| `make package` | Build a clean, sanitized `.tar.gz` distribution package in `app/`. |
| `make inspect` | Build package and run Splunk AppInspect precertification checks. |
| `make clean` | Remove build directories, caches, and vendored libraries. |
| `make up` | Start Splunk container via Docker Compose. |
| `make wait_up` | Wait until Splunk container healthcheck reports ready. |
| `make deploy` | Build package, copy to container, and install via `splunk install app`. |
| `make start` | Start Splunk, wait for readiness, and deploy the packaged app. |
| `make down` | Stop running Splunk container. |
| `make restart` | Restart Splunk container and redeploy app. |
| `make remove` | Remove Splunk container. |
