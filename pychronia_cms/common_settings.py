# -*- coding: utf-8 -*-


# bugfix, to prevent djangoscms.models.monkeypatch_reverse from breaking i18n_patterns standard system #
import django.core.urlresolvers
django.core.urlresolvers.reverse.cms_monkeypatched = True

# bugfix for missing language prefixes in urls #
import menus.base
menus.base.NavigationNode._remove_current_root = lambda self, url: url


from pychronia_common.common_settings import *

LANGUAGE_CODE = 'fr' # for now, CMS content is french only so....

INSTALLED_APPS += [
    'pychronia_cms',

    'request', # stats on HTTP requests

    #'userprofiles',
    #'userprofiles.contrib.profiles',

    'djangocms_text_ckeditor', # must be before CMS
    'cms',
    'mptt',
    'menus',

    'cmsplugin_rst',
    'cmsplugin_simple_gallery',

    # 'djangocms_flash',
    # 'djangocms_googlemap',
    # 'djangocms_text',
    'djangocms_link',
    'djangocms_snippet',

    ## too weak versions of plugins ##
    # 'djangocms_file',
    # 'djangocms_picture',
    # 'djangocms_teaser',
    # 'djangocms_video',

    ## OR BETTER: ##
    'filer',

    'cmsplugin_filer_file',
    'cmsplugin_filer_folder',
    'cmsplugin_filer_image',
    'cmsplugin_filer_teaser',
    'cmsplugin_filer_video',
    'jplayer', # cmsplugin too

    'django.contrib.comments', # for zinnia blog
    'tagging',
    'zinnia',
    'cmsplugin_zinnia',
]


TEMPLATE_CONTEXT_PROCESSORS = TEMPLATE_CONTEXT_PROCESSORS + ("cms.context_processors.cms_settings",) # for CMS_MEDIA_URL etc.


MIDDLEWARE_CLASSES += (
'django.middleware.clickjacking.XFrameOptionsMiddleware',
'django.middleware.csrf.CsrfViewMiddleware',
# #'cms.middleware.multilingual.MultilingualURLMiddleware', OBSOLETE
'cms.middleware.page.CurrentPageMiddleware',
'cms.middleware.user.CurrentUserMiddleware',
'request.middleware.RequestMiddleware',
'cms.middleware.toolbar.ToolbarMiddleware',
)


# global django overrides, easier than overridding models get_absolute_url() methods
ABSOLUTE_URL_OVERRIDES = {
    'auth.user': (lambda u: "/") # access to user data, eg. u.username
}


############# DJANGO-APP CONFS ############


## DJANGO-REQUEST STATS CONF ##
# most settings only work with dev version of module, as of 2013/06
REQUEST_IGNORE_AJAX = True
REQUEST_ANONYMOUS_IP = True
REQUEST_LOG_USER = False
REQUEST_IGNORE_USERNAME = ("admin", "PKL")
REQUEST_IGNORE_PATHS = (
    r'^admin/',
    r'^static/',
)
REQUEST_ONLY_ERRORS = False


## DJANGO CONTRIB RST CONF ##
# on the public portal, only superuser write RST docs
# so we trust him for "raw" directive (not file insertion though)
RESTRUCTUREDTEXT_FILTER_SETTINGS["raw_enabled"] = True


CMS_LANGUAGES = {
    1: [
        {
            'code': 'fr',
            'name': ugettext('French'),
            'public': True,
        },
    ],
}


## DJANGO CMS CONF ##
CMS_TEMPLATES = (
   ('cms_one_column.html', ugettext('One column')),
   ('cms_two_columns.html', ugettext('Two columns')),
)
CMS_URL_OVERWRITE = True
CMS_MENU_TITLE_OVERWRITE = True
CMS_REDIRECTS = True # handy for "dummy" menu entries
CMS_SEO_FIELDS = True # page metadata etc.

CMS_SOFTROOT = False # no need to cut the menu in sections
CMS_PUBLIC_FOR = "all" # not restricted to "staff"
CMS_PERMISSION = False # no fine grained restrictions ATM
CMS_TEMPLATE_INHERITANCE = True
CMS_PLACEHOLDER_CONF = {} # unused atm
CMS_PLUGIN_CONTEXT_PROCESSORS = []
CMS_PLUGIN_PROCESSORS = []
PLACEHOLDER_FRONTEND_EDITING = True

