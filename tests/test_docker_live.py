import subprocess
import pytest
import shutil


def is_splunk_container_healthy() -> bool:
    """Check if the splunk-jinja2-formatter container is running and healthy."""
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(
            ["docker", "inspect", "--format={{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{end}}", "splunk-jinja2-formatter"],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            return False
        parts = res.stdout.strip().split()
        return len(parts) >= 2 and parts[0].lower() == "true" and parts[1].lower() == "healthy"
    except Exception:
        return False


@pytest.mark.skipif(not is_splunk_container_healthy(), reason="Splunk docker container is not running or not healthy")
def test_live_splunk_basic_search():
    """Run a basic SPL search with jinja2format in the running container."""
    cmd = [
        "docker",
        "exec",
        "-u",
        "splunk",
        "splunk-jinja2-formatter",
        "/opt/splunk/bin/splunk",
        "search",
        '| makeresults count=1 | eval name="World" | jinja2format "Hello, {{ name }}!"',
        "-auth",
        "admin:changed!",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "Hello, World!" in res.stdout


@pytest.mark.skipif(not is_splunk_container_healthy(), reason="Splunk docker container is not running or not healthy")
def test_live_splunk_extensive_search():
    """Run the extensive SPL search test inside the running container."""
    query = """| makeresults count=1 
| eval celsius = 25 
| eval mv = mvappend("value1", "value2", "value3", "value4", "value5")
| eval ip = mvappend("ip1", "ip2", "ip3")
| eval domain = mvappend("domain1", "domain2", "domain3", "domain4")
| eval encoded = "w5pwbG7EmyDFvmx1xaVvdcSNa8O9IGvFr8WI"
| eval mvtest = "value1"
| eval name = "Joe" 
| eval tj = "{\\"dict\\": { \\"key1\\": \\"1234-5678-90ab\\", \\"key2\\": \\"abcdef\\"}}"
| eval template = "
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
" 
| jinja2format result=out template
| table out"""

    cmd = [
        "docker",
        "exec",
        "-u",
        "splunk",
        "splunk-jinja2-formatter",
        "/opt/splunk/bin/splunk",
        "search",
        query,
        "-auth",
        "admin:changed!",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = res.stdout

    assert "It's 25 degrees, Joe!" in out
    assert "key1: 1234-5678-90ab" in out
    assert "['value1']" in out
    assert "- IP: ip1; domain: domain1, mv: value1" in out
    assert "- IP: -; domain: domain4, mv: value4" in out
    assert "- IP: -; domain: -, mv: value5" in out
    assert "Úplně žluťoučký kůň" in out
