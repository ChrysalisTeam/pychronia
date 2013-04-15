# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.common import _undefined # for static checker...
import json
from django.http import Http404, HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden, HttpResponseBadRequest
from django.template import loader

from ..datamanager import GameDataManager
from .abstract_form import AbstractGameForm, UninstantiableFormError
from .datamanager_tools import transaction_watcher, readonly_method
from django.forms import Form
from django.utils.functional import Promise



@decorator
def transform_usage_error(caller, self, *args, **kwargs):
    """
    Can be used for both html and ajax requests, so only 'error' HTTP codes should be returned
    if an exception is encountered.
    """
    try:

        return caller(self, *args, **kwargs)

    except AccessDeniedError, e:

            # TODO - test all these pages, in particular impersonation case !!!

            if self.datamanager.user.is_impersonation:
                # Will mainly happen when we switch between two impersonations with different access rights, on a restricted page
                self.datamanager.user.add_error(_("Currently impersonated user can't access view %s") % self.NAME)
                return HttpResponseRedirect(reverse("rpgweb.views.homepage"))

            if isinstance(e, AuthenticationRequiredError):
                # uses HTTP code for TEMPORARY redirection
                self.datamanager.user.add_error(_("Access denied to page %s") % self.NAME)
                return HttpResponseRedirect(reverse("rpgweb.views.login", kwargs=dict(game_instance_id=self.datamanager.game_instance_id)))
            else:
                # even permission errors are treated like base class AccessDeniedError ATM
                return HttpResponseForbidden(_("Access denied")) # TODO FIXME - provide a proper template and message !!

    except GameError, e:
        #print("|||||||||||||||||||", repr(e))
        traceback.print_exc()
        return HttpResponseBadRequest(repr(e))

    except Exception:
        raise # we let 500 handler take are of all other (very abnormal) exceptions (unhandled UsageError or others)






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

                assert NewClass.TITLE
                assert isinstance(NewClass.TITLE, Promise)

                assert utilities.check_is_slug(NewClass.NAME)
                # assert NewClass.NAME.lower() == NewClass.NAME # FIXME, NOT YET ATM !!!

                assert NewClass.ACCESS in UserAccess.enum_values
                assert isinstance(NewClass.PERMISSIONS, (list, tuple)) # not a string!!
                assert NewClass.ALWAYS_AVAILABLE in (True, False)

                if NewClass.ACCESS == UserAccess.master:
                    assert not NewClass.PERMISSIONS
                    assert NewClass.ALWAYS_AVAILABLE
                elif NewClass.ACCESS in (UserAccess.authenticated, UserAccess.character):
                    pass # all is allowed
                elif NewClass.ACCESS == UserAccess.anonymous:
                    assert not NewClass.PERMISSIONS
                else:
                    raise NotImplementedError("Missing UserAccess case in GameView setup")

                if NewClass.TEMPLATE is not None:
                    assert loader.get_template(NewClass.TEMPLATE)


                RESERVED_CALLBACK_NAMES = AbstractGameView.__dict__.keys()
                def _check_callback(callback):
                    ###print ("CALLBACK", callback)
                    assert getattr(NewClass, callback, None), callback
                    assert callback not in RESERVED_CALLBACK_NAMES, (callback, RESERVED_CALLBACK_NAMES)
                    assert not callback.startswith("_")


                def _check_action_registry(action_registry, form_class_required):
                    for (action_name, action_properties) in action_registry.items():
                        utilities.check_is_slug(action_name)
                        action_properties_reference = {
                            "title": Promise, # LAZILY translated string!!
                            "form_class": (types.NoneType, types.TypeType),
                            "callback": basestring,
                        }
                        utilities.check_dictionary_with_template(action_properties, action_properties_reference)
                        _check_callback(action_properties["callback"])

                        FormClass = action_properties["form_class"]
                        if form_class_required:
                            assert FormClass
                        if FormClass:
                            assert issubclass(FormClass, Form) # not necessarily AbstractGameForm - may be managed manually

                _check_action_registry(NewClass.GAME_ACTIONS, form_class_required=False) # can be directly called via ajax/custom forms
                _check_action_registry(NewClass.ADMIN_ACTIONS, form_class_required=True) # must be auto-exposed via forms

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
        return ClassInstantiationProxy(cls)




