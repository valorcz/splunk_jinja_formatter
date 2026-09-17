import os
import sys
import base64
import time
import json
import functools
import itertools
import collections.abc
import logging

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

logger = logging.getLogger("splunk.jinja2format")


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


# KV Store Jinja Loader


class SplunkKVStoreLoader(jinja2.BaseLoader):
    """
    Custom Jinja2 loader that retrieves template strings from a Splunk KV Store
    collection ('jinja_templates'). Supports multi-tenant template inheritance
    and deterministic resolution based on the executing Splunk application context:
      - Explicit cross-app borrowing: <target_app>:<template_name>
      - Standard / scoped resolution: calling_app -> global -> TemplateNotFound
    """

    def __init__(self, service=None, app: str = "global"):
        super(SplunkKVStoreLoader, self).__init__()
        self.service = service
        self.app = app or "global"
        self._cache = {}

    def _fetch_template_from_kvstore(self, app: str, name: str):
        """Query the Splunk KV store collection for a template matching app and name."""
        if not self.service:
            return None

        query_json = json.dumps({"app": app, "name": name})
        try:
            response = self.service.get(
                "storage/collections/data/jinja_templates",
                owner="nobody",
                app="jinja_formatter",
                query=query_json,
            )
            body = getattr(response, "body", None)
            if body is None and isinstance(response, dict):
                body = response.get("body")

            if hasattr(body, "read"):
                raw_data = body.read()
            else:
                raw_data = body

            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode("utf-8")

            if isinstance(raw_data, str):
                records = json.loads(raw_data) if raw_data.strip() else []
            elif isinstance(raw_data, list):
                records = raw_data
            else:
                records = []

            if records and isinstance(records, list):
                first_record = records[0]
                if isinstance(first_record, dict):
                    template_content = first_record.get("template")
                    return "" if template_content is None else str(template_content)

            return None
        except Exception as e:
            logger.debug("Failed to fetch template from KV Store (app=%s, name=%s): %s", app, name, e)
            return None

    def get_source(self, environment, template):
        """
        Resolve template source with multi-tenant isolation and inheritance support.
        Returns: (source, template_name, lambda: True)
        """
        if template in self._cache:
            return self._cache[template]

        if ":" in template and not template.startswith(":"):
            # Syntax 1: Explicit Cross-App Borrowing (<target_app>:<template_name>)
            target_app, template_name = template.split(":", 1)
            source = self._fetch_template_from_kvstore(target_app, template_name)
            if source is None:
                raise jinja2.TemplateNotFound(template)
            result = (source, template_name, lambda: True)
            self._cache[template] = result
            return result
        else:
            # Syntax 2: Standard / Scoped Resolution (<template_name>)
            template_name = template
            source = self._fetch_template_from_kvstore(self.app, template_name)
            if source is None and self.app != "global":
                source = self._fetch_template_from_kvstore("global", template_name)

            if source is None:
                raise jinja2.TemplateNotFound(template)

            result = (source, template_name, lambda: True)
            self._cache[template] = result
            return result


# Environment Setup


def build_jinja_env(loader: jinja2.BaseLoader = None) -> jinja2.sandbox.SandboxedEnvironment:
    """Instantiate a secure sandboxed environment with custom filters, globals, and the loader."""
    env = jinja2.sandbox.SandboxedEnvironment(loader=loader)

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


# Global default environment and compiled template cache for standalone/inline usage
JINJA_ENV = build_jinja_env()


@functools.lru_cache(maxsize=512)
def get_compiled_template(template_str: str):
    """Cache compiled Jinja templates to prevent expensive re-parsing on every record."""
    return JINJA_ENV.from_string(template_str)


# Custom Splunk Command Implementation


