import os
import sys
import base64
import time
import json
import functools
import itertools
import collections.abc

# Ensure vendor dependencies bundled with the app can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import yaml
import jinja2
import jinja2.sandbox

from splunklib.searchcommands import (
    dispatch,
    StreamingCommand,
    Configuration,
    Option,
    validators,
)


# Custom Jinja Filters


def filter_strftime(unix_timestamp: object, format_string: str = "%Y-%m-%dT%H:%M:%S%z") -> str:
    """Convert a Unix timestamp to a human-readable formatted string."""
    if unix_timestamp is None or unix_timestamp == "":
        return ""
    try:
        timestamp = time.gmtime(float(unix_timestamp))
        return time.strftime(format_string, timestamp)
    except (ValueError, TypeError, OverflowError, OSError):
        return str(unix_timestamp)


def filter_fromjson(value: object):
    """Parse a JSON string into a Python object/structure."""
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def filter_tolist(value: object):
    """Convert value to a list, especially useful for Splunk multivalue fields."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str):
        return [value]
    if isinstance(value, collections.abc.Iterable):
        return list(value)
    return [value]


def filter_toyaml(value: object) -> str:
    """Safely serialize an object to a YAML formatted string."""
    try:
        return yaml.safe_dump(value, default_flow_style=False)
    except Exception:
        return str(value)


def filter_b64encode(value: object) -> str:
    """Base64 encode a string or bytes value to UTF-8."""
    if value is None:
        return ""
    try:
        if isinstance(value, bytes):
            raw = value
        else:
            raw = str(value).encode("utf-8")
        return base64.b64encode(raw).decode("utf-8")
    except Exception:
        return ""


def filter_b64decode(value: object) -> str:
    """Base64 decode a string value to UTF-8."""
    if value is None:
        return ""
    try:
        raw = str(value).strip()
        return base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return ""


def filter_avg(value: object) -> float:
    """Calculate the average of a list or iterable of numbers."""
    try:
        items = [float(x) for x in value] if isinstance(value, collections.abc.Iterable) else [float(value)]
        return sum(items) / len(items) if items else 0.0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


# Environment Setup and Template Caching


def _build_jinja_env() -> jinja2.sandbox.SandboxedEnvironment:
    """Instantiate a secure sandboxed environment with all custom filters and globals."""
    env = jinja2.sandbox.SandboxedEnvironment()

    # Custom filters
    env.filters.update(
        strftime=filter_strftime,
        fromjson=filter_fromjson,
        tolist=filter_tolist,
        toyaml=filter_toyaml,
        b64decode=filter_b64decode,
        b64encode=filter_b64encode,
        avg=filter_avg,
    )

    # Globals
    env.globals.update(
        zip_longest=itertools.zip_longest,
        zip=zip,
        enumerate=enumerate,
    )

    return env


JINJA_ENV = _build_jinja_env()


@functools.lru_cache(maxsize=512)
def get_compiled_template(template_str: str):
    """Cache compiled Jinja templates to prevent expensive re-parsing on every record."""
    return JINJA_ENV.from_string(template_str)


# Custom Splunk Command Implementation


@Configuration()
class Jinja2FormatterCommand(StreamingCommand):
    """
    The jinja2format command renders records using a Jinja2 template.
    It returns events with a field named 'formatted_template' (or a custom field name
    configured via the 'result' option).

    Example:
    ```
    | makeresults count=5
    | eval celsius = random()%100
    | eval name = "Joe"
    | jinja2format "It's {{ celsius }} degrees, {{ name }}!"
    ```
    """

    result = Option(
        doc="""
        **Syntax:** **result=***<fieldname>*
        **Description:** Name of the field that will hold the rendered template (default: 'formatted_template')""",
        require=False,
        validate=validators.Fieldname(),
    )

    on_error = Option(
        doc="""
        **Syntax:** **on_error=***<message|fail|null>*
        **Description:** Behavior when template parsing or rendering fails. (default: 'message')""",
        require=False,
        validate=validators.Set("message", "fail", "null"),
    )

    def __init__(self):
        super(Jinja2FormatterCommand, self).__init__()

    def stream(self, records):
        self.logger.debug("jinja2format started")

        result_field = self.result or "formatted_template"
        error_mode = (self.on_error or "message").lower()

        if not self.fieldnames:
            raise ValueError("jinja2format requires a template string or field name")

        template_arg = self.fieldnames[0]

        for record in records:
            # Check whether template is a field in the record or a literal string
            if template_arg in record:
                val = record[template_arg]
                template_source = "" if val is None else str(val)
            else:
                template_source = template_arg

            try:
                template = get_compiled_template(template_source)
                formatted_value = template.render(record)
            except jinja2.TemplateSyntaxError as e:
                self.logger.warning("Jinja2 syntax error at line %s: %s", e.lineno, e.message)
                if error_mode == "fail":
                    raise
                formatted_value = f"TemplateSyntaxError: {e.message}" if error_mode == "message" else None
            except jinja2.exceptions.SecurityError as e:
                self.logger.warning("Jinja2 security sandbox violation: %s", e)
                if error_mode == "fail":
                    raise
                formatted_value = f"SecurityError: {e}" if error_mode == "message" else None
            except jinja2.TemplateError as e:
                self.logger.warning("Jinja2 template error: %s", e)
                if error_mode == "fail":
                    raise
                formatted_value = f"TemplateError: {e}" if error_mode == "message" else None
            except Exception as e:
                self.logger.warning("Error rendering Jinja2 template: %s", e)
                if error_mode == "fail":
                    raise
                formatted_value = f"RenderError: {e}" if error_mode == "message" else None

            if getattr(self, "_record_writer", None) is not None:
                self.add_field(record, result_field, formatted_value)
            else:
                record[result_field] = formatted_value
            yield record


dispatch(Jinja2FormatterCommand, sys.argv, sys.stdin, sys.stdout, __name__)
