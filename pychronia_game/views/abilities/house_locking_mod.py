# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_ability import AbstractAbility
from pychronia_game.datamanager.abstract_game_view import register_view
from pychronia_game.datamanager import readonly_method, \
    transaction_watcher


@register_view
class HouseLockingAbility(AbstractAbility):

    #TITLE = ugettext_lazy("Manor Security")

    TITLE = ugettext_lazy("Manor Security")
    NAME = "house_locking"

    GAME_ACTIONS = dict(lock=dict(title=ugettext_lazy("Lock house doors"),
                                              form_class=None,
                                              callback="lock_house_doors"),
                        unlock=dict(title=ugettext_lazy("Unlock house doors"),
                                              form_class=None,
                                              callback="try_unlocking_house_doors"))

    TEMPLATE = "abilities/house_locking.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True



    def get_template_vars(self, previous_form_data=None):
        are_doors_open = self.are_house_doors_open()
        return {
                'page_title': _("Doors Security Management"),
                'are_doors_open': are_doors_open
               }

    @readonly_method
    def are_house_doors_open(self):
        return self.settings["house_doors_are_open"]


    @transaction_watcher
    def lock_house_doors(self, use_gems=()):
        if self.are_house_doors_open():
            self.settings["house_doors_are_open"] = False
            self.user.add_message(_("House doors successfully locked."))
            self.log_game_event(_("House doors have been locked by security client."))
            return True
        else:
            self.user.add_error(_("Doors are already locked."))
            return False

        assert False, "lock_house_doors"


    @transaction_watcher
    def try_unlocking_house_doors(self, password, use_gems=()):

        expected_password = self.get_ability_parameter("house_doors_password")

        if not self.are_house_doors_open():
            if password.strip() == expected_password.strip():
                self.settings["house_doors_are_open"] = True
                self.user.add_message(_("House doors successfully unlocked."))
                self.log_game_event(_("House doors have been successfully unlocked with password."))
                return True
            else:
                self.user.add_error(_("Wrong password."))
                return False
        else:
            self.user.add_error(_("Doors are already unlocked."))
            return False

        assert False, "try_unlocking_house_doors"


    @classmethod
    def _setup_ability_settings(cls, settings):
        settings.setdefault("house_doors_are_open", True)


    def _setup_private_ability_data(self, private_data):
        pass


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        password = settings["house_doors_password"]
        assert utilities.check_is_string(password)
        assert password.isdigit()
        assert 2 <= len(password) <= 6

        if strict:
            utilities.check_num_keys(settings, 1)
        assert isinstance(settings["house_doors_are_open"], bool)




'''

# no security authentication
def ajax_domotics_security(request):

    action = request.REQUEST.get("action", None)
    if action == "lock":
        request.datamanager.lock_house_doors()
    elif action == "unlock":
        password = request.REQUEST.get("password", None)
        if password:
            request.datamanager.try_unlocking_house_doors(password)

    response = unicode(request.datamanager.are_house_doors_open())
    return HttpResponse(response) # "True" or "False"

'''
