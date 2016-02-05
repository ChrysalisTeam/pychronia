# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from django.db.utils import DatabaseError
from pychronia_game.utilities import encryption

SESSION_TICKET_KEY_TEMPLATE = 'pychronia_session_ticket_%s'
IMPERSONATION_TARGET_POST_VARIABLE = "_set_impersonation_target_"
IMPERSONATION_WRITABILITY_POST_VARIABLE = "_set_impersonation_writability_"
ENFORCED_SESSION_TICKET_NAME = "session_ticket"

TEMP_URL_USERNAME = "redirect"  # with this as placeholder in URL, user will get redirected to proper URL without error
UNIVERSAL_URL_USERNAME = "anyuser"  # with this as placeholder in URL, no redirection will occur, session will not be URL-backed

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


def instance_session_key(game_instance_id):
    utilities.check_is_slug(game_instance_id)
    return SESSION_TICKET_KEY_TEMPLATE % game_instance_id


def clear_all_sessions(request):
    request.datamanager.logout_user()
    request.session.flush()
    ## USELESSrequest.session.cycle_key() # security


def logout_session(request):
    request.datamanager.logout_user()
    instance_key = instance_session_key(request.datamanager.game_instance_id)
    if instance_key in request.session:
        del request.session[instance_key]


def _enrich_request_metadata_with_instance_session_ticket(request, session_ticket):
    """Meant to help debugging critical failures."""
    request.META["session_ticket"] = session_ticket


def try_authenticating_with_credentials(request, username, password):
    """
    This function lets exceptions flow...
    """
    datamanager = request.datamanager
    session_ticket = datamanager.authenticate_with_credentials(username, password)

    instance_key = instance_session_key(request.datamanager.game_instance_id)
    request.session[instance_key] = session_ticket # overrides
    _enrich_request_metadata_with_instance_session_ticket(request, session_ticket=session_ticket)


def _lookup_enforced_session_or_none(request):
    session_ticket = None
    is_observer = False

    if config.GAME_ALLOW_ENFORCED_LOGIN:
        login_data = request.REQUEST.get(ENFORCED_SESSION_TICKET_NAME)
        if login_data:
            try:
                login_data = login_data.encode("ascii", "strict")
                login_data = encryption.unicode_decrypt(login_data) # decode using site's SECRET_KEY
            except (TypeError, ValueError, UnicodeError), e:
                logging.warning("Error when trying to decode enforced ticket: %r" % e)
            else:
                data_list = login_data.split("|")
                if len(data_list) == 2: # LEGACY
                    enforced_instance_id, enforced_login = data_list
                else:
                    assert len(data_list) == 3, data_list
                    enforced_instance_id, enforced_login, is_observer_str = data_list
                    is_observer = bool(is_observer_str) # should be "observer"
                    del is_observer_str
                if enforced_instance_id != request.datamanager.game_instance_id:
                    logging.warning("Wrong game instance id in enforced ticket: %s should contain %s instead", login_data, request.datamanager.game_instance_id)
                else:
                    session_ticket = dict(game_instance_id=enforced_instance_id,
                                          game_username=enforced_login,
                                          impersonation_target=None,
                                          impersonation_writability=None,
                                          is_observer=is_observer)
    return session_ticket


def compute_enforced_login_token(game_instance_id, login, is_observer=False):
    assert is_observer in (True, False)
    login_data = "%s|%s|%s" % (game_instance_id, login, "observer" if is_observer else "")
    return encryption.unicode_encrypt(login_data)
    


def try_authenticating_with_session(request, url_game_username=None):
    """
    This function lets exceptions flow...
    """
    datamanager = request.datamanager
    instance_key = instance_session_key(datamanager.game_instance_id)
    session_ticket = request.session.get(instance_key, None)

    potential_session_ticket = _lookup_enforced_session_or_none(request)
    if potential_session_ticket:
        logging.warning("Using ENFORCED session ticket: %r", potential_session_ticket)
        session_ticket = potential_session_ticket
    del potential_session_ticket

    # BEWARE, here we distinguish between empty string (=> stop impersonation) and None (=> use current settings)
    if IMPERSONATION_TARGET_POST_VARIABLE in request.POST or IMPERSONATION_WRITABILITY_POST_VARIABLE in request.POST:

        # Beware here, pop() on QueryDict would return a LIST always
        requested_impersonation_target = request.POST.get(IMPERSONATION_TARGET_POST_VARIABLE, None) # beware, != "" here
        requested_impersonation_writability = request.POST.get(IMPERSONATION_WRITABILITY_POST_VARIABLE, None) # ternary value
        if requested_impersonation_writability is not None:
            requested_impersonation_writability = True if requested_impersonation_writability.strip().lower() == "true" else False

        request.POST.clear() # thanks to our middleware that made it mutable...
        request.method = "GET" # dirty, isn't it ?

    else:
        requested_impersonation_target = requested_impersonation_writability = None

    # priority to POST data, but beware of special (requested_impersonation_target=="") case
    final_requested_impersonation_target = requested_impersonation_target if requested_impersonation_target is not None else url_game_username
    
    try:
        res = datamanager.authenticate_with_session_data(session_ticket=session_ticket, # may be None
                                                           requested_impersonation_target=final_requested_impersonation_target,
                                                           requested_impersonation_writability=requested_impersonation_writability,
                                                           django_user=request.user) # can be anonymous
        #print("NEW AUTHENTICATION DATA IN SESSION", res)
        request.session[instance_key] = res  # this refreshes expiry time, and ensures we properly modify session

    except UsageError, e:
        # invalid session data, or request vars...
        logging.critical("Error in try_authenticating_with_session with locals %r" % repr(locals()), exc_info=True)
        request.session[instance_key] = None # important cleanup!
        pass # thus, if error, we let the anonymous user be...

    _enrich_request_metadata_with_instance_session_ticket(request, session_ticket=session_ticket)

    try:
        request.session.save() # force IMMEDIATE saving, to avoid lost updates between web and ajax (eg. chatroom) requests
    except DatabaseError, e:
        logging.warning("Immediate saving of django session failed (%r), it's expected during unit-tests when DB is not setup...", e)




'''
def _redirection_to_login(request):
    return HttpResponseRedirect(reversssse("pychronia_game.views.login", kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))


@decorator
def basic_access_required(func, request, *args, **kwargs):
    """
    Decorator to apply basic filtering to views, depending on the global availability of these views and their menus.
    """
    if not request.datamanager.user.is_master:
        view_is_allowed = request.datamanager.view_is_allowed


def game_player_required(object=None, permission=None):
    """
    Decorator to only allow normal players, possibly with 
    special access permissions.
    """
    if object and not isinstance(object, collections.Callable):
        raise RuntimeError("game_player_required decorator badly used")

    def decorate(func):
        @decorator
        def player_auth_wrapper(func, request, *args, **kwargs):
            user = request.datamanager.user
            if not user.is_character or (permission and not user.has_permission(permission)):
                user.add_error(_("Access reserved to privileged members."))
                return _redirection_to_login(request)
            return func(request, *args, **kwargs)
        wrapped = player_auth_wrapper(func)
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
'''








