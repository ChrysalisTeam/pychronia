from django import template

from templateaddons.settings import TEMPLATEADDONS_COUNTERS_VARIABLE
from templateaddons.utils import decode_tag_arguments, parse_tag_argument


register = template.Library()


class Counter:
    def __init__(self, start=0, step=1, ascending=True):
        self.value = start
        self.start = start
        self.step = step
        self.ascending = ascending


class CounterNode(template.Node):
    def __init__(self, name='"default"', start=0, step=1, ascending=True, 
                 silent=False, assign=False):
        self.name = name
        self.start = start
        self.step = step
        self.ascending = ascending
        self.silent = silent
        self.assign = assign
    
    def render(self, context):
        # global context initialization
        if not context.has_key(TEMPLATEADDONS_COUNTERS_VARIABLE):
            context[TEMPLATEADDONS_COUNTERS_VARIABLE] = {}
        counters = context[TEMPLATEADDONS_COUNTERS_VARIABLE]
        
        name = parse_tag_argument(self.name, context)
        silent = parse_tag_argument(self.silent, context)
        assign = parse_tag_argument(self.assign, context)
        
        if not counters.has_key(name):
            start = parse_tag_argument(self.start, context)
            step = parse_tag_argument(self.step, context)
            ascending = parse_tag_argument(self.ascending, context)
            counters[name] = Counter(start, step, ascending)
        else:
            if counters[name].ascending:
                counters[name].value += counters[name].step
            else:
                counters[name].value -= counters[name].step
        
        context[TEMPLATEADDONS_COUNTERS_VARIABLE] = counters
        
        if assign:
            context[assign] = counters[name].value
        
        if self.silent:
            return u''
        else:
            return u'%d' % counters[name].value


def counter(parser, token):
    default_arguments = {}
    default_arguments['name'] = '"default"'
    default_arguments['start'] = 0
    default_arguments['step'] = 1
    default_arguments['ascending'] = True
    default_arguments['silent'] = False
    default_arguments['assign'] = '""'
    
    arguments = decode_tag_arguments(token, default_arguments)
    
    return CounterNode(**arguments)

register.tag('counter', counter)
