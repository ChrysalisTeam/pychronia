# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import urllib
import json

from ZODB.POSException import POSError # parent of ConflictError

from pychronia_game.common import *
from pychronia_game.common import _undefined # for static checker...

from django.http import Http404, HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden, HttpResponseBadRequest
from django.core import urlresolvers
from django.utils.functional import Promise # used eg. for lazy-translated strings
from django.shortcuts import redirect

from ..datamanager import GameDataManager
from .abstract_form import AbstractGameForm, SimpleForm, UninstantiableFormError
from .datamanager_tools import transaction_watcher, readonly_method





@decorator
def transform_usage_error(caller, self, request, *args, **kwargs):
    """
    Can be used for both html and ajax requests, so only 'error' HTTP codes should be returned
    if an exception is encountered.
    """
    dm = request.datamanager

    return_to_home_url = game_view_url("pychronia_game-homepage", datamanager=dm)
    return_to_home = HttpResponseRedirect(return_to_home_url)

    from ..authentication import TEMP_URL_USERNAME
    return_to_login_url = game_view_url("pychronia_game-login", datamanager=dm)
    return_to_login_next_url = request.build_absolute_uri()
    # we do a HACK to deal with in-url usernames (except UNIVERSAL_URL_USERNAME username, which stays as is)
    return_to_login_next_url = return_to_login_next_url.replace("/%s/" % dm.user.username, "/%s/" % TEMP_URL_USERNAME)
    return_to_login_qs = urllib.urlencode(dict(next=return_to_login_next_url))
    return_to_login = HttpResponseRedirect("%s?%s" % (return_to_login_url, return_to_login_qs))

    assert urlresolvers.resolve(return_to_home_url)
    try:

        return caller(self, request, *args, **kwargs)

    except AccessDeniedError, e:

        if request.is_ajax():
            return HttpResponseForbidden(repr(e))

        if request.datamanager.user.is_impersonation:
            # Will mainly happen when we switch between two impersonations with different access rights, on a restricted page
            dm.user.add_warning(_("Currently impersonated user can't access view '%s'") % self.TITLE)
        else:
            dm.user.add_error(_("Access denied to page %s") % self.TITLE)
            dm.logger.warning("Access denied to page %s" % self.TITLE, exc_info=True)

        if not request.datamanager.user.impersonation_target and request.datamanager.user.is_anonymous:
            return return_to_login  # special case for REAL anonymous users
        return return_to_home

    except (GameError, POSError), e:

        if request.is_ajax():
            return HttpResponseBadRequest(repr(e))

        dm.logger.critical("Unexpected game error in %s" % self.NAME, exc_info=True)
        dm.user.add_error(_("An unexpected server error occurred, please retry (%s)") % (e if dm.is_master() else _(u"contact webmaster if it persists")))
        return return_to_home

    # else, we let 500 handler take are of all other (very abnormal) exceptions

    assert False







class ClassInstantiationProxy(object):
    """
    Stateless object which automatically instantiates and triggers its wrapped GameView class on call.
    Also forwards attribute retrievals.
    """
    def __init__(self, klass):
        self.klass = klass # important attribute
    def __getattr__(self, name):
        return getattr(self.klass, name) # useful for introspection of views
    def __call__(self, request, *args, **kwargs):
        return self.klass(request.datamanager)(request, *args, **kwargs) # we execute new instance of underlying class, without parameters
    def __str__(self):
        return "ClassInstantiationProxy around %s" % self.klass
    __repr__ = __str__



