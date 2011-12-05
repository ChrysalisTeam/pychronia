# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import UsageError
from django.http import Http404, HttpResponseRedirect, HttpResponse

SESSION_TICKET_KEY = 'rpgweb_session_ticket'
SESSION_TIMESTAMP_KEY = 'rpgweb_session_timestamp'

"""
Django Notes

Reading a session is not considered activity for expiration purposes. Session expiration is computed from the last time the session was modified.
Use normal Python strings as dictionary keys on request.session. This is more of a convention than a hard-and-fast rule.
Session dictionary keys that begin with an underscore are reserved for internal use by Django.
Don’t override request.session with a new object, and don’t access or set its attributes. Use it like a Python dictionary.
The session dictionary should accept any pickleable Python object. See the pickle module for more information.
Session data is stored in a database table named django_session .
Django only sends a cookie if it needs to. If you don't set any session data, it won't send a session cookie.
"""





def clear_session(request):
    request.session.flush()
    request.session.cycle_key()


def authenticate_with_credentials(request, username, password):
    """
    This function lets exceptions flow...
    """
    datamanager = request.datamanager
    session_ticket = datamanager.authenticate_with_credentials(username, password)
    clear_session(request)
    request.session[SESSION_TICKET_KEY] = session_ticket


def try_authenticating_with_ticket(request):
    """
    This function lets exceptions flow...
    """
    datamanager = request.datamanager
    session_ticket = request.session.get(SESSION_TICKET_KEY)

    if session_ticket is not None:
        try:
            datamanager.authenticate_with_ticket(session_ticket)
            request.session[SESSION_TIMESTAMP_KEY] = datetime.utcnow() # forces reset of expiry time
        except UsageError:
            logging.critical("Wrong session ticket detected: %r" % session_ticket, exc_info=True)
            # we let the anonymous user be...


def logout_session(request):
    request.datamanager.logout_user()
    clear_session(request)







def _redirection_to_login(request):
    return HttpResponseRedirect(reverse("rpgweb.views.login", kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))



def game_player_required(object=None, permission=None):
    """
    Decorator to only allow normal players, possibly with 
    special access permissions.
    """
    if object and not isinstance(object, collections.Callable):
        raise RuntimeError("game_player_required decorator badly used")

    def decorate(func):
        @decorator
        def wrapper(func, request, *args, **kwargs):
            user = request.datamanager.user
            if not user.is_character or (permission and not user.has_permission(permission)):
                user.add_error(_("Access reserved to privileged members."))
                return _redirection_to_login(request)
            return func(request, *args, **kwargs)
        wrapped = wrapper(func)
        wrapped.game_permission_required = permission
        return wrapped
    return decorate(object) if object else decorate


def game_master_required(func):
    """
    Decorator to only allow the game master.
    """
    @decorator
    def wrapper(func, request, *args, **kwargs):
        user = request.datamanager.user
        if not user.is_master:
            user.add_error(_("Access reserved to administrators."))
            return _redirection_to_login(request)
        return func(request, *args, **kwargs)
    wrapped = wrapper(func)
    wrapped.game_master_required = True
    return wrapped



def game_authenticated_required(func):
    """
    Decorators to allow game master and players, not visitors.
    """
    @decorator
    def wrapper(func, request, *args, **kwargs):
        user = request.datamanager.user
        if not user.is_authenticated:
            user.add_error(_("Access forbidden to anonymous users."))
            return _redirection_to_login(request)
        return func(request, *args, **kwargs)
    wrapped = wrapper(func)
    wrapped.game_authenticated_required = True
    return wrapped




def game_player_authentication(request):
    """
    Template context manager which adds "player" to the template context.
    """

    if hasattr(request, "datamanager"):

        online_users = [request.datamanager.get_official_name_from_username(username)
                        for username in request.datamanager.get_online_users()]

        return {'game_instance_id': request.datamanager.game_instance_id,
                'user': request.datamanager.user,
                'game_is_started': request.datamanager.get_global_parameter("game_is_started"),
                'online_users': online_users}
    else:
        return {} # not in valid game instance
    
    
    
    
    
    
    
    
