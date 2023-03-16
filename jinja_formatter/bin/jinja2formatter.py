import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import jinja2
from splunklib.searchcommands import (
    dispatch,
    StreamingCommand,
    Configuration,
    Option,
    validators,
)


@Configuration()
class Jinja2FormatterCommand(StreamingCommand):
    """
    The jinja2format command returns events with a one new field 'formatted_template'. It has one
    mandatory parameter, **template**, which needs to hold a valid jinja2 template.

    Example:

    ```
    | makeresults count=5 | eval celsius = random()%100 | eval name = "Joe" | jinja2format template="It's {{ celsius }} degrees, {{ name }}!"
    ```
    """

    template = Option(
        doc="""
        **Syntax:** **template=***<jinja2_template>*
        **Description:** Jinja2 template to format the record.
        """,
        require=True
    )

    def __init__(self):
        super(Jinja2FormatterCommand, self).__init__()

    def stream(self, records):
        # To connect with Splunk, use the instantiated service object which is created using the server-uri and
        # other meta details and can be accessed as shown below
        # Example:-
        #    service = self.service
        #    info = service.info //access the Splunk Server info
        for record in records:
            template = jinja2.Template(self.template)
            formatted_record = template.render(record)
            record["formatted_template"] = formatted_record
            yield record


dispatch(Jinja2FormatterCommand, sys.argv, sys.stdin, sys.stdout, __name__)
