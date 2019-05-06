import re

from django import template
from django.template.defaultfilters import stringfilter

from templateaddons.utils import decode_tag_arguments, parse_tag_argument


register = template.Library()


class ReplaceNode(template.Node):
    def __init__(self, source, search=u'', replacement=u'', use_regexp=True):
        self.nodelist = source
        self.search = search
        self.replacement = replacement
        self.use_regexp = use_regexp
    
    def render(self, context):
        search = parse_tag_argument(self.search, context)
        replacement = parse_tag_argument(self.replacement, context)
        use_regexp = parse_tag_argument(self.use_regexp, context)
        
        source = self.nodelist.render(context)
        if not search:
            output = source
        else:
            if not use_regexp:
                search = re.escape(search)
            pattern = re.compile(search, re.DOTALL | re.UNICODE)
            output = re.sub(pattern, replacement, source)
        
        return output


def replace_tag(parser, token):
    default_arguments = {}
    default_arguments['search'] = u''
    default_arguments['replacement'] = u''
    default_arguments['use_regexp'] = True
    arguments = decode_tag_arguments(token, default_arguments)
    
    source = parser.parse(('endreplace',))
    parser.delete_first_token()
    
    return ReplaceNode(source, **arguments)

register.tag('replace', replace_tag)


@register.filter(name='escape_regexp')
@stringfilter
def escape_regexp(value):
    return re.escape(value)
