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
        doc='''
        **Syntax:** **result=***<fieldname>*
        **Description:** Name of the field that will hold the rendered template''',
        require=False, validate=validators.Fieldname())

    def __init__(self):
        super(Jinja2FormatterCommand, self).__init__()

    def stream(self, records):
        self.logger.debug('jinja2format started')

        # Check the parameters
        if not self.result:
            self.result = "formatted_record"
        template_name = None
        if self.fieldnames:
            template_name = self.fieldnames[0]
        else:
           raise ValueError("We need to get a parameter with template")
       
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
            template = jinja2.Template(template)
            # Render the stuff
            formatted_record = template.render(record)
            # Set the result field
            record[self.result] = formatted_record
            yield record

dispatch(Jinja2FormatterCommand, sys.argv, sys.stdin, sys.stdout, __name__)
