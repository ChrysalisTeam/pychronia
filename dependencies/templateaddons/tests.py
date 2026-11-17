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
        for template_code, valid_output in fixtures:
            t = Template(template_code)
            c = Context()
            output = t.render(c)
            self.assertEqual(output, valid_output)


class AssignTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% assign %} template tag"""

    def test_output(self):
        # set up fixtures
        fixtures = [
            ("{% assign %}1234{% endassign %}", ""),  # silent capture
            ("{% assign %}1234{% endassign %}5678{{ assign }}", "56781234"),  # default name is "assign"
            ('{% assign name="sample" %}1234{% endassign %}5678{{ sample }}', "56781234"),  # "name" parameter
            (
                '{% assign name="sample" %}1234{% endassign %}{% assign name="sample" %}5678{% endassign %}{{ sample }}',
                "5678",
            ),  # context override
            ("{% assign silent=1 %}1234{% endassign %}", ""),  # silent capture
            ("{% assign silent=0 %}1234{% endassign %}", "1234"),  # non silent capture
        ]
        # add template tag library to template code
        fixtures = [("{% load assign %}" + template_code, valid_output) for (template_code, valid_output) in fixtures]
        # test real output
        self.validate_template_code_result(fixtures)


class CounterTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% counter %} template tag"""

    def test_output(self):
        # set up fixtures
        fixtures = [
            ("{% counter %}", "0"),  # default call
            ("{% counter %}{% counter %}", "01"),  # default call, 2 calls
            ("{% counter %}{% counter %}{% counter %}", "012"),  # default call, 3 calls
            ('{% counter %}{% counter name="c2" %}{% counter %}{% counter %}', "0012"),  # name parameter
            (
                '{% counter name="c2" %}{% counter %}{% counter name="c2" %}{% counter name="c2" %}',
                "0012",
            ),  # name parameter
            (
                '{% counter name="c1" %}{% counter name="c2" %}{% counter name="c1" %}{% counter name="c1" %}{% counter name="c2" %}',
                "00121",
            ),  # name parameter
            ('{% counter %}{% counter name="default" %}', "01"),  # default name is "default"
            ("{% counter start=1 %}{% counter %}", "12"),  # start parameter
            ("{% counter step=4 %}{% counter %}{% counter %}", "048"),  # step parameter
            ("{% counter step=-4 %}{% counter %}{% counter %}", "0-4-8"),  # negative step parameter
            ("{% counter ascending=1 %}{% counter %}{% counter %}", "012"),  # ascending parameter
            ("{% counter ascending=0 %}{% counter %}{% counter %}", "0-1-2"),  # ascending parameter
            (
                "{% counter ascending=0 step=-1 %}{% counter %}{% counter %}",
                "012",
            ),  # ascending parameter and negative step
            ("{% counter silent=1 %}{% counter %}{% counter %}", "12"),  # silent parameter
            ("{% counter %}{% counter silent=1 %}{% counter %}", "02"),  # silent parameter
            ("{% counter silent=1 %}{% counter silent=1 %}{% counter %}", "2"),  # silent parameter
            (
                '{% counter assign="c1" %}{{ c1 }}{% counter %}{% counter assign="c1" %}{{ c1 }}{% counter %}{% counter assign="c2" %}{% counter %}{{ c1 }}{{ c2 }}',
                "0012234524",
            ),  # assign parameter
            (
                "{% counter start=4 step=4 ascending=0 %}{% counter start=8 step=23 ascending=1 %}{% counter %}",
                "40-4",
            ),  # only first declaration affects step and ascending parameters
        ]
        # add template tag library to template code
        fixtures = [("{% load counter %}" + template_code, valid_output) for (template_code, valid_output) in fixtures]
        # test real output
        self.validate_template_code_result(fixtures)


class HeadingContextTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% headingcontext %} template tag"""

    def test_output(self):
        # set up fixtures
        fixtures = [
            ("{% headingcontext %}<h1>Test</h1>{% endheadingcontext %}", "<h2>Test</h2>"),
            ("{% headingcontext %}<H1>Test</H1>{% endheadingcontext %}", "<h2>Test</h2>"),
            ('{% headingcontext %}<h1 class="test">Test</h1>{% endheadingcontext %}', '<h2 class="test">Test</h2>'),
            ("{% headingcontext %}<h1>Test</h1>{% endheadingcontext %}", "<h2>Test</h2>"),
            ("{% headingcontext %}<h2>Test</h2>{% endheadingcontext %}", "<h3>Test</h3>"),
            ("{% headingcontext source_level=2 %}<h2>Test</h2>{% endheadingcontext %}", "<h2>Test</h2>"),
            ("{% headingcontext source_level=5 %}<h5>Test</h5>{% endheadingcontext %}", "<h2>Test</h2>"),
            ("{% headingcontext source_level=2 target_level=4 %}<h2>Test</h2>{% endheadingcontext %}", "<h4>Test</h4>"),
            ("{% headingcontext source_level=5 target_level=4 %}<h5>Test</h5>{% endheadingcontext %}", "<h4>Test</h4>"),
        ]
        # add template tag library to template code
        fixtures = [("{% load heading %}" + template_code, valid_output) for (template_code, valid_output) in fixtures]
        # test real output
        self.validate_template_code_result(fixtures)


class JavascriptTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% counter %} template tag"""

    def test_output(self):
        # set up fixtures
        fixtures = [
            ("{% javascript_render %}", ""),  # empty registry
            ("{% javascript_assign %}1{% endjavascript_assign %}", ""),  # no rendering
            ("{% javascript_render %}", "1"),  # later rendering works! (not a bug, this is a feature)
            ("{% javascript_assign %}2{% endjavascript_assign %}", ""),  # additional assignment without rendering
            ("{% javascript_render %}", "1\n2"),  # later rendering still works!
            ("{% javascript_reset %}{% javascript_render %}", ""),  # reset
            ("{% javascript_reset %}", ""),  # clear registry
            (
                "{% javascript_render %} - {% javascript_assign %}1{% endjavascript_assign %}",
                " - ",
            ),  # render before assign, does not work
            ("{% javascript_reset %}", ""),  # clear registry
            ("{% javascript_assign %}1{% endjavascript_assign %} - {% javascript_render %}", " - 1"),  # simple use case
            ("{% javascript_reset %}", ""),  # clear registry
            (
                "{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %}2{% endjavascript_assign %} - {% javascript_render %}",
                " - 1\n2",
            ),  # 2 assignments
            ("{% javascript_reset %}", ""),  # clear registry
            (
                "{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %}2{% endjavascript_assign %} - {% javascript_render %}",
                " - 1\n2",
            ),  # strict duplicates are ignored
            ("{% javascript_reset %}", ""),  # clear registry
            (
                "{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %}2{% endjavascript_assign %}{% javascript_assign %}1{% endjavascript_assign %} - {% javascript_render %}",
                " - 1\n2",
            ),  # strict duplicates are ignored, whatever the order
            ("{% javascript_reset %}", ""),  # clear registry
            (
                "{% javascript_assign %}1{% endjavascript_assign %}{% javascript_assign %} 1{% endjavascript_assign %}{% javascript_assign %}2{% endjavascript_assign %} - {% javascript_render %}",
                " - 1\n 1\n2",
            ),  # non strict duplicates are not ignored
            ("{% javascript_reset %}", ""),  # clear registry
            (
                '{% spaceless %}{% include "tests/templateaddons/javascript/home.html" %}{% endspaceless %}',
                strip_spaces_between_tags("""<html>    
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
</html>"""),
            ),
        ]
        # add template tag library to template code
        fixtures = [
            ("{% load javascript %}" + template_code, valid_output) for (template_code, valid_output) in fixtures
        ]
        # test real output
        self.validate_template_code_result(fixtures)


class ReplaceTemplateTagTestCase(TemplateTagTestCase):
    """Tests the {% replace %} template tag"""

    def test_output(self):
        # set up fixtures
        fixtures = [
            ("{% replace %}{% endreplace %}", ""),  # does nothing
            ('{% replace search="" replacement="" %}{% endreplace %}', ""),  # does nothing
            ('{% replace search="" replacement="" %}toto{% endreplace %}', "toto"),
            ('{% replace search="" replacement="aa" %}toto{% endreplace %}', "toto"),
            ('{% replace search="t" replacement="m" %}toto{% endreplace %}', "momo"),
            ('{% replace search="t" replacement="" %}toto{% endreplace %}', "oo"),
            ('{% replace search="to" replacement="ma" %}toto{% endreplace %}', "mama"),
            ('{% replace search="toto" replacement="a" %}toto{% endreplace %}', "a"),
            ('{% replace search=" " replacement="-" %}t o t o{% endreplace %}', "t-o-t-o"),
            ('{% replace search="\\n" replacement="" %}t\noto{% endreplace %}', "toto"),  # antislash character works
            ('{% replace search="[a-z]+" replacement="" %}Toto{% endreplace %}', "T"),  # regular expressions
            ('{% replace search="^." replacement="A" %}toto{% endreplace %}', "Aoto"),  # regular expressions
            ('{% replace search="to$" replacement="Z" %}toto{% endreplace %}', "toZ"),  # regular expressions
            (
                '{% replace search="\\s+" replacement="-" %}to\t \n\n   \tto{% endreplace %}',
                "to-to",
            ),  # regular expressions
            (
                '{% replace search="(to)" replacement="\\1a" %}toto{% endreplace %}',
                "toatoa",
            ),  # backreferences in regular expressions
            (
                '{% replace search="([a-z]+)" replacement="*\\1*" %}123abc456def{% endreplace %}',
                "123*abc*456*def*",
            ),  # backreferences in regular expressions
            ('{% replace search="(to)" replacement="au" %}(to)to{% endreplace %}', "(au)au"),  # regexp not escaped
            (
                '{% replace search="(to)" replacement="au" use_regexp=0 %}(to)to{% endreplace %}',
                "auto",
            ),  # escaped regexp
            ("{% filter escape_regexp %}(to){% endfilter %}", r"\(to\)"),  # escaped regexp
        ]
        # add template tag library to template code
        fixtures = [("{% load replace %}" + template_code, valid_output) for (template_code, valid_output) in fixtures]
        # test real output
        self.validate_template_code_result(fixtures)
