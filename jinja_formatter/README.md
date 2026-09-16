# Jinja2 Splunk Formatting Command

## Motivation

In many cases, users need to format human-readable content within Splunk -- whether sending alert emails, rendering text in dashboards, or forwarding events to Jira, Slack, or ticketing webhooks.

Without templating, users must rely on complex combinations of `strcat`, `replace`, and `eval` string concatenations, making search queries cluttered, fragile, and difficult to maintain.

With Jinja2 templating, you can write clean, reusable templates with placeholders, loops, filters, and conditionals that are populated dynamically by query results. That is what `jinja2format` provides.

---

## Syntax & Options

```spl
jinja2format [result=<field-name>] [on_error=<message|fail|null>] <template-string|template-field>
```

| Option | Type | Default | Description |
|:---|:---|:---|:---|
| `result` | string | `formatted_template` | Name of the output field that will hold the rendered template. |
| `on_error` | string | `message` | Error handling behavior on template syntax or render errors: `message` (outputs error string), `fail` (aborts search execution), or `null` (sets result field to null). |
| `<template>` | string | *required* | Either a literal template string (e.g. `"Hello {{ name }}"`) or the name of a field containing the template. |

---

## Examples

### Basic Usage with a Literal Template

The following example outputs the rendered text into the default `formatted_template` field:

```spl
| makeresults count=1 
| eval celsius = random()%100 
| eval name = "Joe" 
| jinja2format "It's {{ celsius }} degrees, {{ name }}!"
```

### Custom Result Field and Field-Based Template

You can store the template in a field and customize the output field name using `result`:

```spl
| makeresults count=1
| eval celsius = random()%100 
| eval name = "Joe" 
| eval template = "It's {{ celsius }} degrees, {{ name }}!"
| jinja2format result=out template
```

### Error Handling

Control what happens if a template contains a syntax or rendering error:

```spl
| makeresults count=1
| eval broken_template = "{{ 10 / 0 }}"
| jinja2format on_error=null broken_template
```

---

## Handling Quotes in Splunk Templates

In Splunk SPL, double-quotes (`"`) are used for string literals in `eval`. When creating templates that contain quotes, consider these best practices:

1. **Store multiline templates in an `eval` field**:
   Defining your template in a dedicated `| eval template="..."` keeps your query organized and separates template definition from the `jinja2format` command.
2. **Use single quotes inside Jinja expressions**:
   Inside Jinja tags (`{{ ... }}` and `{% ... %}`), Jinja accepts single-quotes (`'...'`) for string literals. Because Splunk does not require escaping single quotes within double-quoted SPL strings, this requires zero backslashes:
   ```spl
   | eval template = "{{ _time | strftime('%Y-%m-%d') }} - {{ 'Hello ' ~ name }}"
   | jinja2format template
   ```
3. **Use `tojson` and `toyaml` instead of manual quoting**:
   When generating JSON or YAML, avoid manually escaping quotes like `"{\"key\": \"val\"}"`. Instead, construct a Python dictionary using single quotes in Jinja and pipe it to `tojson`:
   ```spl
   | jinja2format "{{ {'user': name, 'status': status, 'active': true} | tojson }}"
   ```

---

## Custom Filters and Jinja Functions

To simplify template creation in Splunk, `jinja2format` provides several built-in custom filters and global functions.

### Custom Filters

#### `strftime(unix_timestamp: int|str, format_string: str = "%Y-%m-%dT%H:%M:%S%z")`

Converts a Unix epoch timestamp to a formatted date/time string. Defaults to ISO 8601 UTC format.

```jinja
{{ _time | strftime('%Y-%m-%d %H:%M:%S') }}
```

#### `fromjson(value: str)`

Parses a JSON-encoded string into a Python dictionary or list structure. Frequently combined with Jinja's built-in `tojson`:

```jinja
{{ raw_json_field | fromjson | tojson(2) }}
```

#### `toyaml(value: object)`

Safely serializes an object or dictionary to a clean, human-readable YAML string.

```jinja
{{ raw_json_field | fromjson | toyaml }}
```

#### `tolist(value: object)`

Converts the given value to a list. This is especially useful for Splunk fields that may or may not be multivalued: Splunk passes single values as a string and multiple values as a list. With `tolist`, you can safely iterate over the field in Jinja loops regardless of whether it has one or many values:

```jinja
{% for ami in aws_ami_id | tolist %}
  - AMI: {{ ami }}
{% endfor %}
```

#### `b64encode(value: str)`

Base64 encodes a string value to UTF-8.

#### `b64decode(value: str)`

Base64 decodes a string value to UTF-8.

#### `avg(value: list)`

Calculates the numeric average of a list or iterable (e.g. `{{ response_times | avg }}`).

---

### Custom Functions

#### `zip(list1, list2, ...)`

Aggregates elements from multiple iterables into tuples until the shortest iterable is exhausted:

```jinja
{{ zip(ip, domain, mv) | list }}
```

#### `zip_longest(list1, list2, ..., fillvalue=None)`

Aggregates elements from multiple iterables until the longest iterable is exhausted, filling missing values with `fillvalue`:

```jinja
{% for (iip, idomain) in zip_longest(ip, domain, fillvalue='-') %}
  - IP: {{ iip }}, Domain: {{ idomain }}
{% endfor %}
```

#### `enumerate(iterable, start=0)`

Returns an iterator yielding pairs of `(index, item)` starting from `start` (default 0):

```jinja
{% for idx, host in enumerate(servers, start=1) %}
  {{ idx }}. {{ host }}
{% endfor %}
```

---

## Complex Example

The following search illustrates the features and custom filters available in `jinja2format`:

```spl
| makeresults count=1 
| eval celsius = random()%100 
| eval mvtest = mvappend("value1", "value2")
| eval mv = mvappend("value1", "value2", "value3", "value4", "value5")
| eval ip = mvappend("ip1", "ip2", "ip3")
| eval domain = mvappend("domain1", "domain2", "domain3", "domain4")
| eval encoded = "w5pwbG7EmyDFvmx1xaVvdcSNa8O9IGvFr8WI"
| eval name = "Joe" 
| eval tj = "{\"dict\": { \"key1\": \"1234-5678-90ab\", \"key2\": \"abcdef\"}}"

| eval template="
It's {{ celsius }} degrees, {{ name }}! Year: {{ _time | strftime('%Y') }}

YAML formatting:
```yaml
{{ tj | fromjson | toyaml }}
```

JSON formatting:
```json
{{ tj | fromjson | tojson(2) }}
```

Dealing with occasional multivalues: {{ mvtest | tolist }}

zip test: {{ zip(ip, domain, mv) | list }}
zip_longest test: {{ zip_longest(ip, domain, mv) | list }}

Loop with zip_longest:
{%- for (iip, idomain, imv) in zip_longest(ip, domain, mv, fillvalue='-') %}
  - IP: {{ iip }}; domain: {{ idomain }}, mv: {{ imv }}
{%- endfor %}

Enumerate loop:
{%- for idx, val in enumerate(ip, start=1) %}
  {{ idx }}. {{ val }}
{%- endfor %}

Base64 decode:
  - {{ encoded | b64decode }}

Average calculation:
  - {{ [celsius, 50, 75] | avg }}
"
| jinja2format result=out on_error=message template
```

---

## Template Language

For standard Jinja syntax (control structures, conditions, macros, and built-in filters), refer to the [official Jinja documentation](https://jinja.palletsprojects.com/en/latest/templates/).

## Issue Reporting

Please use the [splunk_jinja_formatter](https://github.com/valorcz/splunk_jinja_formatter) GitHub repository for reporting issues or suggesting features.