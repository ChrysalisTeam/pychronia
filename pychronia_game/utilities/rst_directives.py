# -*- coding: utf-8 -*-



from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers import rst

from .mediaplayers import generate_audio_player, generate_media_player, generate_image_viewer, get_medium_title_from_url


class AudioEmbedDirective(rst.Directive):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}
    has_content = False

    def run(self):
        file_url = self.arguments[0]
        #print("=========AudioEmbedDirective=========>", file_url)
        title = get_medium_title_from_url(file_url)
        code = generate_audio_player(files=[file_url], titles=[title])
        return [nodes.raw('', code, format='html')]


directives.register_directive("embed_audio", AudioEmbedDirective)


class VideoEmbedDirective(rst.Directive):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {'height': directives.length_or_unitless,
                   'width': directives.length_or_percentage_or_unitless,
                   'image': directives.unchanged}  # front image url
    has_content = False

    def run(self):
        file_url = self.arguments[0]
        #print("=========VideoEmbedDirective=========>", file_url)
        code = generate_media_player(fileurl=file_url,
                                     **self.options)  # not present if not valued
        return [nodes.raw('', code, format='html')]


directives.register_directive("embed_video", VideoEmbedDirective)


class ImageEmbedDirective(rst.Directive):
    """
    This directive is currently mostly useless, use ".. image::" and GAME_THUMBNAIL_URL instead!
    """
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {'alias': directives.unchanged,  # easy-thumbnail preset
                   'align': directives.unchanged}  # like in "image" directive
    has_content = False

    align_h_values = ('left', 'center', 'right')

    def run(self):

        file_url = self.arguments[0]

        if 'align' in self.options:
            if self.options['align'] not in self.align_h_values:
                raise self.error(
                    'Error in "%s" directive: "%s" is not a valid value for '
                    'the "align" option.  Valid values for "align" are: "%s".'
                    % (self.name, self.options['align'],
                       '", "'.join(self.align_h_values)))

        #print("=========ImageEmbedDirective=========>", file_url)
        code = generate_image_viewer(imageurl=file_url,
                                     preset=self.options.get("alias", "default"),
                                     # BEWARE - we expect that "default" preset to exist in settings!
                                     align=self.options.get("align", ""))
        return [nodes.raw('', code, format='html')]


directives.register_directive("embed_image", ImageEmbedDirective)

# TODO - ImageEmbedDirective which uses eaysthumbnails if possible to get final url, and reuses image node in any case
