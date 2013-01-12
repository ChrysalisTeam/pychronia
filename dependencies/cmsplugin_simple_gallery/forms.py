from django.contrib.admin.widgets import AdminFileWidget
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.conf import settings
from easy_thumbnails.files import get_thumbnailer
from settings import CMS_SIMPLEGALLERY_THUMBNAIL_OPTIONS

class AdminImageWidget(AdminFileWidget):
    def render(self, name, value, attrs=None):
        output = []
        if value and getattr(value, "url", None):
            thumbnail = get_thumbnailer(value).get_thumbnail_name(CMS_SIMPLEGALLERY_THUMBNAIL_OPTIONS)
            image_url = settings.MEDIA_URL + thumbnail
            file_name=str(value)
            output.append(u' <a href="%s" target="_blank"><img src="%s" alt="%s" style="height: 100px;" /></a><br /> %s ' %\
                          (unicode(image_url), unicode(image_url), unicode(file_name), _('Change:')))

        output.append(super(AdminFileWidget, self).render(name, value, attrs))
        return mark_safe(u''.join(output))
