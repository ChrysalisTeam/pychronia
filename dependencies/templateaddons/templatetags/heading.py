import re

from django import template
from templateaddons.utils import decode_tag_arguments, parse_tag_argument


register = template.Library()


class HeadingContextNode(template.Node):
    def __init__(self, nodelist, source_level, target_level):
        self.nodelist = nodelist
        self.source_level = source_level
        self.target_level = target_level
    
    def render(self, context):
        source_level = parse_tag_argument(self.source_level, context)
        target_level = parse_tag_argument(self.target_level, context)
        output = self.nodelist.render(context)
        # first of all: move actual levels to 1
        # i.e. if source_level==5 convert h5 to h1
        for heading_level in range(1, 7):
            from_level = heading_level + source_level - 1
            to_level = heading_level
            open_tag = re.compile(r'<h%d([\s>])' % from_level, re.IGNORECASE)
            close_tag = re.compile(r'</h%d([\s>])' % from_level, re.IGNORECASE)
            output = open_tag.sub(r'<h%d\1' % to_level, output)
            output = close_tag.sub(r'</h%d\1' % to_level, output)
        # then move h2 to h(n+1), h1 to h(n)
        for heading_level in reversed(range(1, 7)):
            from_level = heading_level
            to_level = heading_level + target_level - 1
            open_tag = re.compile(r'<h%d([\s>])' % from_level, re.IGNORECASE)
            close_tag = re.compile(r'</h%d([\s>])' % from_level, re.IGNORECASE)
            output = open_tag.sub(r'<h%d\1' % to_level, output)
            output = close_tag.sub(r'</h%d\1' % to_level, output)
        return output


@register.tag
def headingcontext(parser, token):
    default_arguments = {}
    default_arguments['source_level'] = 1
    default_arguments['target_level'] = 2
    arguments = decode_tag_arguments(token, default_arguments)
    
    nodelist = parser.parse(('endheadingcontext',))
    parser.delete_first_token()
    return HeadingContextNode(nodelist, **arguments)