class GameViewMetaclass(type):
    """
    Metaclass automatically checking and registering the view in a global registry.
    """
    def __init__(NewClass, name, bases, new_dict):

        super(GameViewMetaclass, NewClass).__init__(name, bases, new_dict)

        if not NewClass.__name__.startswith("Abstract"):

            if __debug__:

                utilities.check_is_lazy_translation(NewClass.TITLE)
                if NewClass.ACCESS == UserAccess.authenticated:
                    assert NewClass.TITLE_FOR_MASTER is None or utilities.check_is_lazy_translation(NewClass.TITLE_FOR_MASTER)
                else:
                    assert NewClass.TITLE_FOR_MASTER is None # makes no sense if view for characters or for master only

                assert utilities.check_is_slug(NewClass.NAME)
                # assert NewClass.NAME.lower() == NewClass.NAME # FIXME, NOT YET ATM !!!

                assert NewClass.ACCESS in UserAccess.enum_values

                # Both can be True, in which case global-permission=True displays a non-clickable link in menu,
                # and character-permission=True then enables the menu link
                # However character-permission laways allows access=True even if global-permission=False
                assert NewClass.REQUIRES_CHARACTER_PERMISSION in (True, False)
                assert NewClass.REQUIRES_GLOBAL_PERMISSION in (True, False)

                assert NewClass.ALWAYS_ALLOW_POST in (True, False)
                for perm in NewClass.EXTRA_PERMISSIONS:
                    assert perm and perm.lower() == perm and " " not in perm

                if NewClass.ACCESS == UserAccess.master:
                    assert not NewClass.REQUIRES_CHARACTER_PERMISSION
                    assert not NewClass.REQUIRES_GLOBAL_PERMISSION
                elif NewClass.ACCESS in (UserAccess.authenticated, UserAccess.character):
                    pass # all is allowed
                elif NewClass.ACCESS == UserAccess.anonymous:
                    assert not NewClass.REQUIRES_CHARACTER_PERMISSION
                else:
                    raise NotImplementedError("Missing UserAccess case in GameView setup")

                if NewClass.TEMPLATE is not None:
                    pass  # cant' do that anymore due to new app initialization system: assert loader.get_template(NewClass.TEMPLATE)


                RESERVED_CALLBACK_NAMES = AbstractGameView.__dict__.keys()
                def _check_callback(callback):
                    ###print ("CALLBACK", callback)
                    assert getattr(NewClass, callback, None), callback
                    assert callback not in RESERVED_CALLBACK_NAMES, (callback, RESERVED_CALLBACK_NAMES)
                    assert not callback.startswith("_")


                def _check_action_registry(action_registry, form_class_required, allow_permission_requirement):
                    for (action_name, action_properties) in action_registry.items():
                        utilities.check_is_slug(action_name)
                        action_properties_reference = {
                            "title": Promise, # LAZILY translated string!!
                            "form_class": (types.NoneType, types.TypeType),
                            "callback": basestring,
                        }
                        utilities.check_dictionary_with_template(action_properties, action_properties_reference, strict=False)
                        _check_callback(action_properties["callback"])

                        action_properties.setdefault("requires_permission", None) # we COMPLETE the dict here!!

                        requires_permission = action_properties["requires_permission"]
                        if allow_permission_requirement:
                            if requires_permission:
                                assert requires_permission in NewClass.EXTRA_PERMISSIONS or requires_permission in GameDataManager.PERMISSIONS_REGISTRY
                            else:
                                pass # None or not present
                        else:
                            assert requires_permission is None

                        FormClass = action_properties["form_class"]
                        if form_class_required:
                            assert FormClass
                        if FormClass:
                            assert issubclass(FormClass, SimpleForm), FormClass.__mro__ # not necessarily AbstractGameForm - may be managed manually

                for_chars = (NewClass.ACCESS in (UserAccess.authenticated, UserAccess.character))
                _check_action_registry(NewClass.GAME_ACTIONS, form_class_required=False, allow_permission_requirement=for_chars) # can be directly called via ajax/custom forms

                _check_action_registry(NewClass.ADMIN_ACTIONS, form_class_required=True, allow_permission_requirement=False) # must be auto-exposed via forms


                game_form_classes = [props["form_class"] for props in NewClass.GAME_ACTIONS.values() if props["form_class"] is not None]
                utilities.check_no_duplicates(game_form_classes) # at the moment, forms recognize themselves the action, so they can't be reused in same view

                assert not (set(NewClass.GAME_ACTIONS) & set(NewClass.ADMIN_ACTIONS)), NewClass.__name__ # let's avoid ambiguities on action names: GAME or ADMIN only!

            GameDataManager.register_game_view(NewClass)


    @property
    def as_view(cls):
        """
        To be used in django urls conf ; similar to standard class-based views of django,
        except that a separate instance is created for each request!
        """
        if not hasattr(cls, "_instantiation_proxy"):
            cls._instantiation_proxy = ClassInstantiationProxy(cls)
        return cls._instantiation_proxy # ALWAYS THE SAME RETURNED




