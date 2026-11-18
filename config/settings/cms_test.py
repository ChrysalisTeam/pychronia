"""TEST settings of the CMS site: throwaway SQL DB in a temp folder."""

from config.settings.cms import *
from config.settings._transient import *

ROOT_URLCONF = "pychronia_cms.tests._test_urls"
