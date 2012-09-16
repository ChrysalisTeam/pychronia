# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


from rpgweb.common import *
from rpgweb.abilities._abstract_ability import AbstractAbility
from rpgweb.views._abstract_game_view import register_view
from rpgweb.abilities._action_middlewares import with_action_middlewares
from rpgweb.forms import AbstractGameForm
from rpgweb.datamanager.datamanager_tools import transaction_watcher


 

class DummyForm(AbstractGameForm):
    use_gems = forms.ChoiceField(label=_("Use_gems"), choices=[123, 122])
    def __init__(self, ability, *args, **kwargs):
        super(DummyForm, self).__init__(ability, *args, **kwargs)
        self.fields["target_item"] = forms.ChoiceField(label=_("Object"), choices=["one", "two"])
        self.fields["transcription"] = forms.CharField(label=_("Transcription"), widget=forms.Textarea(attrs={'rows': '5', 'cols':'30'}))



@register_view
class DummyTestAbility(AbstractAbility):

    NAME = "dummy_ability"

    ACTIONS = dict(middleware_wrapped_callable1="non_middleware_action_callable") # we check that this name doesnt affect middlwares
    GAME_FORMS = {"middleware_wrapped_callable1": (DummyForm, "non_middleware_action_callable")} # neither does this one
    
    TEMPLATE = "base_main.html" # must exist
    ACCESS = UserAccess.character
    PERMISSIONS = [] 
    ALWAYS_AVAILABLE = False 

    #def __init__(self, *args, **kwargs):
    #    super(DummyTestAbility, self).__init__(*args, **kwargs)
        

    def get_template_vars(self, previous_form_data=None):
        return {'page_title': "hello",}
        
    @classmethod
    def _setup_ability_settings(cls, settings):
        settings.setdefault("myvalue", "True")
        
    def _setup_private_ability_data(self, private_data):
        pass

    def _check_data_sanity(self, strict=False):
        settings = self.settings
    
    
    # test utilities
    
    @transaction_watcher
    def reset_test_settings(self, action_name, middleware_class, new_settings):
        # we activate the middleware if not yet there
        self.settings["middlewares"].setdefault(action_name, PersistentDict())
        middleware_settings = self.settings["middlewares"][action_name].setdefault(middleware_class.__name__, PersistentDict())
        assert middleware_settings is self.get_middleware_settings(action_name, middleware_class)
        middleware_settings.clear()
        middleware_settings.update(new_settings)
    
    @transaction_watcher
    def reset_test_data(self, action_name, middleware_class, new_data):
        middleware_settings = self.get_private_middleware_data(action_name, middleware_class, create_if_unexisting=True)
        middleware_settings.clear()
        middleware_settings.update(new_data)
    
        
    @transaction_watcher
    def non_middleware_action_callable(self, use_gems):
        self.notify_event("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE")
        return 23
    
    @transaction_watcher # must be on the OUTSIDE
    @with_action_middlewares("middleware_wrapped")
    def middleware_wrapped_callable1(self, use_gems):
        self.notify_event("INSIDE_MIDDLEWARE_WRAPPED1")
        return 18277
    
    @transaction_watcher # must be on the OUTSIDE
    @with_action_middlewares("middleware_wrapped")
    def middleware_wrapped_callable2(self, my_arg):
        self.notify_event("INSIDE_MIDDLEWARE_WRAPPED2")       
        return True
        
    @transaction_watcher # must be on the OUTSIDE
    @with_action_middlewares("middleware_wrapped_other_action")
    def middleware_wrapped_other_action(self, my_arg):
        self.notify_event("INSIDE_MIDDLEWARE_WRAPPED2")       
        return True    
        
        