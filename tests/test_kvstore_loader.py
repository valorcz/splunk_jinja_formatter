import pytest
import sys
import os
import json
import jinja2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "jinja_formatter", "bin")))

from jinja2formatter import SplunkKVStoreLoader, Jinja2FormatterCommand, build_jinja_env


class MockResponse:
    def __init__(self, data):
        self.body = json.dumps(data).encode("utf-8")


class MockSplunkService:
    def __init__(self, templates=None):
        # templates is a list of dicts: [{"app": "...", "name": "...", "template": "..."}]
        self.templates = templates or []
        self.get_calls = []

    def get(self, path, query=None, **kwargs):
        self.get_calls.append({"path": path, "query": query, "kwargs": kwargs})
        query_dict = json.loads(query) if query else {}
        app = query_dict.get("app")
        name = query_dict.get("name")

        matches = [
            t for t in self.templates
            if t.get("app") == app and t.get("name") == name
        ]
        return MockResponse(matches)


class MockSearchResultsInfo:
    def __init__(self, app="global"):
        self.app = app


def test_kvstore_loader_get_source_return_signature():
    service = MockSplunkService([
        {"app": "global", "name": "base.html", "template": "BASE CONTENT"}
    ])
    loader = SplunkKVStoreLoader(service=service, app="global")
    env = build_jinja_env(loader=loader)

    source, template_name, uptodate = loader.get_source(env, "base.html")
    assert source == "BASE CONTENT"
    assert template_name == "base.html"
    assert callable(uptodate)
    assert uptodate() is True


def test_kvstore_loader_scoped_resolution_calling_app():
    service = MockSplunkService([
        {"app": "threat-intel", "name": "alert.html", "template": "TI Alert: {{ title }}"},
        {"app": "global", "name": "alert.html", "template": "Global Alert: {{ title }}"},
    ])
    loader = SplunkKVStoreLoader(service=service, app="threat-intel")
    env = build_jinja_env(loader=loader)

    tpl = env.get_template("alert.html")
    assert tpl.render(title="Phishing") == "TI Alert: Phishing"
    # Should have resolved from threat-intel, not global
    assert len(service.get_calls) == 1
    query = json.loads(service.get_calls[0]["query"])
    assert query == {"app": "threat-intel", "name": "alert.html"}


def test_kvstore_loader_scoped_resolution_global_fallback():
    service = MockSplunkService([
        {"app": "global", "name": "base.html", "template": "Global Base: {{ body }}"},
    ])
    loader = SplunkKVStoreLoader(service=service, app="search")
    env = build_jinja_env(loader=loader)

    tpl = env.get_template("base.html")
    assert tpl.render(body="search data") == "Global Base: search data"
    # Calling app checked first, then fallback to global
    assert len(service.get_calls) == 2
    assert json.loads(service.get_calls[0]["query"]) == {"app": "search", "name": "base.html"}
    assert json.loads(service.get_calls[1]["query"]) == {"app": "global", "name": "base.html"}


def test_kvstore_loader_strict_isolation():
    service = MockSplunkService([
        {"app": "private-app", "name": "secret.html", "template": "TOP SECRET"},
        {"app": "global", "name": "public.html", "template": "PUBLIC"},
    ])
    loader = SplunkKVStoreLoader(service=service, app="threat-intel")
    env = build_jinja_env(loader=loader)

    # Calling app "threat-intel" cannot access "secret.html" from "private-app" without prefix
    with pytest.raises(jinja2.TemplateNotFound):
        env.get_template("secret.html")


def test_kvstore_loader_explicit_cross_app_borrowing():
    service = MockSplunkService([
        {"app": "threat-intel", "name": "header.html", "template": "[TI Header: {{ org }}]"},
        {"app": "global", "name": "header.html", "template": "[Global Header]"},
    ])
    loader = SplunkKVStoreLoader(service=service, app="search")
    env = build_jinja_env(loader=loader)

    tpl = env.get_template("threat-intel:header.html")
    assert tpl.render(org="ACME") == "[TI Header: ACME]"

    # Verified strictly queried threat-intel
    assert len(service.get_calls) == 1
    assert json.loads(service.get_calls[0]["query"]) == {"app": "threat-intel", "name": "header.html"}


def test_kvstore_loader_cross_app_no_fallback_on_miss():
    service = MockSplunkService([
        {"app": "global", "name": "footer.html", "template": "Global Footer"},
        {"app": "search", "name": "footer.html", "template": "Search Footer"},
    ])
    loader = SplunkKVStoreLoader(service=service, app="search")
    env = build_jinja_env(loader=loader)

    # When explicit cross-app template doesn't exist in target_app, must NOT fall back to calling app or global
    with pytest.raises(jinja2.TemplateNotFound):
        env.get_template("other-app:footer.html")

    assert len(service.get_calls) == 1
    assert json.loads(service.get_calls[0]["query"]) == {"app": "other-app", "name": "footer.html"}


