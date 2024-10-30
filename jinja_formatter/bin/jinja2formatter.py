import os, sys
import base64
import time
import json
import functools
import itertools
import collections.abc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import yaml
import jinja2

from splunklib.searchcommands import (
    dispatch,
    StreamingCommand,
    Configuration,
    Option,
    validators,
)

# Custom Jinja Filters that may be useful


def filter_strftime(unix_timestamp: str, format_string: str = "%Y-%m-%dT%H:%M:%S%z"):
    timestamp = time.gmtime(float(unix_timestamp))
    return time.strftime(format_string, timestamp)


# TODO: Way better error handling needed
def filter_fromjson(value: str):
    result = None
    try:
        result = json.loads(value)
    except ValueError:
        pass

    return result


# Turn (mostly a string) to a list
def filter_tolist(value: object):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    if isinstance(value, collections.abc.Iterable):
        return [x for x in value]
    else:
        return [value]


# Safe serializer to YAML
def filter_toyaml(value: object):
    return yaml.safe_dump(value)


# TODO: Not sure with the utf-8 encoding
def filter_b64encode(value: str):
    return base64.b64encode(bytes(value, "utf-8")).decode("utf-8")


def filter_b64decode(value: str):
    return base64.b64decode(value).decode("utf-8")


# Custom Splunk function implementation


@Configuration()
class Jinja2FormatterCommand(StreamingCommand):
    """
    The jinja2format command returns events with a one new field 'formatted_template'. It has one
    optional parameter, **result**, which can specify where the template gets rendered to.

    Example:

    ```
    | makeresults count=5
    | eval celsius = random()%100
    | eval name = "Joe"
    | jinja2format "It's {{ celsius }} degrees, {{ name }}!"
    ```
    """

    result = Option(
        doc="""
        **Syntax:** **result=***<fieldname>*
        **Description:** Name of the field that will hold the rendered template""",
        require=False,
        validate=validators.Fieldname(),
    )

    def __init__(self):
        super(Jinja2FormatterCommand, self).__init__()

    def stream(self, records):
        self.logger.debug("jinja2format started")

        # Check the parameters
        if not self.result:
            self.result = "formatted_record"

        # Check input parameter (template)
        template_name = None
        if self.fieldnames:
            template_name = self.fieldnames[0]
        else:
            raise ValueError("We need to get a parameter with a template")

        # Implementation note:
        #   in theory, each event can have its own template defined,
        #   so even though we could probably init Template() here,
        #   it could break the unlikely scenario with different templates
        #   per record.

        # Register our custom filters/functions
        env = jinja2.Environment()

        # Register our custom filters
        env.filters.update(strftime=filter_strftime)
        env.filters.update(fromjson=filter_fromjson)
        env.filters.update(tolist=filter_tolist)
        env.filters.update(toyaml=filter_toyaml)
        env.filters.update(b64decode=filter_b64decode)
        env.filters.update(b64encode=filter_b64encode)

        # Register our global functions
        env.globals.update(zip_longest=itertools.zip_longest)
        env.globals.update(zip=zip)
        env.globals.update(enumerate=enumerate)

        # Process the given chunk of records
        for record in records:
            # For each record, check the template
            if template_name not in record:
                # We were either given a string or non-existent fieldname
                template = template_name
            else:
                template = record[template_name]

            # Initialize the template
            # TODO: Check for parsing errors
            template = env.from_string(template)
            # Render the stuff
            formatted_record = template.render(record)
            # Set the result field
            record[self.result] = formatted_record
            yield record


dispatch(Jinja2FormatterCommand, sys.argv, sys.stdin, sys.stdout, __name__)
