from django.conf import settings


TEMPLATEADDONS_COUNTERS_VARIABLE = getattr(settings, 'TEMPLATEADDONS_COUNTER_GLOBAL_VARIABLE', '_templateaddons_counters')
