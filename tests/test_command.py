import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "jinja_formatter", "bin")))

from jinja2formatter import Jinja2FormatterCommand


def create_command_instance(fieldnames=None, result=None, on_error=None):
    cmd = Jinja2FormatterCommand()
    cmd.fieldnames = fieldnames or []
    cmd.result = result
    cmd.on_error = on_error
    return cmd


def test_command_with_literal_template():
    cmd = create_command_instance(["Hello {{ name }}, you have {{ count }} alerts."])
    records = [
        {"name": "Alice", "count": 5},
        {"name": "Bob", "count": 0},
    ]

    out = list(cmd.stream(records))
    assert len(out) == 2
    assert out[0]["formatted_template"] == "Hello Alice, you have 5 alerts."
    assert out[1]["formatted_template"] == "Hello Bob, you have 0 alerts."


def test_command_with_custom_result_field():
    cmd = create_command_instance(["Temp: {{ temp }}C"], result="custom_output")
    records = [{"temp": 25}]

    out = list(cmd.stream(records))
    assert out[0]["custom_output"] == "Temp: 25C"
    assert "formatted_template" not in out[0]


def test_command_with_template_field():
    cmd = create_command_instance(["my_tpl"])
    records = [
        {"my_tpl": "Value is {{ val }}", "val": 42},
        {"my_tpl": "Alt: {{ val * 2 }}", "val": 10},
    ]

    out = list(cmd.stream(records))
    assert out[0]["formatted_template"] == "Value is 42"
    assert out[1]["formatted_template"] == "Alt: 20"


def test_command_error_handling_message():
    cmd = create_command_instance(["Invalid {{ syntax "], on_error="message")
    records = [{"name": "test"}]

    out = list(cmd.stream(records))
    assert "TemplateSyntaxError" in out[0]["formatted_template"]


def test_command_error_handling_null():
    cmd = create_command_instance(["Invalid {{ syntax "], on_error="null")
    records = [{"name": "test"}]

    out = list(cmd.stream(records))
    assert out[0]["formatted_template"] is None


def test_command_error_handling_fail():
    cmd = create_command_instance(["Invalid {{ syntax "], on_error="fail")
    records = [{"name": "test"}]

    with pytest.raises(Exception):
        list(cmd.stream(records))


def test_command_missing_arguments():
    cmd = create_command_instance([])
    with pytest.raises(ValueError, match="jinja2format requires a template"):
        list(cmd.stream([{"name": "test"}]))


def test_command_sandbox_security():
    # Attempting to access Python object subclasses through MRO
    cmd = create_command_instance(["{{ [].__class__.__base__.__subclasses__() }}"])
    records = [{"name": "test"}]

    out = list(cmd.stream(records))
    # SandboxedEnvironment prevents access to private __*__ attributes
    assert "SecurityError" in out[0]["formatted_template"]


def test_command_undefined_variables():
    cmd = create_command_instance(["Defined: {{ defined_val }}, Missing: {{ missing_val }}"])
    records = [{"defined_val": "yes"}]

    out = list(cmd.stream(records))
    # Default Jinja undefined renders as empty string without crashing
    assert out[0]["formatted_template"] == "Defined: yes, Missing: "


def test_command_empty_records():
    cmd = create_command_instance(["Hello {{ name }}"])
    out = list(cmd.stream([]))
    assert out == []


def test_command_multibyte_unicode():
    cmd = create_command_instance(["Greetings {{ name }}! Status: {{ status }} 🚀"])
    records = [{"name": "田中太郎", "status": "Český řetězec"}]

    out = list(cmd.stream(records))
    assert out[0]["formatted_template"] == "Greetings 田中太郎! Status: Český řetězec 🚀"


def test_command_render_runtime_error_message():
    cmd = create_command_instance(["{{ 1 / 0 }}"], on_error="message")
    records = [{"x": 1}]
    out = list(cmd.stream(records))
    assert "RenderError: division by zero" in out[0]["formatted_template"]


def test_command_render_runtime_error_null():
    cmd = create_command_instance(["{{ 1 / 0 }}"], on_error="null")
    records = [{"x": 1}]
    out = list(cmd.stream(records))
    assert out[0]["formatted_template"] is None


def test_command_render_runtime_error_fail():
    cmd = create_command_instance(["{{ 1 / 0 }}"], on_error="fail")
    records = [{"x": 1}]
    with pytest.raises(ZeroDivisionError):
        list(cmd.stream(records))


def test_command_template_field_with_none_or_empty():
    cmd = create_command_instance(["tpl"])
    records = [
        {"tpl": None, "name": "Alice"},
        {"tpl": "", "name": "Bob"},
    ]
    out = list(cmd.stream(records))
    assert out[0]["formatted_template"] == ""
    assert out[1]["formatted_template"] == ""


def test_command_dict_tojson_no_quotes_needed():
    # Demonstrating creating JSON with single quotes inside Jinja expressions
    cmd = create_command_instance(["{{ {'user': name, 'active': true} | tojson }}"])
    records = [{"name": "Carol"}]
    out = list(cmd.stream(records))
    assert out[0]["formatted_template"] == '{"active": true, "user": "Carol"}'

