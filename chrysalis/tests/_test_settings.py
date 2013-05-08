# -*- coding: utf-8 -*-


import os
from rpgweb_common.common_settings import *


TEST_DIR = os.path.dirname(os.path.abspath(__file__))


DEBUG = True
TEMPLATE_DEBUG = DEBUG


# Make this unique, and don't share it with anybody.
SECRET_KEY = '=%f!!2^yh5gk982827p8QD725wsdfsdf2kz^$vbjyqalyYgSzvd'


SITE_DOMAIN = "http://127.0.0.1" # NO trailing slash ! # USELESS ?? FIXME


MEDIA_ROOT = os.path.join(ROOT_PATH, "chrysalis", "media") # useless


ROOT_URLCONF = 'chrysalis.tests._test_urls'


TEMPLATE_CONTEXT_PROCESSORS = TEMPLATE_CONTEXT_PROCESSORS + ("cms.context_processors.media",)


MIDDLEWARE_CLASSES = (
'sessionprofile.middleware.SessionProfileMiddleware',
'django.contrib.sessions.middleware.SessionMiddleware',
'django.contrib.messages.middleware.MessageMiddleware',
# 'localeurl.middleware.LocaleURLMiddleware',
# 'django.middleware.locale.LocaleMiddleware', replaced by LocaleURLMiddleware
'django.middleware.common.CommonMiddleware',
'django.contrib.auth.middleware.AuthenticationMiddleware',
# #'cms.middleware.multilingual.MultilingualURLMiddleware',
'cms.middleware.page.CurrentPageMiddleware',
'cms.middleware.user.CurrentUserMiddleware',
'cms.middleware.toolbar.ToolbarMiddleware',
#'debug_toolbar.middleware.DebugToolbarMiddleware',
)



INSTALLED_APPS += [
    'chrysalis',

    'cms',
    'mptt',
    'menus',

    'cmsplugin_rst',
    'cmsplugin_simple_gallery',

    # 'cms.plugins.flash',
    # 'cms.plugins.googlemap',
    'cms.plugins.link',
    'cms.plugins.snippet',
    'cms.plugins.text',


    ## too weak ##
    # 'cms.plugins.file',
    # 'cms.plugins.picture',
    # 'cms.plugins.teaser',
    # 'cms.plugins.video',

    ## OR BETTER: ##
    'filer',
    'easy_thumbnails',
    'cmsplugin_filer_file',
    'cmsplugin_filer_folder',
    'cmsplugin_filer_image',
    'cmsplugin_filer_teaser',
    'cmsplugin_filer_video',
    'jplayer', # cmsplugin too

    'django.contrib.comments', # for blog
    'tagging',
    'zinnia',
    'cmsplugin_zinnia',
]



THUMBNAIL_PROCESSORS = (
    'easy_thumbnails.processors.colorspace',
    'easy_thumbnails.processors.autocrop',
    # 'easy_thumbnails.processors.scale_and_crop',
    'filer.thumbnail_processors.scale_and_crop_with_subject_location',
    'easy_thumbnails.processors.filters',
)

CMS_SIMPLEGALLERY_THUMBNAIL_OPTIONS = {
    'size': (240, 180),
    'crop': True,
    'quality': 80,
}



ZINNIA_ENTRY_BASE_MODEL = 'cmsplugin_zinnia.placeholder.EntryPlaceholder'
ZINNIA_PAGINATION = 1
ZINNIA_UPLOAD_TO = "uploads/zinnia"
ZINNIA_PROTOCOL = "http"
ZINNIA_COPYRIGHT = "ChrysalisGame"
ZINNIA_USE_TWITTER = False # todo later

CMSPLUGIN_ZINNIA_HIDE_ENTRY_MENU = True
CMSPLUGIN_ZINNIA_TEMPLATES = []
CMSPLUGIN_ZINNIA_APP_MENUS = []


JPLAYER_BASE_PATH = "/static/resources/libs/jquery-jplayer-1.1.1/"

