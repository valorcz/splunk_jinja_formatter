# Splunk Jinja2 Formatter

If you seek the actual documentation for the Splunk custom command, please
read [README.md](jinja_formatter/README.md) in `jinja_formatter` folder.

This part contains some development notes and remarks, which will later on
be put somewhere else.

## Development Notes

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

In order to get ready for Splunk app certification, run the verbose mode:

```bash
splunk-appinspect inspect --mode=precert jinja_formatter
```

## Package

Btw, as of October 2024, `splunk-packaging-toolkit` only works under python3.9 version, not
newer ones. Work with `pyenv` to get python3.9 to the system, otherwise `slim` won't work.
Hopefully they'll update the package before python3.9 reaches its end-of-life (2025-10).

```bash
slim package jinja_formatter -o app
```

## References

* TBD
