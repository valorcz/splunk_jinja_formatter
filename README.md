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

In order to get ready for Splunk app certification, run the verbose mode:

```bash
splunk-appinspect inspect --mode=precert jinja_formatter
```

## Package

```bash
slim package jinja_formatter -o app
```

## References

### Internal

* [Creating Splunk Applications](https://confluence.in.here.com/display/~lorenc/DRAFT%3A+Creating+Splunk+Applications)
