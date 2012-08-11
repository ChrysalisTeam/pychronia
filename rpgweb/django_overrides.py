# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls.defaults import *
from .utilities import config
from django.core.urlresolvers import get_callable, reverse as django_reverse



def gameview_patterns(prefix, *args):
    """
    Resolves dotted callable paths to objects, 
    and looks for their "as_view" method if they're
    subclasses of AbstractGameView.
    """
    from rpgweb.views._abstract_game_view import AbstractGameView
    if prefix:
        prefix = prefix + "."
    my_patterns = []
    for regex, obj in args:
        if isinstance(obj, basestring):
            view = get_callable(prefix + obj)
            if isinstance(view, type) and issubclass(view, AbstractGameView):
                view = view.as_view
            my_patterns.append((regex, view))
        else:
            my_patterns.append((regex, obj)) # already a callable
    
    from pprint import pprint
    pprint( my_patterns)

    return patterns(prefix, *my_patterns)


def gameview_reverse(viewname, *args, **kwargs):
    from rpgweb.views._abstract_game_view import AbstractGameView
    if isinstance(viewname, basestring):
        viewname = get_callable(viewname)
    if isinstance(viewname, type) and issubclass(viewname, AbstractGameView):
        viewname = viewname.as_view
    return django_reverse(viewname, *args, **kwargs)



import django.core.urlresolvers
django.core.urlresolvers.reverse = gameview_reverse # UGLY monkey patching...

 