CMS_MULTILINGUAL_PATCH_REVERSE = False
'''
CMS_LANGUAGE_CONF = { # fallbacks ordering
    'fr': ['en'],
    'en': ['fr'],
}
'''

CMS_HIDE_UNTRANSLATED = False
CMS_LANGUAGE_FALLBACK = False
CMS_FRONTEND_LANGUAGES = ("fr",)
CMS_CACHE_PREFIX = "chryscms-" # useful if multiple CMS installations
CMS_CACHE_DURATIONS = { # in seconds
    'menus': 60 * 60,
    'content': 60,
    'permissions': 60 * 60,
}

CMS_MAX_PAGE_PUBLISH_REVERSIONS = 25 # FIXME - for when we'll use DJANGO-REVERSION


## SIMPLEGALLERY CONF ##
CMS_SIMPLEGALLERY_THUMBNAIL_OPTIONS = {
    'size': (240, 180),
    'crop': True,
    'quality': 80,
}


## ORIGINAL ZINNIA CONF ##
# note: if error "Unknown column 'zinnia_entry.content_placeholder_id' in 'field list" => python manage.py reset zinnia
ZINNIA_ENTRY_BASE_MODEL = 'cmsplugin_zinnia.placeholder.EntryPlaceholder'
ZINNIA_PAGINATION = 10
ZINNIA_UPLOAD_TO = "uploads/zinnia"
ZINNIA_PROTOCOL = "http"
ZINNIA_COPYRIGHT = "ChrysalisGame"
ZINNIA_USE_TWITTER = False # todo later


## CMSPLUGIN ZINNIA CONF ##
CMSPLUGIN_ZINNIA_HIDE_ENTRY_MENU = True
CMSPLUGIN_ZINNIA_TEMPLATES = []
CMSPLUGIN_ZINNIA_APP_MENUS = []


## CMSPLUGIN JPLAYER CONF ##
JPLAYER_BASE_PATH = STATIC_URL + "libs/jquery-jplayer-2.3.0/" # for Jplayer SWF object mainly


## DJANGO REGISTRATION CONF ##
ACCOUNT_ACTIVATION_DAYS = 7



## DJANGO AUTH & USERPROFILES CONF ##
AUTH_PROFILE_MODULE = "pychronia_cms.Profile"
USERPROFILES_REGISTRATION_FORM = 'pychronia_cms.forms.RegistrationForm'
USERPROFILES_USE_ACCOUNT_VERIFICATION = False # default
USERPROFILES_AUTO_LOGIN = True # Automatically log in the user upon registration
USERPROFILES_USE_PROFILE = True
USERPROFILES_PROFILE_ALLOW_EMAIL_CHANGE = True



