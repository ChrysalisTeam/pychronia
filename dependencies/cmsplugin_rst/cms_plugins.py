# -*- coding: utf-8 -*-
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from cmsplugin_rst.forms import RstPluginForm
from cmsplugin_rst.models import RstPluginModel
from cmsplugin_rst.utils import postprocess
from django.contrib.markup.templatetags.markup import restructuredtext
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

class RstPlugin(CMSPluginBase):
    name = _('Restructured Text Plugin')
    render_template = 'cms/content.html'
    model = RstPluginModel
    form = RstPluginForm

    def render(self, context, instance, placeholder):
        rst = instance.body
        rst = rst.replace("{{ MEDIA_URL }}", settings.MEDIA_URL)
        rst = rst.replace("{{ STATIC_URL }}", settings.STATIC_URL)
        context.update({'content': postprocess(restructuredtext(rst))})
        return context

plugin_pool.register_plugin(RstPlugin)
