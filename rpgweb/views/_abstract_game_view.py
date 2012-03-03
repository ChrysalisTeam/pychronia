# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


from django.http import Http404, HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden
from django.shortcuts import render_to_response
from django.template import RequestContext, loader

from ..datamanager import GameDataManager
from ..forms import AbstractGameForm
from rpgweb.common import *








class GameViewMetaclass(type):
    """
    Metaclass automatically checking and registering the view in a global registry.
    """ 
    def __init__(NewClass, name, bases, new_dict):
        
        super(GameViewMetaclass, NewClass).__init__(name, bases, new_dict)
        
        if not NewClass.__name__.startswith("Abstract"):

            if __debug__:

                RESERVED_NAMES = AbstractGameView.__dict__.keys()

                assert utilities.check_is_slug(NewClass.NAME)

                assert NewClass.ACCESS in UserAccess.enum_values
                assert isinstance(NewClass.PERMISSIONS,  (list, tuple))
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

                def _check_callback(name):
                    assert getattr(NewClass, callback)
                    assert callback not in RESERVED_NAMES
                    assert not callback.startswith("_")

                for (form_name, (FormClass, callback)) in NewClass.GAME_FORMS.items():
                    assert issubclass(FormClass, AbstractGameForm)
                    _check_callback(callback)
                for (action_name, callback) in NewClass.ACTIONS.items():
                    _check_callback(callback)
                    
            GameDataManager.register_game_view(NewClass)
            
    



class SubmittedGameForm:
    
    def __init__(self, form_name, form_instance, form_successful):
        utilities.check_is_slug(form_name)
        assert form_successful in (True, False)
        self.form_name = form_name
        self.form_instance = form_instance
        self.form_successful = form_successful




class AbstractGameView(object):
    """
    By default, concrete subclasses just need to implement the _process_request() method 
    of that class, and they are then suitable to process multiple http requests related to multiple datamanagers,
    in a single thread (no concurrency).
    
    But special subclasses might break that genericity by binding the instance to a particular request/datamanager.
    """
    __metaclass__ = GameViewMetaclass

    NAME = None # slug to be overridden, used as primary identifier

    GAME_FORMS = {} # dict mapping form identifiers to tuples (AbstractGameForm subclass, processing method name)
    ACTIONS = {} # dict mapping action identifiers to processing method names (for ajax calls or custom forms)
    
    TEMPLATE = None # HTML template name, required when using default request handler

    ACCESS = None # UserAccess entry
    PERMISSIONS = [] # list of required permission names, only used for character access    
    ALWAYS_AVAILABLE = None # True iff view can't be globally hidden by game master

    _action_field = "_action_" # for ajax and no-form request

    logger = logging.getLogger("views")


    def __init__(self, *args, **kwargs):
        pass # we ignore any argument
    
    
    @classmethod
    def get_access_token(cls, request):
        
        # TODO - check POST write permission too!!!
        
        user = request.datamanager.user
        
        if not cls.ALWAYS_AVAILABLE:
            pass # TODO HERE CHECK THAT THE VIEW IS WELL ACTIVATED BY THE GAME MASTER, if not gamemaster logged
            # TODO return AccessResult.globally_forbidden
        
        if ((cls.ACCESS == UserAccess.master and not user.is_master) or
            (cls.ACCESS == UserAccess.authenticated and not user.is_authenticated) or
            (cls.ACCESS == UserAccess.character and not user.is_character)):
            return AccessResult.authentication_required

        if cls.PERMISSIONS:
            assert cls.ACCESS in (UserAccess.character, UserAccess.authenticated)
            if user.is_character: # game master does what he wants
                for permission in cls.PERMISSIONS:
                    if not user.has_permission(permission):
                        return AccessResult.permission_required 
            
        return AccessResult.available
    
    
    def _check_access(self, request):
       
        user = request.datamanager.user
        access_result = self.get_access_token(request)
        
        if access_result == AccessResult.available:
            return
        elif access_result == AccessResult.permission_required:
            raise PermissionRequiredError(_("Access reserved to privileged members."))
        elif access_result == AccessResult.authentication_required:
            raise AuthenticationRequiredError(_("Authentication required.")) # could also mean a gamemaster tries to access a character-only section
        else:
            assert access_result == AccessResult.globally_forbidden
            raise AccessDeniedError(_("Access forbidden."))
        assert False
        
    
    @classmethod
    def _instantiate_form(cls,
                          datamanager,
                          new_form_name, # id of the form to be potentially instantiated
                          hide_on_success=False, # should we return None if this form has just been submitted successfully?
                          previous_form_data=None, # data about previously submitted form, if any
                          initial_data=None):
        assert datamanager is None or datamanager # some forms don't neeed a valid datamanager
        
        if previous_form_data:
            previous_form_name = previous_form_data.form_name
            previous_form_instance = previous_form_data.form_instance
            previous_form_successful = previous_form_data.form_successful
        else:
            previous_form_name = previous_form_instance = previous_form_successful = None
        
        NewFormClass = cls.FORMS[new_form_name][0]

        if __debug__:
            form_data = (previous_form_name, previous_form_instance, (previous_form_successful is not None))
            assert all(form_data) or not any(form_data)

        if new_form_name == previous_form_name:
            # this particular form has just been submitted
            if previous_form_successful:
                if hide_on_success:
                    return None
                else:
                    pass

            else:
                return previous_form_instance # atm we ALWAYS redisplay a failed form
        else:
            pass

        form = NewFormClass(datamanager, initial=initial_data)

        return form



    def _try_processing_action(self, data):
        func = getattr(self, self.ACTIONS[data[self._action_field]])
        relevant_args = utilities.adapt_parameters_to_func(data, func)
        res = func(**relevant_args)
        return res

    def _process_ajax_request(self, data):
        res = self._try_processing_action(data) # we let exceptions flow atm
        return HttpResponse(res)

    def _process_post_data(self, request):
        """
        Returns a dict with keys:
        
            - result (ternary, None means "no action done")
            - form_data (instance of SubmittedGameForm, or None)
        """
        res = dict(result = None,
                   form_data = None)
        
        if request.method != "POST":
            return res
        
        user = request.datamanager.user
        data = request.POST

        if data.get("_action_"): # manually built form
            with action_failure_handler(request, success_message=None): # only for unhandled exceptions
                self._try_processing_action(data)
                dict["result"] = True
            dict["result"] = False
        
        else: # it must be a call using django newforms
            for (form_name, (FormClass, action_name)) in self.GAME_FORMS.items():
                if FormClass.matches(data): # class method
                    bound_form = FormClass(self._datamanager, data=data)
                    form_successful = False
                    if bound_form.is_valid():
                        with action_failure_handler(request, success_message=None): # only for unhandled exceptions
                            action = getattr(self, action_name)

                            relevant_args = utilities.adapt_parameters_to_func(bound_form.get_normalized_values(), action)
                            success_message = action(**relevant_args)

                            form_successful = True
                            if not isinstance(success_message, basestring):
                                logging.error("Action %s returned wrong success message: %r", action_name, success_message)
                                user.add_message(_("Operation successful")) # default msg
                            else:
                                user.add_message(success_message)
                    else:
                        user.add_error(_("Submitted data is invalid"))
                    res["form_data"] = SubmittedGameForm(form_name=form_name,
                                                           form_instance=bound_form,
                                                           form_successful=form_successful)
                    break # IMPORTANT
            else:
                user.add_error(_("Submitted form data hasn't been recognized"))
                logging.error("Unexpected form data sent to %s - %r" % (self.NAME, request.POST))
    
        return res


    def get_template_vars(self, previous_form_data=None):
        raise NotImplementedError("Unimplemented get_template_vars called in %s" % self)
    
    
    def _process_html_request(self, request):

        res = self._process_post_data(request)
        
        success = res["result"] # can be None if nothing processed
        previous_form_data = res["form_data"]
        
        template_vars = self.get_template_vars(previous_form_data)

        assert isinstance(template_vars, collections.Mapping), template_vars

        response = render_to_response(self.TEMPLATE,
                                      template_vars,
                                      context_instance=RequestContext(request))
        return response


    def _auto_process_request(self, request):
        #if not self.datamanager.player.has_permission(self.NAME): #TODO
        #    raise RuntimeError("Player has no permission to use ability")

        if request.is_ajax() or request.REQUEST.get(self._action_field):
            return self._process_ajax_request(request.REQUEST)
        else:
            return self._process_html_request(request)    
    
     
    def _process_request(self, request, *args, **kwargs):
        raise NotImplementedError("_process_request must be implemented by AbstractGameView subclass")
    
    
    def __call__(self, request, *args, **kwargs):
        
        try:
            
            self._check_access(request) # crucial
            
            return self._process_request(request, *args, **kwargs)
        
        except AuthenticationRequiredError, e:
            print("<<<", e)
            # TODO - 
            # uses HTTP code for TEMPORARY redirection
            return HttpResponseRedirect(reverse("rpgweb.views.login", kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))
        except AccessDeniedError, e:
            print("<<<", e)
            # even permission errors are treated like base class erors ATM
            return HttpResponseForbidden(_("Access denied")) # TODO FIXME - provide a proper template and message !!
        except:
            raise # we let 500 handler take are of all other (very abnormal) exceptions
    





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
            if access == UserAccess.master:
                always_available = True 
            else:
                always_available = False  # by default, non-master views must be deactivable
    
    return dict(access=access,
                permissions=permissions,
                always_available=always_available)
                

