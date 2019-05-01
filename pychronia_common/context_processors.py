import sys
from django.conf import settings

def google_analytics(request):
    """
    Use the variables returned in this function to
    render your Google Analytics tracking code template.
    """
    ga_prop_id = settings.GOOGLE_ANALYTICS_PROPERTY_ID
    ga_domain = settings.GOOGLE_ANALYTICS_DOMAIN
    res = {
        'GOOGLE_ANALYTICS_PROPERTY_ID': ga_prop_id,
        'GOOGLE_ANALYTICS_DOMAIN': ga_domain,
    }
    #print(">>>>>>>>google_analytics>>>>>>>", res, file=sys.stderr)
    return res
