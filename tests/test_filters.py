import pytest
import sys
import os

# Add bin to sys.path so we can import filters directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "jinja_formatter", "bin")))

from jinja2formatter import (
    filter_strftime,
    filter_fromjson,
    filter_tolist,
    filter_toyaml,
    filter_b64encode,
    filter_b64decode,
    filter_avg,
    JINJA_ENV,
    get_compiled_template,
)


def test_filter_strftime():
    # 2024-01-01 00:00:00 UTC = 1704067200
    assert filter_strftime(1704067200, "%Y-%m-%d") == "2024-01-01"
    assert filter_strftime("1704067200", "%Y") == "2024"
    # Graceful error handling for invalid/empty inputs
    assert filter_strftime(None) == ""
    assert filter_strftime("") == ""
    assert filter_strftime("not-a-number") == "not-a-number"


def test_filter_fromjson():
    assert filter_fromjson('{"key": "value"}') == {"key": "value"}
    assert filter_fromjson('[1, 2, 3]') == [1, 2, 3]
    assert filter_fromjson({"already": "dict"}) == {"already": "dict"}
    assert filter_fromjson(None) is None
    assert filter_fromjson("") is None
    assert filter_fromjson("invalid json {") is None


def test_filter_tolist():
    assert filter_tolist(["a", "b"]) == ["a", "b"]
    assert filter_tolist(("a", "b")) == ["a", "b"]
    assert filter_tolist("single") == ["single"]
    assert filter_tolist(123) == [123]
    assert filter_tolist(None) == []


def test_filter_toyaml():
    data = {"name": "test", "items": [1, 2]}
    yaml_out = filter_toyaml(data)
    assert "name: test" in yaml_out
    assert "- 1" in yaml_out
    assert filter_toyaml(None) == "null\n...\n"


def test_filter_b64encode():
    assert filter_b64encode("hello") == "aGVsbG8="
    assert filter_b64encode("hello world") == "aGVsbG8gd29ybGQ="
    assert filter_b64encode(None) == ""
    assert filter_b64encode(123) == "MTIz"


def test_filter_b64decode():
    assert filter_b64decode("aGVsbG8=") == "hello"
    assert filter_b64decode("aGVsbG8gd29ybGQ=") == "hello world"
    assert filter_b64decode(None) == ""
    assert filter_b64decode("invalid%%%b64") == ""


def test_filter_avg():
    assert filter_avg([10, 20, 30]) == 20.0
    assert filter_avg(["1", "2", "3"]) == 2.0
    assert filter_avg(5) == 5.0
    assert filter_avg([]) == 0.0
    assert filter_avg(["invalid"]) == 0.0


def test_jinja_env_with_custom_filters():
    template = JINJA_ENV.from_string(
        "{{ b64_val | b64decode }} - {{ nums | avg }} - {{ dt | strftime('%Y') }}"
    )
    rendered = template.render(
        b64_val="U3BsdW5r",
        nums=[10, 20],
        dt=1704067200,
    )
    assert rendered == "Splunk - 15.0 - 2024"


def test_jinja_globals():
    template = JINJA_ENV.from_string(
        "{% for a, b in zip(list1, list2) %}{{ a }}:{{ b }} {% endfor %}"
    )
    rendered = template.render(list1=["x", "y"], list2=[1, 2]).strip()
    assert rendered == "x:1 y:2"


def test_template_caching():
    t1 = get_compiled_template("Hello {{ name }}")
    t2 = get_compiled_template("Hello {{ name }}")
    assert t1 is t2