class SubmittedGameForm(object):
    """
    Simple container class.
    """
    def __init__(self, view_name, action_name, form_instance, action_successful):
        utilities.check_is_slug(action_name)
        assert action_successful in (True, False)
        self.view_name = view_name # useful for multi-view systems like admin widgets
        self.action_name = action_name
        self.form_instance = form_instance
        self.action_successful = action_successful




class AbstractGameView(object):
    """
    By default, concrete subclasses just need to implement the _process_standard_request() method 
    of that class, and they are then suitable to process multiple http requests related to multiple datamanagers,
    in a single thread (no concurrency).
    
    But special subclasses might break that genericity by binding the instance to a particular request/datamanager.
    """
    __metaclass__ = GameViewMetaclass

    TITLE = None # must be a ugettext_lazy() string
    TITLE_FOR_MASTER = None # must be a ugettext_lazy() string or None

    NAME = None # slug to be overridden, used as primary identifier

    GAME_ACTIONS = {} # dict mapping action identifiers to a dict of action properties (that might use action middlewares)
    ADMIN_ACTIONS = {} # idem, but reserved to admin (no middlewares), and form classes are mandatory here

    TEMPLATE = None # HTML template name, required when using default request handler
    ADMIN_TEMPLATE = "utilities/admin_form_widget.html" # TODO - template to render a single admin form, with notifications

    ACCESS = None # UserAccess entry
    EXTRA_PERMISSIONS = [] # list of extra permissions used by the view
    REQUIRES_GLOBAL_PERMISSION = True # True iff view needn't be activated by game master (constraint for non-master only, i.e anonymous and character users))
    REQUIRES_CHARACTER_PERMISSION = False # by default, a view is only globally switched on/off, with this, a character must ALSO be personally enabled by master

    ALWAYS_ALLOW_POST = False # True if we can post data to this view even when game/user is in read-only mode (eg. auth-related view)

    DISPLAY_STATIC_CONTENT = True # meant to be overridden per-instance (eg. for captchas)

    _ACTION_FIELD = "_action_" # for ajax and no-form request


    ## request and view params, set ONLY during a request processing ##
    request = None
    args = None
    kwargs = None
    ###############


    def __init__(self, datamanager, *args, **kwargs):
        self._inner_datamanager = datamanager
        # do NOT store datamanager.user, as it might change during execution!!!


    @property
    def datamanager(self):
        return self._inner_datamanager

    @property
    def logger(self):
        return self._inner_datamanager.logger

    @classmethod
    def get_access_permission_name(cls):
        assert cls.NAME
        assert cls.REQUIRES_CHARACTER_PERMISSION
        return "access_" + cls.NAME

    @classmethod
    def get_access_token(cls, datamanager):

        user = datamanager.user

        if ((cls.ACCESS == UserAccess.master and not user.is_master) or
            (cls.ACCESS == UserAccess.authenticated and not user.is_authenticated) or
            (cls.ACCESS == UserAccess.character and not user.is_character)):
            #print(">>>>>>>>>>", cls.ACCESS, "|", user.is_master, user.is_authenticated, user.is_character, user.username)
            return AccessResult.authentication_required  # that view is UNABLE to handle that kind of user!

        if user.is_master:
            return AccessResult.available  # game master does what he wants then!

        view_is_globally_available = True
        if cls.REQUIRES_GLOBAL_PERMISSION:
            if not datamanager.is_game_view_activated(cls.NAME):
                view_is_globally_available = False

        if cls.REQUIRES_CHARACTER_PERMISSION:
            assert cls.ACCESS in (UserAccess.character, UserAccess.authenticated)
            if user.has_permission(cls.get_access_permission_name()):
                return AccessResult.available  # OVERRIDE: even if not view_is_globally_available, this user has access then!
            elif view_is_globally_available:
                return AccessResult.permission_required  # thus menu entry will be disable but VISIBLE

        if not view_is_globally_available:
            return AccessResult.globally_forbidden # EVEN for game master ATM

        return AccessResult.available


    @classmethod
    def relevant_title(cls, datamanager):
        if datamanager.is_master() and cls.TITLE_FOR_MASTER:
            return cls.TITLE_FOR_MASTER
        return cls.TITLE

    def _check_writability(self):

        user = self.datamanager.user
        if self.request.POST and not self.datamanager.is_game_writable() and not self.ALWAYS_ALLOW_POST:
            self.request.POST.clear() # thanks to our middleware that made it mutable...
            self.request.method = "GET" # whooo ugly
            user.add_error(_("You are not allowed to submit changes to that page"))
            if self.request.is_ajax():
                self.logger.critical("Forbidden ajax POST request on non-writable game at url %s", self.request.get_full_path)
        assert (user.has_write_access and (user.is_master or self.datamanager.is_game_started())) or self.ALWAYS_ALLOW_POST or not self.request.POST


    def _check_standard_access(self):
        try:
            access_result = self.get_access_token(self.datamanager)

            if access_result == AccessResult.available:
                return
            elif access_result == AccessResult.permission_required:
                raise PermissionRequiredError(_("Access reserved to privileged members."))
            elif access_result == AccessResult.authentication_required:
                raise AuthenticationRequiredError(_("Authentication required.")) # could also mean a gamemaster tries to access a character-only section
            else:
                assert access_result == AccessResult.globally_forbidden
                raise AccessDeniedError(_("Access globally forbidden."))
            assert False
        except Exception, e:
            self.logger.error("check_standard_access failed: %r", e)
            raise


    def _check_admin_access(self):
        if not self.datamanager.user.is_master:
            raise AuthenticationRequiredError(_("Authentication required."))


    @staticmethod
    def _is_action_permitted_for_user(new_action_name, action_registry, user):
        """
        Currently, only checks personal permission for CHARACTERS in case
        this action requires one.
        """
        requires_permission = action_registry[new_action_name]["requires_permission"]
        if requires_permission:
            if not user.is_master:
                assert user.is_character # only other case where requires_permission can be set
                if not user.has_permission(requires_permission):
                    return False
                    # in any other case, we're good
        return True

    @classmethod
    def _common_instantiate_form(cls,
                                  new_action_name, # id of the form to be potentially instantiated
                                  hide_on_success=False, # should we return None if this form has just been submitted successfully?
                                  previous_form_data=None, # data about previously submitted form, if any
                                  initial_data=None,
                                  data=None, # submitted, bound data
                                  action_registry=None,
                                  user=None,
                                  form_initializer=None,
                                  propagate_errors=False,
                                  form_options=None):
        """
        *form_initializer* will be passed as 1st argument to the form. By default, it's the datamanager.
        
        Might raise UninstantiableFormError, if propagate_errors if True.
        
        Important: previous form is NOT necessarily of the same type as that of new_action_name.
        """
        form_options = form_options or {}
        assert action_registry
        assert user
        assert form_initializer

        if previous_form_data:
            preview_view_name = previous_form_data.view_name
            previous_action_name = previous_form_data.action_name
            previous_form_instance = previous_form_data.form_instance
            previous_action_successful = previous_form_data.action_successful
        else:
            preview_view_name = previous_action_name = previous_form_instance = previous_action_successful = None

        if not cls._is_action_permitted_for_user(new_action_name=new_action_name, action_registry=action_registry, user=user):
            if propagate_errors:
                raise UninstantiableFormError(_("This action requires personal permissions"))
            else:
                return None


        NewFormClass = action_registry[new_action_name]["form_class"]
        assert NewFormClass, new_action_name # important, not all actions have form classes available

        if __debug__:
            form_data = (previous_action_name, (previous_action_successful is not None))
            # we CAN have previous_form_instance is None and previous_action_successful == False, if form not instantiable
            if previous_action_successful: assert previous_form_instance
            assert all(form_data) or not any(form_data)

        if preview_view_name == cls.NAME and new_action_name == previous_action_name: # beware of preview_view_name!!
            if previous_form_instance:  assert previous_form_instance.__class__.__name__ == NewFormClass.__name__ # an action always uses same form class

            # this particular form has just been submitted
            if previous_action_successful:
                if hide_on_success:
                    return None
                else:
                    pass

            else:
                return previous_form_instance # atm we ALWAYS redisplay a failed form
        else:
            pass

        try:
            form = NewFormClass(form_initializer, data=data, initial=initial_data, **form_options)
        except UninstantiableFormError:
            if propagate_errors:
                raise
            form = None

        return form



    def _instantiate_game_form(self, *args, **all_params):
        return self._common_instantiate_form(*args,
                                             action_registry=self.GAME_ACTIONS,
                                             form_initializer=self.datamanager, #  this property might be overridden by subclasses
                                             user=self.datamanager.user,
                                             ** all_params)




    def _try_coercing_arguments_to_func(self, data, func):
        # FIXME - TEST THIS STUFF!!??
        try:
            relevant_args = utilities.adapt_parameters_to_func(data, func)
            return relevant_args
        except (TypeError, ValueError), e:
            self.logger.error("Wrong signature when calling %s : %s (exception is %r)", func.__name__, data, e)
            raise UsageError(_("Wrong arguments when calling method %s") % func.__name__)


    def _resolve_callback_callargs(self, callback_name, unfiltered_params):
        callback = getattr(self, callback_name) # MUST exist
        relevant_args = self._try_coercing_arguments_to_func(data=unfiltered_params, func=callback) # might raise UsageError
        return (callback, relevant_args)

    def _execute_game_action_callback(self, action_name, unfiltered_params):
        """
        Might raise any kind of exception. 
        
        Method to be overriden.
        """
        callback_name = self.GAME_ACTIONS[action_name]["callback"]
        (callback, relevant_args) = self._resolve_callback_callargs(callback_name=callback_name, unfiltered_params=unfiltered_params)
        res = callback(**relevant_args) # might fail
        return res


    @transaction_watcher # IMPORTANT, even for simple gameviews
    def execute_game_action_callback(self, action_name, unfiltered_params):
        if not self._is_action_permitted_for_user(new_action_name=action_name, action_registry=self.GAME_ACTIONS, user=self.datamanager.user):
            raise AbnormalUsageError(_("Forbidden action '%s' called by unauthorized user") % action_name) # it means we improperly exposed form/widget to call this action
        return self._execute_game_action_callback(action_name=action_name, unfiltered_params=unfiltered_params)



    def _try_processing_formless_game_action(self, data):
        """
        Raises AbnormalUsageError if action is not determined,
        else returns its result (or raises an action exception).
        """
        if __debug__: self.datamanager.notify_event("TRY_PROCESSING_FORMLESS_GAME_ACTION")

        data = utilities.sanitize_query_dict(data) # translates params to arrays, for example

        action_name = data.get(self._ACTION_FIELD)
        if not action_name or action_name not in self.GAME_ACTIONS:
            raise AbnormalUsageError(_("Abnormal action name: %(action_name)s (available: %(actions)r)") % SDICT(action_name=action_name, actions=self.GAME_ACTIONS.keys()))

        res = self.execute_game_action_callback(action_name=action_name, unfiltered_params=data)

        return res


    def _process_ajax_request(self):
        if __debug__: self.datamanager.notify_event("PROCESS_AJAX_REQUEST")
        # we let exceptions flow upto upper level handlers
        res = self._try_processing_formless_game_action(self.request.POST)
        response = json.dumps(res)
        return HttpResponse(response)


    def _do_process_form_submission(self, action_registry, action_name, unfiltered_data, execution_processor):
        if __debug__: self.datamanager.notify_event("DO_PROCESS_FORM_SUBMISSION")
        assert self.request.method == "POST"
        assert execution_processor._is_under_transaction_watcher

        user = self.datamanager.user
        res = dict(result=False, # by default
                   form_data=None)

        callback_name = action_registry[action_name]["callback"]
        FormClass = action_registry[action_name]["form_class"]
        assert FormClass.matches(unfiltered_data)

        action_successful = False
        try:
            bound_form = self._common_instantiate_form(new_action_name=action_name,
                                                       previous_form_data=None,
                                                       data=unfiltered_data,
                                                       action_registry=action_registry,
                                                       form_initializer=self.datamanager,
                                                       user=self.datamanager.user,
                                                       propagate_errors=True)
        except UninstantiableFormError:
            bound_form = None # the form correponding to data can't even be created, so POST data is necessarily invalid

        if bound_form and bound_form.is_valid():
            with action_failure_handler(self.request, success_message=None): # only for unhandled exceptions
                normalized_values = bound_form.get_normalized_values()
                self.logger.info("In _do_process_form_submission normalized_values: %r", normalized_values)
                success_message = execution_processor(action_name=action_name,
                                                      unfiltered_params=normalized_values)
                res["result"] = action_successful = True
                if isinstance(success_message, basestring) and success_message:
                    user.add_message(success_message)
                else:
                    self.logger.error("Action %s returned wrong success message: %r", callback_name, success_message)
                    user.add_message(_("Operation successful")) # default msg

        else:
            user.add_error(_("Submitted data is invalid")) # should be completed by form errors, if bound_form could be instantiated
        res["form_data"] = SubmittedGameForm(view_name=self.NAME,
                                             action_name=action_name, # same as action name, actually
                                             form_instance=bound_form,
                                             action_successful=action_successful)
        return res


    def _process_html_post_data(self):
        """
        Returns a dict with keys:
        
            - result (ternary, None means "no action done")
            - form_data (instance of SubmittedGameForm, or None)
        """
        assert not self.request.is_ajax()
        assert self.request.method == "POST"

        res = dict(result=None,
                   form_data=None)

        user = self.datamanager.user
        data = self.request.POST

        #self.logger.debug("Processing HTML POST data: %r", data)

        if data.get(self._ACTION_FIELD): # manually built form
            res["result"] = False # by default
            with action_failure_handler(self.request, success_message=None): # only for unhandled exceptions
                result = self._try_processing_formless_game_action(data)
                if isinstance(result, basestring) and result:
                    user.add_message(result) # since we're NOT in ajax here
                res["result"] = True

        else: # it must be a call using registered django newforms
            for (action_name, action_data) in self.GAME_ACTIONS.items():
                FormClass = action_data["form_class"] # MIGHT BE NONE
                if FormClass and FormClass.matches(data): # class method
                    res = self._do_process_form_submission(action_registry=self.GAME_ACTIONS,
                                                           action_name=action_name,
                                                           unfiltered_data=data,
                                                           execution_processor=self.execute_game_action_callback)
                    break # IMPORTANT
            else:
                user.add_error(_("Submitted form data hasn't been recognized"))
                self.logger.error("Unexpected form data sent to %s - %r" % (self.NAME, self.request.POST))

        assert set(res.keys()) == set("result form_data".split()), res
        return res


    def get_template_vars(self, previous_form_data=None):
        raise NotImplementedError("Unimplemented get_template_vars called in %s" % self)


    def _process_html_request(self):
        if __debug__: self.datamanager.notify_event("PROCESS_HTML_REQUEST")
        if self.request.method == "POST":
            res = self._process_html_post_data()
            action_success = res["result"] # can be None also if nothing processed
            previous_form_data = res["form_data"]
        else:
            action_success = None # unused ATM
            previous_form_data = None

        assert not previous_form_data or previous_form_data.action_successful == action_success # coherence

        if action_success and self._redirection_url:
            return redirect(self._redirection_url)  # optimization: we do it BEFORE get_template_vars()

        template_vars = self.get_template_vars(previous_form_data)

        assert isinstance(template_vars, collections.Mapping), template_vars

        response = render(self.request,
                          self.TEMPLATE,
                          template_vars)
        return response



    def _auto_process_request(self):
        #if not self.datamanager.player.has_permission(self.NAME): #TODO
        #    raise RuntimeError("Player has no permission to use ability")
        if self.request.is_ajax() or self.request.GET.get("is_ajax"):
            return self._process_ajax_request()
        else:
            return self._process_html_request()


    def _process_standard_request(self, request, *args, **kwargs):
        """
        Must return a valid http response.
        """
        return self._auto_process_request()


    def _setup_http_redirect_on_success(self, url):
        """
        For now, it's only taken intop account for NON-AJAX HTTP POST actions.
        """
        self._redirection_url = url


    def _before_request(self, request, *args, **kwargs):
        # we finish initializing the game view instance, with request-specific parameters
        assert request.datamanager == self._inner_datamanager # let's be coherent
        self.request = request
        self.args = args
        self.kwargs = kwargs
        self._redirection_url = None

        request.processed_view = self # needed for menu building and template context processor, later

    def _after_request(self):
        del self.request, self.args, self.kwargs, self._redirection_url # cleanup


    @transform_usage_error
    @readonly_method # we ensure all "actions" were committed
    def __call__(self, request, *args, **kwargs):
        """
        Do not override that method - too sensitive.
        """
        self._before_request(request, *args, **kwargs)
        try:

            self._check_standard_access() # crucial
            self._check_writability() # crucial

            if self.datamanager.is_game_writable():
                self.mark_view_as_accessed(self.datamanager) # must be BEFORE template processing

            response = self._process_standard_request(request, *args, **kwargs)
            return response

        finally:
            self._after_request()


    @readonly_method
    def get_game_actions_explanations(self):
        """
        Must return a list of tuples (action_title, explanations) 
        where explanations is a list of (per-middleware) lists of strings.
        """
        return []



    # Novelty tracking for gameviews #

    _game_view_novelty_category = "gameview"

    @classmethod
    def mark_view_as_accessed(cls, datamanager):
        return datamanager.access_novelty(item_key=cls.NAME, category=cls._game_view_novelty_category)

    @classmethod
    def has_user_accessed_view(cls, datamanager):
        return datamanager.has_accessed_novelty(item_key=cls.NAME, category=cls._game_view_novelty_category)




    ### Administration API ###


    def _instantiate_admin_form(self, *args, **all_params):
        return self._common_instantiate_form(*args,
                                             action_registry=self.ADMIN_ACTIONS,
                                             form_initializer=self.datamanager, # this property might be overridden by subclasses
                                             user=self.datamanager.user,
                                             ** all_params)


    @readonly_method
    def compute_admin_template_variables(self, action_name, previous_form_data=None):
        """
        Can be used both in and out of request processing.
        
        # FIXME TODO HANDLE UninstantiableForm error
        """
        form = self._instantiate_admin_form(new_action_name=action_name,
                                              hide_on_success=False,
                                              previous_form_data=previous_form_data,
                                              initial_data=None,)

        template_vars = dict(target_form_id=self.datamanager.build_admin_widget_identifier(self.__class__, action_name),
                             title=self.ADMIN_ACTIONS[action_name]["title"],
                             form=form) # BEWARE - form might be NONE here!
        return template_vars


    @transaction_watcher(always_writable=True)
    def _execute_admin_action_callback(self, action_name, unfiltered_params):
        """
        No action middlewares involved here, at the moment.
        
        Might raise any kind of exception.
        """
        assert self._is_action_permitted_for_user(new_action_name=action_name, action_registry=self.ADMIN_ACTIONS, user=self.datamanager.user) # of course...
        callback_name = self.ADMIN_ACTIONS[action_name]["callback"]
        (callback, relevant_args) = self._resolve_callback_callargs(callback_name=callback_name, unfiltered_params=unfiltered_params)
        res = callback(**relevant_args) # might fail
        return res


    @transaction_watcher
    @transform_usage_error
    def process_admin_request(self, request, action_name):
        """
        Used to process POST mini-forms from admin dashboard view.
        """
        assert action_name in self.ADMIN_ACTIONS # else big pb!

        self._before_request(request)
        try:

            self._check_admin_access() # crucial
            self._check_writability() # crucial

            data = request.POST

            if request.method == "POST":
                # this might add messages to current user #
                res = self._do_process_form_submission(action_registry=self.ADMIN_ACTIONS,
                                                       action_name=action_name,
                                                       unfiltered_data=data,
                                                       execution_processor=self._execute_admin_action_callback)

            else:
                res = dict(result=None,
                           form_data=None)
            """ ABORTED ATM - NO AJAX SUBMISSION
            success = res["result"] # UNUSED ATM - can be None also if nothing processed
            previous_form_data = res["form_data"]

            template_vars = self.compute_admin_template_variables(action_name=action_name, previous_form_data=previous_form_data)

            response = render(request,
                              self.ADMIN_TEMPLATE,
                              template_vars)
            """
            return res
        finally:
            self._after_request()


    @readonly_method
    def get_admin_summary_html(self):
        return self._get_admin_summary_html()

    def _get_admin_summary_html(self):
        """
        Override this utility to return an HTML block, which will be exposed in "admin info" special page.
        
        Must NOT rely on a self.request object to be present.
        """
        return None




