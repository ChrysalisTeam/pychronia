from django import template


register = template.Library()


class JavascriptContainer(object):
    """
    Content storage. Stores fragments of code in a list (self.nodes).
    Provides a method to render code fragments as an unicode. 
    """
    def __init__(self):
        self.nodes = []
        self.separator = u'\n'
        self.unique = True
    
    def __unicode__(self):
        """
        Joins self.nodes with self.separator.
        If self.unique is True, then duplicate code fragments are ignored.
        """
        if self.unique:
            self.remove_duplicates()
        return u'%s' % self.separator.join(self.nodes)
    
    def remove_duplicates(self):
        """
        Removes duplicate code fragments from self.nodes. Updates self.nodes
        and returns None.
        """
        seen = set()
        self.nodes = [x for x in self.nodes if x not in seen and not seen.add(x)]
    
    def append(self, content):
        """
        Appends a code fragment to the internal node list.
        """
        self.nodes.append(content)


# global registry which is used across templates
javascript_container = JavascriptContainer()


class JavascriptRenderNode(template.Node):
    def render(self, context):
        return u'%s' % javascript_container


@register.tag
def javascript_render(parser, token):
    """
    Renders the Javascript code.
    """
    return JavascriptRenderNode()


class JavascriptAssignNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist
    
    def render(self, context):
        content = self.nodelist.render(context)
        javascript_container.append(content)
        return u''


@register.tag
def javascript_assign(parser, token):
    """
    Adds some Javascript code to the registry. Requires a
    {% endjavascript_assign %} closing tag. 
    """
    nodelist = parser.parse(('endjavascript_assign',))
    parser.delete_first_token()
    return JavascriptAssignNode(nodelist)


@register.simple_tag
def javascript_reset():
    """
    Empties the Javascript registry.
    """
    global javascript_container
    javascript_container = JavascriptContainer()
    return u''
