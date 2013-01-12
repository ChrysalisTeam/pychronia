from django.conf import settings

CMS_SIMPLEGALLERY_UPLOAD_TO = getattr(settings, 'CMS_SIMPLEGALLERY_UPLOAD_TO', 'cmsplugin_simple_gallery/images')
CMS_SIMPLEGALLERY_DEFAULT_TEMPLATE = getattr(settings, 'CMS_SIMPLEGALLERY_DEFAULT_TEMPLATE', 'cmsplugin_simple_gallery/fancy_image.html')
CMS_SIMPLEGALLERY_TEMPLATES = getattr(settings, 'CMS_SIMPLEGALLERY_TEMPLATES', [
    ('cmsplugin_simple_gallery/fancy_image.html', u'Display first only image form gallery'),
    ('cmsplugin_simple_gallery/fancy_gallery.html', u'Display all images from gallery'),
])
CMS_SIMPLEGALLERY_THUMBNAIL_OPTIONS = getattr(settings, 'CMS_SIMPLEGALLERY_THUMBNAIL_OPTIONS',{
    'size': (120, 90),
    'crop': True,
    'quality': 95,
})
