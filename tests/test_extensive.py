import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "jinja_formatter", "bin")))

from jinja2formatter import Jinja2FormatterCommand


def test_extensive_template_features():
    """Test extensive Jinja2 formatting features including YAML, JSON, zip, zip_longest, and base64."""
    cmd = Jinja2FormatterCommand()
    cmd.fieldnames = ["template"]
    cmd.result = "out"

    template_content = """
It's {{ celsius }} degrees, {{ name }}! It's year {{ _time | strftime('%Y') }} now.

How about a YAML test?
```yaml
{{ tj | fromjson | toyaml }}
```

How about a JSON test?
```json
{{ tj | fromjson | tojson(2) }}
```

Dealing with occasional multivalues: {{ mvtest | tolist }}

zip test: {{ zip(ip, domain, mv) | list }}
zip_longest test: {{ zip_longest(ip, domain, mv) | list }}

Test of the `zip_longest` in a loop:
{%- for (iip, idomain, imv) in zip_longest(ip, domain, mv, fillvalue='-') %}
  - IP: {{ iip }}; domain: {{ idomain }}, mv: {{ imv }}
{%- endfor %}

Test of the YAML functions:
{{ zip(ip, domain, mv) | list | toyaml }}

Test b64decode:
  - {{ encoded | b64decode }}

Average calculation: {{ [celsius, 50, 75] | avg }}
"""

    record = {
        "celsius": 25,
        "name": "Joe",
        "_time": 1710500000,
        "mvtest": "value1",
        "mv": ["value1", "value2", "value3", "value4", "value5"],
        "ip": ["ip1", "ip2", "ip3"],
        "domain": ["domain1", "domain2", "domain3", "domain4"],
        "encoded": "w5pwbG7EmyDFvmx1xaVvdcSNa8O9IGvFr8WI",
        "tj": '{"dict": { "key1": "1234-5678-90ab", "key2": "abcdef"}}',
        "template": template_content,
    }

    results = list(cmd.stream([record]))
    assert len(results) == 1

    out = results[0]["out"]

    # Basic values & time formatting
    assert "It's 25 degrees, Joe! It's year 2024 now." in out

    # JSON parsing and YAML serialization
    assert "key1: 1234-5678-90ab" in out
    assert "key2: abcdef" in out

    # JSON formatting
    assert '"dict": {' in out

    # tolist filter
    assert "['value1']" in out

    # zip & zip_longest
    assert "('ip1', 'domain1', 'value1')" in out
    assert "(None, 'domain4', 'value4')" in out
    assert "(None, None, 'value5')" in out

    # zip_longest loop with fillvalue '-'
    assert "- IP: ip1; domain: domain1, mv: value1" in out
    assert "- IP: -; domain: domain4, mv: value4" in out
    assert "- IP: -; domain: -, mv: value5" in out

    # Base64 decode of Czech UTF-8 text
    assert "- Úplně žluťoučký kůň" in out

    # Average filter
    assert "Average calculation: 50.0" in out
