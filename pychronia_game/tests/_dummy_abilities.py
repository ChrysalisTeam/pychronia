# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django import forms

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_ability import AbstractAbility
from pychronia_game.datamanager.abstract_game_view import register_view
from pychronia_game.forms import AbstractGameForm, MoneyTransferForm
from pychronia_game.datamanager.datamanager_tools import transaction_watcher




class DummyForm(AbstractGameForm):
    use_gems = forms.ChoiceField(label=ugettext_lazy("Use_gems"), choices=[123, 122])
    def __init__(self, ability, *args, **kwargs):
        super(DummyForm, self).__init__(ability, *args, **kwargs)
        self.fields["target_item"] = forms.ChoiceField(label=_("Object"), choices=["one", "two"])
        self.fields["transcription"] = forms.CharField(label=_("Transcription"), widget=forms.Textarea(attrs={'rows': '5', 'cols':'30'}))


class DummyFormOther(AbstractGameForm):
    my_arg = forms.CharField()


def with_enforced_action_middlewares(action_name):
    """
    Apply this decorator to tested actions, so that they get automatically processed
    through action middlewares.
    """
    @decorator # IMPORTANT - keep same signature so that adapt_parameters_to_func() works
    def _execute_with_middlewares(method, self, *args, **kwargs):
        assert not getattr(method, "_is_under_transaction_watcher", None) or getattr(method, "_is_under_readonly_method", None) # session management must be on TOP of decorators' stack
        method = method.__get__(self) # we transform into bound method, to mimic real cases
        return self._execute_game_action_with_middlewares(action_name, method, *args, **kwargs)
    return _execute_with_middlewares




@register_view
class DummyTestAbility(AbstractAbility):

    TITLE = ugettext_lazy("Dummy Ability")
    NAME = "dummy_ability"

    # BEWARE - we cheat to test action middlewares, using with_enforced_action_middlewares() system
    GAME_ACTIONS = dict(non_middleware_action_callable=dict(title=ugettext_lazy("my test title 1"),
                                                              form_class=None,
                                                              callback="non_middleware_action_callable"),
                        middleware_wrapped_other_test_action=dict(title=ugettext_lazy("my test title 2"),
                                                              form_class=DummyFormOther,
                                                              callback="middleware_wrapped_other_test_action"))

    TEMPLATE = "base_main.html" # must exist
    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = True

    #def __init__(self, *args, **kwargs):
    #    super(DummyTestAbility, self).__init__(*args, **kwargs)


    def get_template_vars(self, previous_form_data=None):
        return {'page_title': "hello", }

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
        new_settings.setdefault("is_active", True) # retrocompatibility
        self.settings["middlewares"].setdefault(action_name, PersistentDict())
        middleware_settings = self.settings["middlewares"][action_name].setdefault(middleware_class.__name__, PersistentDict())
        middleware_settings.clear()
        middleware_settings.update(new_settings)
        assert middleware_settings is self.get_middleware_settings(action_name, middleware_class, ensure_active=False)

    @transaction_watcher
    def reset_test_data(self, action_name, middleware_class, game_data):
        middleware_settings = self.get_private_middleware_data(action_name, middleware_class, create_if_unexisting=True)
        middleware_settings.clear()
        middleware_settings.update(game_data)


    @transaction_watcher
    def non_middleware_action_callable(self, use_gems):
        self.notify_event("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE")
        return 23

    @transaction_watcher # must be on the OUTSIDE
    @with_enforced_action_middlewares("middleware_wrapped_test_action") # SHARED MIDDELWARE CONFIG, possible in tests only
    def middleware_wrapped_callable1(self, use_gems):
        self.notify_event("INSIDE_MIDDLEWARE_WRAPPED1")
        return 18277

    @transaction_watcher # must be on the OUTSIDE
    @with_enforced_action_middlewares("middleware_wrapped_test_action") # SHARED MIDDELWARE CONFIG, possible in tests only
    def middleware_wrapped_callable2(self, my_arg, use_gems=()):
        self.notify_event("INSIDE_MIDDLEWARE_WRAPPED2")
        return True

    @transaction_watcher # must be on the OUTSIDE
    @with_enforced_action_middlewares("middleware_wrapped_other_test_action")
    def middleware_wrapped_other_test_action(self, my_arg, use_gems=()):
        self.notify_event("INSIDE_MIDDLEWARE_WRAPPED_OTHER_ACTION")
        return True