def test_kvstore_loader_in_memory_caching():
    service = MockSplunkService([
        {"app": "global", "name": "reusable.html", "template": "Template {{ id }}"},
    ])
    loader = SplunkKVStoreLoader(service=service, app="global")
    env = build_jinja_env(loader=loader)

    # First fetch
    tpl1 = env.get_template("reusable.html")
    tpl1.render(id=1)
    call_count = len(service.get_calls)
    assert call_count == 1

    # Second fetch should hit cache
    tpl2 = env.get_template("reusable.html")
    tpl2.render(id=2)
    assert len(service.get_calls) == call_count


def test_kvstore_loader_template_inheritance():
    service = MockSplunkService([
        {
            "app": "global",
            "name": "base.html",
            "template": "<html><body>{% block content %}{% endblock %}</body></html>",
        },
        {
            "app": "threat-intel",
            "name": "child.html",
            "template": '{% extends "base.html" %}{% block content %}Alert: {{ alert_id }}{% endblock %}',
        },
    ])
    loader = SplunkKVStoreLoader(service=service, app="threat-intel")
    env = build_jinja_env(loader=loader)

    tpl = env.get_template("child.html")
    rendered = tpl.render(alert_id="SEC-101")
    assert rendered == "<html><body>Alert: SEC-101</body></html>"


def test_kvstore_loader_inheritance_with_cross_app_borrowing():
    service = MockSplunkService([
        {
            "app": "enterprise-theme",
            "name": "theme.html",
            "template": "<header>{% include 'enterprise-theme:nav.html' %}</header><main>{% block body %}{% endblock %}</main>",
        },
        {
            "app": "enterprise-theme",
            "name": "nav.html",
            "template": "<nav>HOME</nav>",
        },
        {
            "app": "threat-intel",
            "name": "dashboard.html",
            "template": '{% extends "enterprise-theme:theme.html" %}{% block body %}Dashboard: {{ user }}{% endblock %}',
        },
    ])
    loader = SplunkKVStoreLoader(service=service, app="threat-intel")
    env = build_jinja_env(loader=loader)

    tpl = env.get_template("dashboard.html")
    rendered = tpl.render(user="SecAnalyst")
    assert rendered == "<header><nav>HOME</nav></header><main>Dashboard: SecAnalyst</main>"


def test_command_with_kvstore_template_option():
    cmd = Jinja2FormatterCommand()
    cmd.ref = "child.html"
    cmd.search_results_info = MockSearchResultsInfo(app="threat-intel")
    cmd.service = MockSplunkService([
        {
            "app": "global",
            "name": "base.html",
            "template": "[BASE: {% block body %}{% endblock %}]",
        },
        {
            "app": "threat-intel",
            "name": "child.html",
            "template": '{% extends "base.html" %}{% block body %}User: {{ user }}{% endblock %}',
        },
    ])

    records = [{"user": "Alice"}, {"user": "Bob"}]
    out = list(cmd.stream(records))

    assert len(out) == 2
    assert out[0]["formatted_template"] == "[BASE: User: Alice]"
    assert out[1]["formatted_template"] == "[BASE: User: Bob]"


def test_command_with_cross_app_template_option():
    cmd = Jinja2FormatterCommand()
    cmd.ref = "shared_app:report.html"
    cmd.search_results_info = MockSearchResultsInfo(app="search")
    cmd.service = MockSplunkService([
        {
            "app": "shared_app",
            "name": "report.html",
            "template": "Report: {{ title }} by {{ author }}",
        },
    ])

    records = [{"title": "Monthly Audit", "author": "Security Team"}]
    out = list(cmd.stream(records))

    assert len(out) == 1
    assert out[0]["formatted_template"] == "Report: Monthly Audit by Security Team"


def test_command_with_dynamic_incoming_event_field():
    cmd = Jinja2FormatterCommand()
    cmd.ref = "tpl_field"
    cmd.search_results_info = MockSearchResultsInfo(app="threat-intel")
    cmd.service = MockSplunkService([
        {
            "app": "threat-intel",
            "name": "phish.html",
            "template": "Phish: {{ subject }}",
        },
        {
            "app": "global",
            "name": "malware.html",
            "template": "Malware: {{ hash }}",
        },
    ])

    records = [
        {"tpl_field": "phish.html", "subject": "Urgent update"},
        {"tpl_field": "malware.html", "hash": "d41d8cd98f00b204e9800998ecf8427e"},
    ]
    out = list(cmd.stream(records))

    assert out[0]["formatted_template"] == "Phish: Urgent update"
    assert out[1]["formatted_template"] == "Malware: d41d8cd98f00b204e9800998ecf8427e"


