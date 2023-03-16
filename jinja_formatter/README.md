# Jinja2 Splunk Formatting Command

The `jinja2format` command returns events with a one new field,
`formatted_template`, unless you specify an `result` option.

The command has one mandatory parameter, **template**, which needs
to hold a valid jinja2 template.

## Example

The following example will output the rendered template into
`formatted_template` field:

```text
  | makeresults count=1 
  | eval celsius = random()%100 
  | eval name = "Joe" 
  | jinja2format "It's {{ celsius }} degrees, {{ name }}!"
```

In this example, we override the output field:

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
