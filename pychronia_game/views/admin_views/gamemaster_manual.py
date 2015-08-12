# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_game_view import register_view


@register_view(access=UserAccess.master, title=ugettext_lazy("Master Manual"))
def gamemaster_manual(request, template_name="administration/master_manual.html"):

    dm = request.datamanager

    gamemaster_manual = dm.get_gamemaster_manual_for_html()

    return render(request,
                  template_name,
                    {
                     "gamemaster_manual": gamemaster_manual
                    })

'''

MAYBE ONE DAY, generate pdf directly from webserver 
(but security issues with RAW docutils directives must be handled first)

@register_view(access=UserAccess.master, title=ugettext_lazy("Master Manual PDF Export"))
def gamemaster_manual_pdf(request, template_name="administration/master_manual.html"):

    dm = request.datamanager

    gamemaster_manual = "hello boys"

    from rst2pdf.createpdf import RstToPdf

    RstToPdf(
            stylesheets=options.style,
            language=options.language,
            header=options.header, footer=options.footer,
            inlinelinks=options.inlinelinks,
            breaklevel=int(options.breaklevel),
            baseurl=options.baseurl,
            fit_mode=options.fit_mode,
            background_fit_mode=options.background_fit_mode,
            smarty=str(options.smarty),
            font_path=options.fpath,
            style_path=options.stylepath,
            repeat_table_rows=options.repeattablerows,
            footnote_backlinks=options.footnote_backlinks,
            inline_footnotes=options.inline_footnotes,
            real_footnotes=options.real_footnotes,
            def_dpi=int(options.def_dpi),
            basedir=options.basedir,
            show_frame=options.show_frame,
            splittables=options.splittables,
            blank_first_page=options.blank_first_page,
            first_page_on_right=options.first_page_on_right,
            breakside=options.breakside,
            custom_cover=options.custom_cover,
            floating_images=options.floating_images,
            numbered_links=options.numbered_links,
            raw_html=options.raw_html,
            section_header_depth=int(options.section_header_depth),
            strip_elements_with_classes=options.strip_elements_with_classes,
            ).createPdf(text=options.infile.read(),
                        source_path=options.infile.name,
                        output=options.outfile,
                        compressed=options.compressed)
    return render(request,
                  template_name,
                    {
                     "gamemaster_manual": gamemaster_manual
                    })
'''