def test_command_template_not_found_error_modes():
    service = MockSplunkService([])

    # 1. on_error='message' (default)
    cmd1 = Jinja2FormatterCommand()
    cmd1.ref = "missing.html"
    cmd1.on_error = "message"
    cmd1.service = service
    out1 = list(cmd1.stream([{"foo": "bar"}]))
    assert "TemplateNotFound: missing.html" in out1[0]["formatted_template"]

    # 2. on_error='null'
    cmd2 = Jinja2FormatterCommand()
    cmd2.ref = "missing.html"
    cmd2.on_error = "null"
    cmd2.service = service
    out2 = list(cmd2.stream([{"foo": "bar"}]))
    assert out2[0]["formatted_template"] is None

    # 3. on_error='fail'
    cmd3 = Jinja2FormatterCommand()
    cmd3.ref = "missing.html"
    cmd3.on_error = "fail"
    cmd3.service = service
    with pytest.raises(jinja2.TemplateNotFound):
        list(cmd3.stream([{"foo": "bar"}]))


def test_command_default_calling_app_standalone():
    # Without search_results_info, defaults to 'global'
    cmd = Jinja2FormatterCommand()
    assert cmd.calling_app == "global"

    cmd.ref = "global_only.html"
    cmd.service = MockSplunkService([
        {"app": "global", "name": "global_only.html", "template": "From Global: {{ status }}"}
    ])
    out = list(cmd.stream([{"status": "OK"}]))
    assert out[0]["formatted_template"] == "From Global: OK"


def test_command_conflicting_ref_and_positional_arguments():
    cmd = Jinja2FormatterCommand()
    cmd.ref = "alert.html"
    cmd.fieldnames = ["Hello {{ name }}"]
    with pytest.raises(ValueError, match="Conflicting arguments specified"):
        list(cmd.stream([{"name": "test"}]))


def test_command_with_ref_option():
    cmd = Jinja2FormatterCommand()
    cmd.ref = "alert.html"
    cmd.search_results_info = MockSearchResultsInfo(app="threat-intel")
    cmd.service = MockSplunkService([
        {"app": "threat-intel", "name": "alert.html", "template": "TI Alert: {{ ip }}"}
    ])
    out = list(cmd.stream([{"ip": "1.2.3.4"}]))
    assert out[0]["formatted_template"] == "TI Alert: 1.2.3.4"


def test_command_with_ref_option_strips_at():
    cmd = Jinja2FormatterCommand()
    cmd.ref = "@threat-intel:alert.html"
    cmd.service = MockSplunkService([
        {"app": "threat-intel", "name": "alert.html", "template": "Cross-App: {{ ip }}"}
    ])
    out = list(cmd.stream([{"ip": "5.6.7.8"}]))
    assert out[0]["formatted_template"] == "Cross-App: 5.6.7.8"


def test_command_with_ref_from_event_field():
    cmd = Jinja2FormatterCommand()
    cmd.ref = "tpl_ref_field"
    cmd.search_results_info = MockSearchResultsInfo(app="search")
    cmd.service = MockSplunkService([
        {"app": "global", "name": "report.html", "template": "Report: {{ title }}"}
    ])
    records = [{"tpl_ref_field": "report.html", "title": "Weekly"}]
    out = list(cmd.stream(records))
    assert out[0]["formatted_template"] == "Report: Weekly"


def test_command_with_positional_at_prefix():
    cmd = Jinja2FormatterCommand()
    cmd.fieldnames = ["@child.html"]
    cmd.search_results_info = MockSearchResultsInfo(app="threat-intel")
    cmd.service = MockSplunkService([
        {"app": "global", "name": "base.html", "template": "BASE: {% block body %}{% endblock %}"},
        {"app": "threat-intel", "name": "child.html", "template": '{% extends "base.html" %}{% block body %}Hello {{ user }}{% endblock %}'},
    ])
    out = list(cmd.stream([{"user": "Admin"}]))
    assert out[0]["formatted_template"] == "BASE: Hello Admin"


def test_command_with_positional_at_prefix_cross_app():
    cmd = Jinja2FormatterCommand()
    cmd.fieldnames = ["@shared_app:header.html"]
    cmd.search_results_info = MockSearchResultsInfo(app="search")
    cmd.service = MockSplunkService([
        {"app": "shared_app", "name": "header.html", "template": "HEADER {{ app }}"}
    ])
    out = list(cmd.stream([{"app": "Test"}]))
    assert out[0]["formatted_template"] == "HEADER Test"


def test_command_with_field_value_having_at_prefix():
    cmd = Jinja2FormatterCommand()
    cmd.fieldnames = ["tpl_field"]
    cmd.service = MockSplunkService([
        {"app": "global", "name": "dyn.html", "template": "Dynamic: {{ data }}"}
    ])
    records = [{"tpl_field": "@dyn.html", "data": "payload"}]
    out = list(cmd.stream(records))
    assert out[0]["formatted_template"] == "Dynamic: payload"


def test_command_legacy_positional_static_text_no_false_positive():
    # Legacy searches passing static plain text without Jinja delimiters must render as literal text
    cmd = Jinja2FormatterCommand()
    cmd.fieldnames = ["Static constant message without any variables"]
    out = list(cmd.stream([{"any": "val"}]))
    assert out[0]["formatted_template"] == "Static constant message without any variables"