class SubmittedGameForm:
    """
    Simple container class.
    """
    def __init__(self, action_name, form_instance, action_successful):
        utilities.check_is_slug(action_name)
        assert action_successful in (True, False)
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

    TITLE = None # must be a _lazy() string

    NAME = None # slug to be overridden, used as primary identifier

    GAME_ACTIONS = {} # dict mapping action identifiers to a dict of action properties (that might use action middlewares)
    ADMIN_ACTIONS = {} # idem, but reserved to admin (no middlewares), and form classes are mandatory here

    TEMPLATE = None # HTML template name, required when using default request handler
    ADMIN_TEMPLATE = "utilities/admin_form_widget.html" # TODO - template to render a single admin form, with notifications


    ACCESS = None # UserAccess entry
    PERMISSIONS = [] # list of required permission names, only used for character access
    ALWAYS_AVAILABLE = False # True iff view can't be globally hidden by game master, for players

    _ACTION_FIELD = "_action_" # for ajax and no-form request

    logger = logging.getLogger("views")


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

    @classmethod
    def get_access_token(cls, datamanager):

        # TODO - check POST write permission too!!!

        user = datamanager.user

        if not cls.ALWAYS_AVAILABLE:
            if not datamanager.is_game_view_activated(cls.NAME):
                #print (">>>>>", cls.NAME, "-", datamanager.get_activated_game_views())
                return AccessResult.globally_forbidden

        if ((cls.ACCESS == UserAccess.master and not user.is_master) or
            (cls.ACCESS == UserAccess.authenticated and not user.is_authenticated) or
            (cls.ACCESS == UserAccess.character and not user.is_character)):
            #print(">>>>>>>>>>", cls.ACCESS, "|", user.is_master, user.is_authenticated, user.is_character, user.username)
            return AccessResult.authentication_required

        if cls.PERMISSIONS:
            assert cls.ACCESS in (UserAccess.character, UserAccess.authenticated)
            if user.is_character: # game master does what he wants
                for permission in cls.PERMISSIONS:
                    if not user.has_permission(permission):
                        return AccessResult.permission_required

        return AccessResult.available



    def _check_writability(self):

        user = self.datamanager.user
        if self.request.POST and not user.has_write_access:
            self.request.POST.clear() # thanks to our middleware that made it mutable...
            user.add_error(_("You are not allowed to submit changes to that page"))
        assert user.has_write_access or not self.request.POST


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
    def _common_instantiate_form(new_action_name, # id of the form to be potentially instantiated
                                  hide_on_success=False, # should we return None if this form has just been submitted successfully?
                                  previous_form_data=None, # data about previously submitted form, if any
                                  initial_data=None,
                                  action_registry=None,
                                  form_initializer=None,
                                  propagate_errors=False,
                                  **form_options):
        """
        *form_initializer* will be passed as 1st argument to the form. By default, it's the datamanager.
        
        Might raise UninstantiableFormError, if propagate_errors if True.
        
        Important: previous form is NOT necessarily of the same type as that of new_action_name.
        """
        form_options = form_options or {}
        assert action_registry
        assert form_initializer

        if previous_form_data:
            previous_action_name = previous_form_data.action_name
            previous_form_instance = previous_form_data.form_instance
            previous_action_successful = previous_form_data.action_successful
        else:
            previous_action_name = previous_form_instance = previous_action_successful = None

        NewFormClass = action_registry[new_action_name]["form_class"]
        assert NewFormClass, new_action_name # important, not all actions have form classes available

        if __debug__:
            form_data = (previous_action_name, (previous_action_successful is not None))
            # we CAN have previous_form_instance is None and previous_action_successful == False, if form not instantiable
            if previous_action_successful: assert previous_form_instance
            assert all(form_data) or not any(form_data)

        if new_action_name == previous_action_name:
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
            form = NewFormClass(form_initializer, initial=initial_data, **form_options)
        except UninstantiableFormError:
            if propagate_errors:
                raise
            form = None

        return form



    def _instantiate_game_form(self, *args, **all_params):
        return self._common_instantiate_form(*args,
                                             action_registry=self.GAME_ACTIONS,
                                             form_initializer=self.datamanager, #  this property might be overridden by subclasses
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
        """
        callback_name = self.GAME_ACTIONS[action_name]["callback"]
        (callback, relevant_args) = self._resolve_callback_callargs(callback_name=callback_name, unfiltered_params=unfiltered_params)
        res = callback(**relevant_args) # might fail
        return res

    @transaction_watcher
    def execute_game_action_callback(self, action_name, unfiltered_params):
        """Public interface, just for transaction watching in tests atm..."""
        return self._execute_game_action_callback(action_name=action_name,
                                                 unfiltered_params=unfiltered_params)


    def _try_processing_formless_game_action(self, data):
        """
        Raises AbnormalUsageError if action is not determined,
        else returns its result (or raises an action exception).
        """
        if __debug__: self.datamanager.notify_event("TRY_PROCESSING_FORMLESS_GAME_ACTION")

        data = utilities.sanitize_query_dict(data) # translates params to arrays, for example

        action_name = data.get(self._ACTION_FIELD)
        if not action_name or action_name not in self.GAME_ACTIONS:
            raise AbnormalUsageError(_("Abnormal action name: %s (available: %r)") % (action_name, self.GAME_ACTIONS.keys()))

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

        user = self.datamanager.user
        res = dict(result=False, # by default
                   form_data=None)

        callback_name = action_registry[action_name]["callback"]
        FormClass = action_registry[action_name]["form_class"]
        assert FormClass.matches(unfiltered_data)

        action_successful = False
        try:
            bound_form = FormClass(self.datamanager, data=unfiltered_data)
        except UninstantiableFormError:
            bound_form = None # the form correponding to data can't even be cerated, so POST data is necessarily invalid

        if bound_form and bound_form.is_valid():
            with action_failure_handler(self.request, success_message=None): # only for unhandled exceptions
                success_message = execution_processor(action_name=action_name,
                                                      unfiltered_params=bound_form.get_normalized_values())
                res["result"] = action_successful = True
                if isinstance(success_message, basestring) and success_message:
                    user.add_message(success_message)
                else:
                    self.logger.error("Action %s returned wrong success message: %r", callback_name, success_message)
                    user.add_message(_("Operation successful")) # default msg

        else:
            user.add_error(_("Submitted data is invalid")) # should be completed by form errors, if bound_form could be instantiated
        res["form_data"] = SubmittedGameForm(action_name=action_name, # same as action name, actually
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
                logging.error("Unexpected form data sent to %s - %r" % (self.NAME, self.request.POST))

        assert set(res.keys()) == set("result form_data".split()), res
        return res


    def get_template_vars(self, previous_form_data=None):
        raise NotImplementedError("Unimplemented get_template_vars called in %s" % self)


    def _process_html_request(self):
        if __debug__: self.datamanager.notify_event("PROCESS_HTML_REQUEST")
        if self.request.method == "POST":
            res = self._process_html_post_data()
            success = res["result"] # can be None also if nothing processed
            previous_form_data = res["form_data"]
        else:
            success = None # unused ATM
            previous_form_data = None

        assert not previous_form_data or previous_form_data.action_successful == success # coherency

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


    def _pre_request(self, request, *args, **kwargs):
        # we finish initializing the game view instance, with request-specific parameters
        assert request.datamanager == self._inner_datamanager # let's be coherent
        self.request = request
        self.args = args
        self.kwargs = kwargs

    def _post_request(self):
        del self.request, self.args, self.kwargs # cleanup


    @transform_usage_error
    @transaction_watcher
    def __call__(self, request, *args, **kwargs):
        """
        Do not override that method - too sensitive.
        """
        self._pre_request(request, *args, **kwargs)
        try:
            self._check_writability() # crucial
            self._check_standard_access() # crucial

            response = self._process_standard_request(request, *args, **kwargs)
            self.mark_view_as_accessed(self.datamanager) # no errors -> we mark view as "read"
            return response

        finally:
            self._post_request()


    @readonly_method
    def get_game_actions_explanations(self):
        """
        Must return a tuple (action_title, explanations) 
        where explanation is a list of (per-middleware) lists of strings.
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


    def _execute_admin_action_callback(self, action_name, unfiltered_params):
        """
        No action middlewares involved here, at the moment.
        
        Might raise any kind of exception.
        """
        callback_name = self.ADMIN_ACTIONS[action_name]["callback"]
        (callback, relevant_args) = self._resolve_callback_callargs(callback_name=callback_name, unfiltered_params=unfiltered_params)
        res = callback(**relevant_args) # might fail
        return res


    @transaction_watcher
    @transform_usage_error
    def process_admin_request(self, request, action_name):

        assert action_name in self.ADMIN_ACTIONS # else big pb!

        self._pre_request(request)
        try:
            self._check_writability() # crucial
            self._check_admin_access() # crucial

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
            self._post_request()




def _normalize_view_access_parameters(access=_undefined,
                                      permissions=_undefined,
                                      always_available=_undefined,
                                      attach_to=_undefined):

    """
    Wraps a view into a system processing all kinds of authorization operations.
    
    *access* is a UserAccess value giving which kind of user has the right to access that view.
    
    *permissions* only apply to users loged-in as characters, and asks them for specific permissions
    
    *always_available* makes the view always available to user having proper permissions, i.e the game master 
    can't globally enable/disable it.
    
    *attach_to* is exclusive of other arguments, and duplicates the permissions of the provided GameView.       
    """


    if attach_to is not _undefined:
        assert access is _undefined and permissions is _undefined and always_available is _undefined
        # other_game_view might itself be attached to another view, but it's OK
        access = attach_to.ACCESS
        permissions = attach_to.PERMISSIONS
        always_available = attach_to.ALWAYS_AVAILABLE
        # all checks have already been done on these values, theoretically

    else:
        access = access if access is not _undefined else UserAccess.master
        if permissions is _undefined:
            permissions = []
        elif isinstance(permissions, basestring):
            permissions = [permissions]
        else:
            pass # OK
        if always_available is _undefined:
            if access in UserAccess.master:
                always_available = True
            else:
                always_available = False  # by default, non-master views must be deactivable, even anonymous ones

    return dict(access=access,
                permissions=permissions,
                always_available=always_available)




def register_view(view_object=None,
                  access=_undefined,
                  permissions=_undefined,
                  always_available=_undefined,
                  attach_to=_undefined,
                  title=None):
    """
    Helper allowing with or without-arguments decorator usage for GameView.
    
    Returns a CLASS or a METHOD, depending on the type of the wrapped object.
    """

    def _build_final_view_callable(real_view_object):

        local_attach_to = attach_to # tiny optimization

        if isinstance(real_view_object, type):

            assert issubclass(real_view_object, AbstractGameView)
            assert real_view_object.ACCESS
            assert all((val == _undefined) for val in (access, permissions, always_available, local_attach_to)) # these params must already exist as class attrs
            view_callable = real_view_object

        else:

            assert title and isinstance(title, Promise)
            assert inspect.isroutine(real_view_object) # not a class!

            if local_attach_to is not _undefined and not isinstance(local_attach_to, GameViewMetaclass):
                # we get back from proxy to AbstractGameView class
                local_attach_to = local_attach_to.klass
                assert issubclass(local_attach_to, AbstractGameView)


            normalized_access_args = _normalize_view_access_parameters(access=access,
                                                                       permissions=permissions,
                                                                       always_available=always_available,
                                                                       attach_to=local_attach_to)

            class_data = dict((key.upper(), value) for key, value in normalized_access_args.items())
            class_data["TITLE"] = title
            class_data["NAME"] = real_view_object.__name__
            class_data["_process_standard_request"] = staticmethod(real_view_object) # we install the real request handler, not expecting a "self"

            # we build new GameView subclass on the fly
            KlassName = utilities.to_pascal_case(real_view_object.__name__)
            NewViewType = type(KlassName, (AbstractGameView,), class_data) # metaclass checks everything for us
            view_callable = NewViewType.as_view

        return view_callable # a class or method, depending on *real_view_object*

    if view_object:
        return _build_final_view_callable(view_object)
    else:
        return _build_final_view_callable # new decorator ready to be applied to a view function/type
    assert False