import django.views.generic  
class ClassInstantiationProxy(object):
    """
    Stateless object which automatically instantiates the targeted game view type on access
    """
    def __init__(self, klass):
        self._klass = klass
    def __getattr__(self, name):
        return getattr(self._klass, name) # useful for introspection of views                
    def __call__(self, request, *args, **kwargs):
        return self._klass(request.datamanager, *args, **kwargs)(request, *args, **kwargs) # we execute new instance of underlying class
    def __str__(self):
        return "ClassInstantiationProxy around %s" % self._klass
    __repr__ = __str__
    
    
def register_view(view_object=None, 
                  access=_undefined,
                  permissions=_undefined, 
                  always_available=_undefined,
                  attach_to=_undefined):
    """
    Helper allowing with or without-arguments decorator usage for GameView.
    """
    
    def _build_final_view_callable(real_view_object):
        
        if not isinstance(real_view_object, type):
            
            assert isinstance(real_view_object, collections.Callable)
    
            normalized_access_args = _normalize_view_access_parameters(access=access,
                                                                       permissions=permissions,
                                                                       always_available=always_available,
                                                                       attach_to=attach_to)
            KlassName = utilities.to_snake_case(real_view_object.__name__)
            class_data = dict((key.upper(), value) for key, value in normalized_access_args.items())
            class_data["NAME"] = KlassName
            class_data["_process_request"] = staticmethod(real_view_object) # we install the real request handler, not expecting a "self"
            
            # we build new GameView subclass on the fly
            NewViewType = type(KlassName, (AbstractGameView,), class_data)
    
            
        else:
            assert all(val == _undefined for val in (access, permissions, always_available, attach_to)) # these params must already exist as class attrs
            NewViewType = real_view_object
        
        return ClassInstantiationProxy(NewViewType)
    
    if view_object: 
        return _build_final_view_callable(view_object)
    return _build_final_view_callable # new decorator ready to be applied to a view function/type

