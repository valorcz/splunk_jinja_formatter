# Jinja2 Splunk Formatting Command

The jinja2format command returns events with a one new field
'formatted_template'. It has one mandatory parameter, **template**, which needs
to hold a valid jinja2 template.

## Example:

 ```
  | makeresults count=5 | eval celsius = random()%100 | eval name = "Joe" | jinja2format template="It's {{ celsius }} degrees, {{ name }}!"
```
