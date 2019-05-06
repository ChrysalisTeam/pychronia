from django import template
from templateaddons.utils import decode_tag_arguments, parse_tag_argument


register = template.Library()


class AssignNode(template.Node):
    def __init__(self, nodelist, arguments):
        self.nodelist = nodelist
        self.name = arguments['name']
        self.silent = arguments['silent']
    
    def render(self, context):
        name = parse_tag_argument(self.name, context)
        silent = parse_tag_argument(self.silent, context)
        context[name] = self.nodelist.render(context)
        if silent:
            return u''
        else:
            return context[name]


@register.tag
def assign(parser, token):
    """
    The {% assign %} template tag is useful when you want to capture some template
    code output and use the result later.
    
    The following template code::
    
      {% load assign %}
      {% assign name="sample_code" %}1234{% endassign %}
      5678
      {{ sample_code }}
    
    ... gives the following output::
    
      
      
      5678
      1234
    
    """
    default_arguments = {}
    default_arguments['name'] = '"assign"'
    default_arguments['silent'] = '1'
    arguments = decode_tag_arguments(token, default_arguments)
    
    nodelist = parser.parse(('endassign',))
    parser.delete_first_token()
    return AssignNode(nodelist, arguments)
