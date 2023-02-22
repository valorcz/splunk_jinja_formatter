# Development Notes

## Virtual Environment

This command prepares a few tools we'll be using in the app validation process:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install https://download.splunk.com/misc/packaging-toolkit/splunk-packaging-toolkit-1.0.1.tar.gz
pip install splunk-appinspect
```

## Verify

```bash
splunk-appinspect inspect jinja_formatter
```

## Package

```bash
slim package jinja_formatter -o app
```

