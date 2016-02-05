# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers import rst

from .mediaplayers import generate_audio_player, generate_media_player, generate_image_viewer


class AudioEmbedDirective(rst.Directive):

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}
    has_content = False

    def run(self):
        code = generate_audio_player(files=[self.arguments[0]])
        return [nodes.raw('', code, format='html')]

directives.register_directive("embed_audio", AudioEmbedDirective)



class VideoEmbedDirective(rst.Directive):

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {'height': directives.length_or_unitless,
                   'width': directives.length_or_percentage_or_unitless,
                   'image': directives.unchanged} # front image url
    has_content = False

    def run(self):
        code = generate_media_player(fileurl=self.arguments[0],
                                     **self.options) # not present if not valued
        return [nodes.raw('', code, format='html')]

directives.register_directive("embed_video", VideoEmbedDirective)



class ImageEmbedDirective(rst.Directive):
    # currently useless, use GAME_IMAGE_URL instead!
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {'alias': directives.unchanged,  # easy-thumbnail preset
                   'align': directives.unchanged}  # like in "image" directive
    has_content = False

    align_h_values = ('left', 'center', 'right')

    def run(self):

        if 'align' in self.options:
            if self.options['align'] not in self.align_h_values:
                raise self.error(
                    'Error in "%s" directive: "%s" is not a valid value for '
                    'the "align" option.  Valid values for "align" are: "%s".'
                    % (self.name, self.options['align'],
                       '", "'.join(self.align_h_values)))

        code = generate_image_viewer(imageurl=self.arguments[0],
                                     preset=self.options.get("alias", "default"), # BEWARE - we expect that "default" preset to exist in settings!
                                     align=self.options.get("align", ""))
        return [nodes.raw('', code, format='html')]


directives.register_directive("embed_image", ImageEmbedDirective)






# TODO - ImageEmbedDirective which uses eaysthumbnails if possible to get final url, and reuses image node in any case


'''
        # Raise an error if the directive does not have contents.
        self.assert_has_content()
        text = '\n'.join(self.content)
        # Create the admonition node, to be populated by `nested_parse`.
        admonition_node = self.node_class(rawsource=text)
        # Parse the directive contents.
        self.state.nested_parse(self.content, self.content_offset,
                                admonition_node)
        return [admonition_node]




CODE = """\
<object type="application/x-shockwave-flash"
        width="%(width)s"
        height="%(height)s"
        class="youtube-embed"
        data="http://www.youtube.com/v/%(yid)s">
    <param name="movie" value="http://www.youtube.com/v/%(yid)s"></param>
    <param name="wmode" value="transparent"></param>%(extra)s
</object>
"""

PARAM = """\n    <param name="%s" value="%s"></param>"""

def youtube(name, args, options, content, lineno,
            contentOffset, blockText, state, stateMachine):
    """ Restructured text extension for inserting youtube embedded videos """
    if len(content) == 0:
        return
    string_vars = {
        'yid': content[0],
        'width': 425,
        'height': 344,
        'extra': ''
        }
    extra_args = content[1:] # Because content[0] is ID
    extra_args = [ea.strip().split("=") for ea in extra_args] # key=value
    extra_args = [ea for ea in extra_args if len(ea) == 2] # drop bad lines
    extra_args = dict(extra_args)
    if 'width' in extra_args:
        string_vars['width'] = extra_args.pop('width')
    if 'height' in extra_args:
        string_vars['height'] = extra_args.pop('height')
    if extra_args:
        params = [PARAM % (key, extra_args[key]) for key in extra_args]
        string_vars['extra'] = "".join(params)
    return [nodes.raw('', CODE % (string_vars), format='html')]
youtube.content = True
directives.register_directive('youtube', youtube)
'''
