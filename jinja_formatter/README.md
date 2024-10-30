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

```text
  | makeresults count=1 
  | eval celsius = random()%100 
  | eval name = "Joe" 
  | jinja2format "It's {{ celsius }} degrees, {{ name }}!"
```

In this example, we override the output field, and use
a Splunk variable to hold the template.

This is generally better if the template can be complex, and/or
contains characters that could break passing the value to
the `jinja2format` Splunk app -- mostly quotes, perhaps
something else too, but I am not really sure what exactly.

```text
  | makeresults count=1
  | eval celsius = random()%100 
  | eval name = "Joe" 
  | eval template="It's {{ celsius }} degrees, {{ name }}!"
  | jinja2format result=out template
```

## Custom Filters and Jinja Functions

Over time, we realized we need more functions to be able to efficiently
implement our templates.

In order to do so, we've added the following custom filters & functions.

### Custom Filters

- `toyaml(value: object)`
- `fromjson(value: str)`
- `tolist`
- `strftime(unix_timestamp: str, format_string: str = "%Y-%m-%dT%H:%M:%S%z")`

```text
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

Github