## WYMEDITOR CONF ##
''' USELESS now that we have ckeditor
WYM_TOOLS = ",\n".join([
    "{'name': 'Bold', 'title': 'Strong', 'css': 'wym_tools_strong'}",
    "{'name': 'Italic', 'title': 'Emphasis', 'css': 'wym_tools_emphasis'}",
    "{'name': 'Superscript', 'title': 'Superscript', 'css': 'wym_tools_superscript'}",
    "{'name': 'Subscript', 'title': 'Subscript', 'css': 'wym_tools_subscript'}",
    "{'name': 'InsertOrderedList', 'title': 'Ordered_List', 'css': 'wym_tools_ordered_list'}",
    "{'name': 'InsertUnorderedList', 'title': 'Unordered_List', 'css': 'wym_tools_unordered_list'}",
    "{'name': 'Indent', 'title': 'Indent', 'css': 'wym_tools_indent'}",
    "{'name': 'Outdent', 'title': 'Outdent', 'css': 'wym_tools_outdent'}",
    "{'name': 'Undo', 'title': 'Undo', 'css': 'wym_tools_undo'}",
    "{'name': 'Redo', 'title': 'Redo', 'css': 'wym_tools_redo'}",
    "{'name': 'Paste', 'title': 'Paste_From_Word', 'css': 'wym_tools_paste'}",
    "{'name': 'ToggleHtml', 'title': 'HTML', 'css': 'wym_tools_html'}",
    ##"{'name': 'CreateLink', 'title': 'Link', 'css': 'wym_tools_link'}",
    ##"{'name': 'Unlink', 'title': 'Unlink', 'css': 'wym_tools_unlink'}",
    ##"{'name': 'InsertImage', 'title': 'Image', 'css': 'wym_tools_image'}",
    "{'name': 'InsertTable', 'title': 'Table', 'css': 'wym_tools_table'}",
    "{'name': 'Preview', 'title': 'Preview', 'css': 'wym_tools_preview'}",
])

WYM_CONTAINERS = ",\n".join([
    "{'name': 'P', 'title': 'Paragraph', 'css': 'wym_containers_p'}",
    "{'name': 'H1', 'title': 'Heading_1', 'css': 'wym_containers_h1'}",
    "{'name': 'H2', 'title': 'Heading_2', 'css': 'wym_containers_h2'}",
    "{'name': 'H3', 'title': 'Heading_3', 'css': 'wym_containers_h3'}",
    "{'name': 'H4', 'title': 'Heading_4', 'css': 'wym_containers_h4'}",
    "{'name': 'H5', 'title': 'Heading_5', 'css': 'wym_containers_h5'}",
    "{'name': 'H6', 'title': 'Heading_6', 'css': 'wym_containers_h6'}",
    "{'name': 'PRE', 'title': 'Preformatted', 'css': 'wym_containers_pre'}",
    "{'name': 'BLOCKQUOTE', 'title': 'Blockquote', 'css': 'wym_containers_blockquote'}",
    ##"{'name': 'TH', 'title': 'Table_Header', 'css': 'wym_containers_th'}",
])

WYM_CLASSES = ",\n".join([
    "{'name': 'date', 'title': 'PARA: Date', 'expr': 'p'}",
    "{'name': 'hidden-note', 'title': 'PARA: Hidden note', 'expr': 'p[@class!=\"important\"]'}",
])

WYM_STYLES = ",\n".join([
    "{'name': '.hidden-note', 'css': 'color: #999; border: 2px solid #ccc;'}",
    "{'name': '.date', 'css': 'background-color: #ff9; border: 2px solid #ee9;'}",
])
'''



## CKEDITOR SETTINGS ##
# remember, when installing it over standard django-cms text plugins : launch python manage.py migrate djangocms_text_ckeditor 0001 --fake
#See http://docs.cksource.com/ckeditor_api/symbols/CKEDITOR.config.html for all settings

CKEDITOR_SETTINGS = {
            'language': '{{ language }}',
            'skin': 'moono',
            'height': '320px',
            'toolbar': 'CMS',
            'toolbar_CMS': [
                ['Undo', 'Redo'],
                ['cmsplugins', '-', 'ShowBlocks'],
                ['Font', 'FontSize', 'Format', 'Styles'],
                ['TextColor', 'BGColor', '-', 'PasteText', 'PasteFromWord'],
                ['Maximize', ''],
                '/',
                ['Bold', 'Italic', 'Underline', '-', 'Subscript', 'Superscript', '-', 'RemoveFormat'],
                ['CreateDiv', 'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock'],
                ['Link', 'Unlink'],
                ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'Table'],
                ['Source']
            ],
            'toolbarCanCollapse': False,
            'extraPlugins': 'cmsplugins'
}






'''
## DJANGO LOCALEURL CONF - OBSOLETE TO DELETE ASAP
 
LOCALE_INDEPENDENT_PATHS = ()
LOCALE_INDEPENDENT_MEDIA_URL = True
PREFIX_DEFAULT_LOCALE = True # whether we must enforce a locale in url even for default language
USE_ACCEPT_LANGUAGE = True # use http headres to choose the right language
LOCALE_INDEPENDENT_PATHS = (
      '^/$',
      '^/files/',
      '^/admin/',
      '^/media/',
      '^/static/',
      '^/i18n/', # TO BE REMOVED
      )
'''
