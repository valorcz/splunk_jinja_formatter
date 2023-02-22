# Development Notes

## Virtual Environment

```bash
python3 -m venv .venv
pip install https://download.splunk.com/misc/packaging-toolkit/splunk-packaging-toolkit-1.0.1.tar.gz
pip install splunk-appinspect
```

## Verify

```bash
splunk-appinspect inspect jinja_formatter
```

## Package

```bash
slim package jinja_formatter
```

## Errors

```
02-22-2023 15:53:35.824 INFO  ChunkedExternProcessor [16959 searchOrchestrator] - Running process: /opt/splunk/bin/python3.7 /opt/splunk/etc/apps/jinja_formatter/bin/jinja2formatter.py
02-22-2023 15:53:35.846 ERROR ChunkedExternProcessor [16964 ChunkedExternProcessorStderrLogger] - stderr: Traceback (most recent call last):
02-22-2023 15:53:35.846 ERROR ChunkedExternProcessor [16964 ChunkedExternProcessorStderrLogger] - stderr:   File "/opt/splunk/etc/apps/jinja_formatter/bin/jinja2formatter.py", line 5, in <module>
02-22-2023 15:53:35.846 ERROR ChunkedExternProcessor [16964 ChunkedExternProcessorStderrLogger] - stderr:     import jinja2
02-22-2023 15:53:35.846 ERROR ChunkedExternProcessor [16964 ChunkedExternProcessorStderrLogger] - stderr: ModuleNotFoundError: No module named 'jinja2'
02-22-2023 15:53:35.850 ERROR ChunkedExternProcessor [16959 searchOrchestrator] - EOF while attempting to read transport header read_size=0
02-22-2023 15:53:35.852 ERROR ChunkedExternProcessor [16959 searchOrchestrator] - Error in 'jinjaformatter' command: External search command exited unexpectedly with non-zero error code 1.
```

