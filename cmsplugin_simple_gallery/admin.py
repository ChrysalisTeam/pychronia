from django.contrib import admin
from inline_ordering.admin import OrderableStackedInline
import forms
import models

class SimpleImageInline(OrderableStackedInline):
    model = models.SimpleImage

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'src':
            kwargs.pop('request', None)
            kwargs['widget'] = forms.AdminImageWidget
            return db_field.formfield(**kwargs)
        return super(SimpleImageInline, self).formfield_for_dbfield(db_field, **kwargs)

class SimpleGalleryAdmin(admin.ModelAdmin):
    inlines = [SimpleImageInline]

admin.site.register(models.SimpleGallery, SimpleGalleryAdmin)
