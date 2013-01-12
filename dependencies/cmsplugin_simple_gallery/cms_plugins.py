from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from django.utils.translation import ugettext_lazy as _
import models
import settings

class SimpleGalleryPlugin(CMSPluginBase):
    model = models.SimpleGalleryPointer
    name = _('Simple: Image gallery')
    render_template = settings.CMS_SIMPLEGALLERY_DEFAULT_TEMPLATE
    text_enabled = True

    def render(self, context, instance, placeholder):
        images = instance.gallery.simpleimage_set.all()
        #print images[0].src
        context.update({
            'images': images,
            'placeholder': placeholder,
            'gallery': instance.gallery,
        })
        self.render_template = instance.template
        return context

    def icon_src(self, instance):
        return instance.gallery.simpleimage_set.all()[0].get_thumbnail()

plugin_pool.register_plugin(SimpleGalleryPlugin)