def _normalize_view_access_parameters(access=_undefined,
                                      requires_character_permission=_undefined,
                                      requires_global_permission=_undefined,
                                      attach_to=_undefined):

    """
    Wraps a view into a system processing all kinds of authorization operations.
    
    *access* is a UserAccess value giving which kind of user has the right to access that view.
    
    *requires_character_permission* restricts access to specifically allowed users
    
    *requires_global_permission*: if True, the game master must globally enable the view
    
    *attach_to* is exclusive of other arguments, and duplicates the access permissions of the provided GameView.       
    """


    if attach_to is not _undefined:
        assert access is _undefined and requires_character_permission is _undefined and requires_global_permission is _undefined
        # other_game_view might itself be attached to another view, but it's OK
        access = attach_to.ACCESS
        requires_character_permission = attach_to.REQUIRES_CHARACTER_PERMISSION
        requires_global_permission = attach_to.REQUIRES_GLOBAL_PERMISSION
        # all checks have already been done on these values, theoretically

    else:
        access = access if access is not _undefined else UserAccess.master
        if requires_character_permission is _undefined:
            requires_character_permission = False
        else:
            pass # OK
        if requires_global_permission is _undefined:
            if access == UserAccess.master:
                requires_global_permission = False
            else:
                requires_global_permission = True  # by default, non-master views must be deactivable, even anonymous ones

    return dict(access=access,
                requires_character_permission=requires_character_permission,
                requires_global_permission=requires_global_permission)




