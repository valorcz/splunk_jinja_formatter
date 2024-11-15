# Jinja2 Splunk Formatting Command

## Motivation

In many cases, people format a user-readable content within
Splunk -- either because they need to send an e-mail, show
a text in a dashboard, or push the results to JIRA or other
ticketing tool.

But when they format the actual readable message, they have
to use a very simple formatting techniques, making the
query look rather ugly and difficult to maintain.

With a template, it's possible to specify the resulting
text with placeholders, which will later on be properly
populated by the query results. And that's exactly
what `jinja2format` does.

## Description

The `jinja2format` command returns events with a one new field,
`formatted_template`, unless you specify the `result` option.

## Example

The following example will output the rendered template into
`formatted_template` field:

```bash
  | makeresults count=1 
  | eval celsius = random()%100 
  | eval name = "Joe" 
  | jinja2format "It's {{ celsius }} degrees, {{ name }}!"
```

In the following example, we override the output field, and use a Splunk
variable to hold the template.

```bash
  | makeresults count=1
  | eval celsius = random()%100 
  | eval name = "Joe" 
  | eval template="It's {{ celsius }} degrees, {{ name }}!"
  | jinja2format result=out template
```

This is generally better if the template is complex, and/or
contains characters that could break passing the value to
the `jinja2format` Splunk app -- mostly quotes, perhaps
something else too, but I am not really sure what exactly.

## Custom Filters and Jinja Functions

Over time, we realized we need more functions to be able to efficiently
implement our templates.

In order to do so, we've added the following custom filters & functions.

### Custom Filters

#### `toyaml(value: object)`

Take the given object and try to render it as YAML structure, with
some default pretty-printing.

#### `fromjson(value: str)`

Take a string and turn it into a JSON object. This can be useful in a combination
with `tojson()` function, which nicely formats the given JSON object.

```bash
{ value | fromjson | tojson(2) }
```

will take the `value` and, if everything is well, it'll format it
to a nice JSON representation.

#### `tolist(value: object)`

Convert the given value to a list. This is probably only useful for multi-value
Splunk fields that may or may not be multivalued. By default, a multi-value field
is passed as a list, but single-value field is a string. With 

#### `strftime(unix_timestamp: str, format_string: str = "%Y-%m-%dT%H:%M:%S%z")`

Convert the given `unix_timestamp` to a human-readable timestamp. By default,
it uses ISO 8601 standard, but you can provide your own `format_string`.

Useful for many Splunk searches, because timestamps are usually in the Epoch
format, not in the human-readable one.

#### `b64decode(value: str)`

Take the given string and apply base64 decoding to it.

#### `b64encode(value: str)`

Take the given string and apply base64 encoding to it.

### Custom Functions

#### `zip(list1, list2, ...)`

Allows you to aggregate elements from multiple iterables/list into a single
list.  It takes two or more lists as input and returns an iterator that
produces tuples containing elements from all the input iterables.

In many cases, you may want to use `list()` filter as the follow-up filter in
order to convert the output to a list.

```bash
zip test: {{ zip(ip, domain, mv) | list }}
```

#### `zip_longest(list1, list2, ..., fillvalue=None)`

This function makes an iterator that aggregates elements from each of the
iterables. The iteration continues until the longest iterable is not exhausted.

It takes two or more lists as input and returns an iterator that
produces tuples containing elements from all the input iterables.

### Complex Example

The following example shows probably all the functionality
implemented in the current release of `jinja2format` command.

```bash
    | makeresults count=1 
    | eval celsius = random()%100 
    | eval mvtest=mvappend("value1", "value2")
    | eval mv = mvappend("value1", "value2", "value3", "value4", "value5")
    | eval ip=mvappend("ip1", "ip2", "ip3")
    | eval domain=mvappend("domain1", "domain2", "domain3", "domain4")
    | eval encoded="w5pwbG7EmyDFvmx1xaVvdcSNa8O9IGvFr8WI"
    | eval mvtest="value1"
    | eval name = "Joe" 
    | eval tj = "{\"dict\": { \"key1\": \"1234-5678-90ab\", \"key2\": \"abcdef\"}}"

    | eval template="
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
```

## Template Language

Please refer to the [official
documentation](https://jinja.palletsprojects.com/en/latest/templates/) for more
details.

## Issue Reporting

Please use [splunk_jinja_formatter](https://github.com/valorcz/splunk_jinja_formatter) 
repository on Github for reporting issues, suggesting features, etc.