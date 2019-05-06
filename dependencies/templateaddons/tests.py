from django.template import Template, Context
from django.test import TestCase
from django.utils.html import strip_spaces_between_tags


class TemplateTagTestCase(TestCase):
    """
    Base class to test template tags.
    """
    def validate_template_code_result(self, fixtures):
        """
        Validates that the template code in given fixtures match the 
        corresponding expected output.
        
        The given 'fixtures' argument is an iterable of 2-items lists matching 
        the following scheme::
          
          (
            (template_code_1, expected_output_1),
            (template_code_2, expected_output_2),
            ...
          )
        """
        for (template_code, valid_output) in fixtures:
            t = Template(template_code)
            c = Context()
            output = t.render(c)
            self.assertEquals(output, valid_output)


class AssignTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% assign %} template tag"""
    def test_output(self):
        # set up fixtures
        fixtures = [
            (u'{% assign %}1234{% endassign %}', u''), # silent capture
            (u'{% assign %}1234{% endassign %}5678{{ assign }}', u'56781234'), # default name is "assign"
            (u'{% assign name="sample" %}1234{% endassign %}5678{{ sample }}', u'56781234'), # "name" parameter
            (u'{% assign name="sample" %}1234{% endassign %}{% assign name="sample" %}5678{% endassign %}{{ sample }}', u'5678'), # context override
            (u'{% assign silent=1 %}1234{% endassign %}', u''), # silent capture
            (u'{% assign silent=0 %}1234{% endassign %}', u'1234'), # non silent capture
            ]
        # add template tag library to template code
        fixtures = [(u'{% load assign %}' + template_code, valid_output) for (template_code, valid_output) in fixtures]            
        # test real output
        self.validate_template_code_result(fixtures)


class CounterTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% counter %} template tag"""
    def test_output(self):
        # set up fixtures
        fixtures = [
            (u'{% counter %}', u'0'), # default call
            (u'{% counter %}{% counter %}', u'01'), # default call, 2 calls
            (u'{% counter %}{% counter %}{% counter %}', u'012'), # default call, 3 calls
            (u'{% counter %}{% counter name="c2" %}{% counter %}{% counter %}', u'0012'), # name parameter
            (u'{% counter name="c2" %}{% counter %}{% counter name="c2" %}{% counter name="c2" %}', u'0012'), # name parameter
            (u'{% counter name="c1" %}{% counter name="c2" %}{% counter name="c1" %}{% counter name="c1" %}{% counter name="c2" %}', u'00121'), # name parameter
            (u'{% counter %}{% counter name="default" %}', u'01'), # default name is "default"
            (u'{% counter start=1 %}{% counter %}', u'12'), # start parameter
            (u'{% counter step=4 %}{% counter %}{% counter %}', u'048'), # step parameter
            (u'{% counter step=-4 %}{% counter %}{% counter %}', u'0-4-8'), # negative step parameter
            (u'{% counter ascending=1 %}{% counter %}{% counter %}', u'012'), # ascending parameter
            (u'{% counter ascending=0 %}{% counter %}{% counter %}', u'0-1-2'), # ascending parameter
            (u'{% counter ascending=0 step=-1 %}{% counter %}{% counter %}', u'012'), # ascending parameter and negative step
            (u'{% counter silent=1 %}{% counter %}{% counter %}', u'12'), # silent parameter
            (u'{% counter %}{% counter silent=1 %}{% counter %}', u'02'), # silent parameter
            (u'{% counter silent=1 %}{% counter silent=1 %}{% counter %}', u'2'), # silent parameter
            (u'{% counter assign="c1" %}{{ c1 }}{% counter %}{% counter assign="c1" %}{{ c1 }}{% counter %}{% counter assign="c2" %}{% counter %}{{ c1 }}{{ c2 }}', u'0012234524'), # assign parameter
            (u'{% counter start=4 step=4 ascending=0 %}{% counter start=8 step=23 ascending=1 %}{% counter %}', u'40-4'), # only first declaration affects step and ascending parameters
            ]
        # add template tag library to template code
        fixtures = [(u'{% load counter %}' + template_code, valid_output) for (template_code, valid_output) in fixtures]            
        # test real output
        self.validate_template_code_result(fixtures)


class HeadingContextTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% headingcontext %} template tag"""
    def test_output(self):
        # set up fixtures
        fixtures = [
            (u'{% headingcontext %}<h1>Test</h1>{% endheadingcontext %}', u'<h2>Test</h2>'),
            (u'{% headingcontext %}<H1>Test</H1>{% endheadingcontext %}', u'<h2>Test</h2>'),
            (u'{% headingcontext %}<h1 class="test">Test</h1>{% endheadingcontext %}', u'<h2 class="test">Test</h2>'),
            (u'{% headingcontext %}<h1>Test</h1>{% endheadingcontext %}', u'<h2>Test</h2>'),
            (u'{% headingcontext %}<h2>Test</h2>{% endheadingcontext %}', u'<h3>Test</h3>'),
            (u'{% headingcontext source_level=2 %}<h2>Test</h2>{% endheadingcontext %}', u'<h2>Test</h2>'),
            (u'{% headingcontext source_level=5 %}<h5>Test</h5>{% endheadingcontext %}', u'<h2>Test</h2>'),
            (u'{% headingcontext source_level=2 target_level=4 %}<h2>Test</h2>{% endheadingcontext %}', u'<h4>Test</h4>'),
            (u'{% headingcontext source_level=5 target_level=4 %}<h5>Test</h5>{% endheadingcontext %}', u'<h4>Test</h4>'),
            ]
        # add template tag library to template code
        fixtures = [(u'{% load heading %}' + template_code, valid_output) for (template_code, valid_output) in fixtures]            
        # test real output
        self.validate_template_code_result(fixtures)


class JavascriptTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% counter %} template tag"""
    def test_output(self):
        # set up fixtures
        fixtures = [
            (u'{% javascript_render %}', u''), # empty registry
            (u'{% javascript_assign %}1{% endjavascript_assign %}', u''), # no rendering
            (u'{% javascript_render %}', u'1'), # later rendering works! (not a bug, this is a feature)
            (u'{% javascript_assign %}2{% endjavascript_assign %}', u''), # additional assignment without rendering
            (u'{% javascript_render %}', u'1\n2'), # later rendering still works!
            (u'{% javascript_reset %}{% javascript_render %}', u''), # reset
            (u'{% javascript_reset %}', u''), # clear registry
            (u'{% javascript_render %} - {% javascript_assign %}1{% endjavascript_assign %}', u' - '), # render before assign, does not work
            (u'{% javascript_reset %}', u''), # clear registry
            (u'{% javascript_assign %}1{% endjavascript_assign %} - {% javascript_render %}', u' - 1'), # simple use case
            (u'{% javascript_reset %}', u''), # clear registry
            (u'{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %}2{% endjavascript_assign %} - {% javascript_render %}', u' - 1\n2'), # 2 assignments
            (u'{% javascript_reset %}', u''), # clear registry
            (u'{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %}2{% endjavascript_assign %} - {% javascript_render %}', u' - 1\n2'), # strict duplicates are ignored
            (u'{% javascript_reset %}', u''), # clear registry
            (u'{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %}2{% endjavascript_assign %}{% javascript_assign %}1{% endjavascript_assign %} - {% javascript_render %}', u' - 1\n2'), # strict duplicates are ignored, whatever the order
            (u'{% javascript_reset %}', u''), # clear registry
            (u'{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %} 1{% endjavascript_assign %}{% javascript_assign %}2{% endjavascript_assign %} - {% javascript_render %}', u' - 1\n 1\n2'), # non strict duplicates are not ignored
            (u'{% javascript_reset %}', u''), # clear registry
            (u'{% spaceless %}{% include "tests/templateaddons/javascript/home.html" %}{% endspaceless %}', strip_spaces_between_tags(u"""<html>    
<head>
</head>
<body>
  <div id="menu">
    <ul>
      <li><a href="/">Home</a></li>
      <!-- the menu... -->
    </ul>
  </div>
  <div id="content">
    <p>This is the content</p>
  </div>
  <!--  JAVASCRIPT CODE -->
<script type="text/javascript" src="/first_lib.js" />
<script type="text/javascript">
    /* some javascript code that uses "first_lib.js" */
    var a = 1;
    /* Notice that the "left aligned" indentation helps avoiding whitespace differences between two code fragments. */
</script>
<script type="text/javascript" src="/second_lib.js" />
<script type="text/javascript">
    /* some javascript code that uses "second_lib.js" */
    var b = 2;
</script>
<script type="text/javascript">
    /* some javascript code that uses both "first_lib.js" and "second_lib.js" */
    var c = 3;
</script>
</body>
</html>""")),
            ]
        # add template tag library to template code
        fixtures = [(u'{% load javascript %}' + template_code, valid_output) for (template_code, valid_output) in fixtures]            
        # test real output
        self.validate_template_code_result(fixtures)


class ReplaceTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% replace %} template tag"""
    def test_output(self):
        # set up fixtures
        fixtures = [
            (u'{% replace %}{% endreplace %}', u''), # does nothing
            (u'{% replace search="" replacement="" %}{% endreplace %}', u''), # does nothing
            (u'{% replace search="" replacement="" %}toto{% endreplace %}', u'toto'),
            (u'{% replace search="" replacement="aa" %}toto{% endreplace %}', u'toto'),
            (u'{% replace search="t" replacement="m" %}toto{% endreplace %}', u'momo'),
            (u'{% replace search="t" replacement="" %}toto{% endreplace %}', u'oo'),
            (u'{% replace search="to" replacement="ma" %}toto{% endreplace %}', u'mama'),
            (u'{% replace search="toto" replacement="a" %}toto{% endreplace %}', u'a'),
            (u'{% replace search=" " replacement="-" %}t o t o{% endreplace %}', u't-o-t-o'),
            (u'{% replace search="\\n" replacement="" %}t\noto{% endreplace %}', u'toto'), # antislash character works
            (u'{% replace search="[a-z]+" replacement="" %}Toto{% endreplace %}', u'T'), # regular expressions
            (u'{% replace search="^." replacement="A" %}toto{% endreplace %}', u'Aoto'), # regular expressions
            (u'{% replace search="to$" replacement="Z" %}toto{% endreplace %}', u'toZ'), # regular expressions
            (u'{% replace search="\s+" replacement="-" %}to\t \n\n   \tto{% endreplace %}', u'to-to'), # regular expressions
            (u'{% replace search="(to)" replacement="\\1a" %}toto{% endreplace %}', u'toatoa'), # backreferences in regular expressions
            (u'{% replace search="([a-z]+)" replacement="*\\1*" %}123abc456def{% endreplace %}', u'123*abc*456*def*'), # backreferences in regular expressions
            (u'{% replace search="(to)" replacement="au" %}(to)to{% endreplace %}', u'(au)au'), # regexp not escaped
            (u'{% replace search="(to)" replacement="au" use_regexp=0 %}(to)to{% endreplace %}', u'auto'), # escaped regexp
            (u'{% filter escape_regexp %}(to){% endfilter %}', u'\(to\)'), # escaped regexp
            ]
        # add template tag library to template code
        fixtures = [(u'{% load replace %}' + template_code, valid_output) for (template_code, valid_output) in fixtures]            
        # test real output
        self.validate_template_code_result(fixtures)