def register_view(view_object=None,
                  access=_undefined,
                  requires_character_permission=_undefined,
                  requires_global_permission=_undefined,
                  always_allow_post=_undefined,
                  attach_to=_undefined,
                  title=None,
                  title_for_master=None,
                  view_name=None):
    """
    Helper allowing with or without-arguments decorator usage for GameView.
    
    Returns a CLASS or a METHOD, depending on the type of the wrapped object.
    """

    def _build_final_view_callable(real_view_object):

        final_view_name = str(view_name) if view_name else real_view_object.__name__

        local_attach_to = attach_to # tiny optimization

        if isinstance(real_view_object, type):

            assert issubclass(real_view_object, AbstractGameView)
            assert real_view_object.ACCESS
            assert all((val == _undefined) for val in (access, requires_character_permission, requires_global_permission, local_attach_to)) # these params must already exist as class attrs
            view_callable = real_view_object

        else:

            assert utilities.check_is_lazy_translation(title)
            assert inspect.isroutine(real_view_object) # not a class!

            if local_attach_to is not _undefined and not isinstance(local_attach_to, GameViewMetaclass):
                # we get back from proxy to AbstractGameView class
                local_attach_to = local_attach_to.klass
                assert issubclass(local_attach_to, AbstractGameView)

            normalized_access_args = _normalize_view_access_parameters(access=access,
                                                                       requires_character_permission=requires_character_permission,
                                                                       requires_global_permission=requires_global_permission,
                                                                       attach_to=local_attach_to)

            class_data = dict((key.upper(), value) for key, value in normalized_access_args.items()) # auto build access attributes
            class_data["TITLE"] = title
            class_data["TITLE_FOR_MASTER"] = title_for_master
            class_data["NAME"] = final_view_name
            if always_allow_post is not _undefined:
                class_data["ALWAYS_ALLOW_POST"] = always_allow_post # unaltered boolean
            class_data["_process_standard_request"] = staticmethod(real_view_object) # we install the real request handler, not expecting a "self"

            ###print ("BUILDING VIEW", real_view_object.__name__, class_data)
            # we build new GameView subclass on the fly
            KlassName = utilities.to_pascal_case(final_view_name)
            NewViewType = type(KlassName, (AbstractGameView,), class_data) # metaclass checks everything for us
            view_callable = NewViewType.as_view

        return view_callable # a class or method, depending on *real_view_object*

    if view_object:
        return _build_final_view_callable(view_object)
    else:
        return _build_final_view_callable # new decorator ready to be applied to a view function/type
    assert False