@Configuration()
class Jinja2FormatterCommand(StreamingCommand):
    """
    The jinja2format command renders records using a Jinja2 template.
    Supports multi-tenant template inheritance backed by a Splunk KV Store collection.

    Example:
    ```
    | makeresults count=5
    | eval celsius = random()%100
    | eval name = "Joe"
    | jinja2format template="child.html"
    ```
    """

    ref = Option(
        doc="""
        **Syntax:** **ref=***<string>*
        **Description:** KV Store template reference (e.g. 'child.html' or 'shared_app:report.html') or event field name""",
        require=False,
    )

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
        self._custom_service = None
        self._custom_search_results_info = None

    @property
    def search_results_info(self):
        """Search results info; permits assignment/mocking for testing."""
        if self._custom_search_results_info is not None:
            return self._custom_search_results_info
        try:
            return super(Jinja2FormatterCommand, self).search_results_info
        except Exception:
            return None

    @search_results_info.setter
    def search_results_info(self, value):
        self._custom_search_results_info = value

    @property
    def service(self):
        """Splunk service instance; permits assignment/mocking for testing."""
        if self._custom_service is not None:
            return self._custom_service
        try:
            return super(Jinja2FormatterCommand, self).service
        except Exception:
            return None

    @service.setter
    def service(self, value):
        self._custom_service = value

    @property
    def calling_app(self) -> str:
        """Dynamically extract the calling Splunk app context, defaulting to 'global'."""
        try:
            sri = getattr(self, "search_results_info", None)
            if sri is not None:
                app = getattr(sri, "app", None)
                if app and str(app).strip():
                    return str(app).strip()
        except Exception:
            pass
        return "global"

    def stream(self, records):
        self.logger.debug("jinja2format started")

        if self.ref and self.fieldnames:
            raise ValueError(
                "jinja2format: Conflicting arguments specified. "
                "Specify either 'ref' or a positional template argument, not both."
            )

        result_field = self.result or "formatted_template"
        error_mode = (self.on_error or "message").lower()

        calling_app = self.calling_app
        loader = SplunkKVStoreLoader(service=self.service, app=calling_app)
        env = build_jinja_env(loader=loader)

        inline_cache = {}

        is_explicit_ref = bool(self.ref)
        template_param = self.ref or (self.fieldnames[0] if self.fieldnames else None)

        for record in records:
            if template_param is not None:
                if template_param in record:
                    val = record[template_param]
                    template_source = "" if val is None else str(val)
                else:
                    template_source = template_param
            elif "template" in record:
                val = record["template"]
                template_source = "" if val is None else str(val)
            else:
                raise ValueError("jinja2format requires a template string, ref, or field name")

            try:
                if template_source == "":
                    formatted_value = ""
                elif is_explicit_ref:
                    # Option ref=<string>: strictly load from KV Store
                    tpl_name = template_source[1:] if template_source.startswith("@") else template_source
                    template_obj = env.get_template(tpl_name)
                    formatted_value = template_obj.render(record)
                elif template_source.startswith("@"):
                    # '@' prefix convention: strictly load from KV Store
                    tpl_name = template_source[1:]
                    template_obj = env.get_template(tpl_name)
                    formatted_value = template_obj.render(record)
                elif any(delim in template_source for delim in ("{{", "{%", "{#")) or "\n" in template_source:
                    # Inline Jinja syntax detected
                    template_obj = inline_cache.get(template_source)
                    if template_obj is None:
                        template_obj = env.from_string(template_source)
                        inline_cache[template_source] = template_obj
                    formatted_value = template_obj.render(record)
                else:
                    # Legacy positional string without '@' and without tags: treat as literal inline string
                    template_obj = inline_cache.get(template_source)
                    if template_obj is None:
                        template_obj = env.from_string(template_source)
                        inline_cache[template_source] = template_obj
                    formatted_value = template_obj.render(record)
            except jinja2.TemplateNotFound as e:
                self.logger.warning("Jinja2 template not found: %s", e)
                if error_mode == "fail":
                    raise
                formatted_value = f"TemplateNotFound: {e.name or template_source}" if error_mode == "message" else None
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
