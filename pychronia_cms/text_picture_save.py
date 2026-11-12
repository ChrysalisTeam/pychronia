# -*- coding: utf-8 -*-
"""
Vendored from djangocms_text_ckeditor.picture_save (5.1.7), since djangocms-text (the
successor plugin) dropped its own implementation of TEXT_SAVE_IMAGE_FUNCTION and expects
projects to supply one. Converts a base64 image pasted into the rich text editor into a
real filer Image, wrapped in a djangocms_picture.Picture plugin (adapted to the django CMS 4+ plugin tree).
"""
from django.core.files.base import ContentFile

from cms.api import add_plugin


def create_picture_plugin(filename, file, parent_plugin, **kwargs):
    # Set the FilerImageField value.
    from filer.settings import FILER_IMAGE_MODEL
    from filer.utils.loader import load_model
    image_class = load_model(FILER_IMAGE_MODEL)
    image_obj = image_class(file=ContentFile(file.read(), name=filename))
    image_obj.save()

    # Since django CMS 4, plugin positions are unique across the whole placeholder tree (not
    # restarting at 1 for each parent), so add_plugin() computes the position (after the last
    # descendant of the Text plugin) and shifts the following plugins, instead of a raw save().
    return add_plugin(
        parent_plugin.placeholder,
        "PicturePlugin",
        parent_plugin.language,
        position="last-child",
        target=parent_plugin,
        picture=image_obj,
    )
