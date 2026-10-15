# -*- coding: utf-8 -*-
"""
Vendored from djangocms_text_ckeditor.picture_save (5.1.7), since djangocms-text (the
successor plugin) dropped its own implementation of TEXT_SAVE_IMAGE_FUNCTION and expects
projects to supply one. Converts a base64 image pasted into the rich text editor into a
real filer Image, wrapped in a djangocms_picture.Picture plugin.
"""
from django.core.files.base import ContentFile

from cms.models.pluginmodel import CMSPlugin


def create_picture_plugin(filename, file, parent_plugin, **kwargs):
    from djangocms_picture.models import Picture

    pic = Picture()
    pic.placeholder = parent_plugin.placeholder
    pic.parent = parent_plugin
    pic.position = CMSPlugin.objects.filter(parent=parent_plugin).count()
    pic.language = parent_plugin.language
    pic.plugin_type = 'PicturePlugin'

    # Set the FilerImageField value.
    from filer.settings import FILER_IMAGE_MODEL
    from filer.utils.loader import load_model
    image_class = load_model(FILER_IMAGE_MODEL)
    image_obj = image_class(file=ContentFile(file.read(), name=filename))
    image_obj.save()
    pic.picture = image_obj

    pic.save()
    return pic
