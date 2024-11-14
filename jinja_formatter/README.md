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

## Template Language

Please refer to the [official
documentation](https://jinja.palletsprojects.com/en/latest/templates/) for more
details.

## Issue Reporting

Github
