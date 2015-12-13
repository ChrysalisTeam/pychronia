# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import json
from django import forms

from pychronia_game.common import *
from pychronia_game.forms import AbstractGameForm
from pychronia_game.datamanager.datamanager_tools import transaction_watcher, \
    readonly_method
from pychronia_game.datamanager.abstract_ability import AbstractPartnershipAbility





class AgentsHiringForm(AbstractGameForm):

    def __init__(self, datamanager, *args, **kwargs):
        super(AgentsHiringForm, self).__init__(datamanager, *args, **kwargs)

        _locations = sorted(datamanager.get_locations().keys())
        _location_choices = zip(_locations, _locations)

        self.fields["location"] = forms.ChoiceField(label=ugettext_lazy(u"Location"), choices=_location_choices)







class MercenariesHiringAbility(AbstractPartnershipAbility):

    TITLE = ugettext_lazy("Mercenaries Hiring")
    NAME = "mercenaries_hiring"

    GAME_ACTIONS = dict(hiring_form=dict(title=ugettext_lazy("Hire mercenaries"),
                                                      form_class=AgentsHiringForm,
                                                      callback="hire_remote_agent"))

    TEMPLATE = "abilities/mercenaries_hiring.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True


    def _get_admin_summary_html(self):
        assert self.is_master()
        data = self.all_private_data.items()
        all_mercenaries_locations = sorted((k, v["mercenaries_locations"])
                                           for (k, v) in data
                                           if v["mercenaries_locations"])

        template_vars = dict(all_mercenaries_locations=all_mercenaries_locations)
        res = render_to_string("abilities/mercenaries_hiring_summary.html",
                               template_vars)

        return res


    def get_template_vars(self, previous_form_data=None):

        assert self.is_character()
        #_user_profile = self.get_character_properties()
        #gems = _user_profile["gems"]
        #total_gems_value = sum(gem[0] for gem in gems)

        # for now we don't exclude locations of already hired mercenaries
        hiring_form = self._instantiate_game_form(new_action_name="hiring_form",
                                             hide_on_success=False,
                                             previous_form_data=previous_form_data)

        mercenaries_locations = self.private_data["mercenaries_locations"]

        #print (">>>>>>>>>>>>>>>>", self.settings)
        return {
                 'page_title': _("Mercenaries Management"),
                 'settings': self.settings,
                 'mercenaries_locations': mercenaries_locations,
                 'hiring_form': hiring_form,
                 'dedicated_email': self.dedicated_email,
               }


    @readonly_method
    def has_remote_agent(self, location):
        assert location in self.datamanager.get_locations()
        return location in self.private_data["mercenaries_locations"]


    @transaction_watcher
    def hire_remote_agent(self, location,
                                use_gems=()): # intercepted by action middlewares
        assert location in self.datamanager.get_locations()

        if self.has_remote_agent(location):
            raise UsageError(_("You already control mercenaries in this location"))

        self.private_data["mercenaries_locations"].append(location)

        ### self._process_spy_activation(location) # USELESS ?

        self.log_game_event(ugettext_noop("Mercenary hired in %(location)s"),
                             PersistentMapping(location=location),
                             url=None,
                             visible_by=[self.username])

        return _("Mercenaries have been successfully hired")



    @classmethod
    def _setup_ability_settings(cls, settings):
        pass # nothing to do

    def _setup_private_ability_data(self, private_data):

        private_data.setdefault("mercenaries_locations", PersistentList())


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        ''' OBSOLETE
        _reference = dict(
                            mercenary_cost_money=utilities.check_is_positive_int,
                            mercenary_cost_gems=utilities.check_is_positive_int
                         )
        utilities.check_dictionary_with_template(settings, _reference, strict=strict)
        '''

        for data in self.all_private_data.values():

            if strict:
                utilities.check_num_keys(data, 1)

            utilities.check_no_duplicates(data["mercenaries_locations"])

            all_locations = self.datamanager.get_locations().keys()
            assert set(data["mercenaries_locations"]) <= set(all_locations), data["mercenaries_locations"]





'''

@game_player_required(permission="manage_agents")
def network_management(request, template_name='specific_operations/network_management.html'):

    locations = request.datamanager.get_locations() # dictionary


    # we process wiretap management operations
    if request.method == "POST":
        with action_failure_handler(request, _("Hiring operation successful.")):
            location = request.POST["location"]
            mercenary = (request.POST["type"] == "mercenary")
            pay_with_money = request.POST.get("pay_with_money", False)
            selected_gems = [int(gem) for gem in request.POST.getlist("gems_choices")]
            request.datamanager.hire_remote_agent(location, mercenary, not pay_with_money, selected_gems) # free for the game master

    places_with_spies = [key for key in sorted(locations.keys()) if locations[key]['has_spy']]
    places_with_mercenaries = [key for key in sorted(locations.keys()) if locations[key]['has_mercenary']]


    if user.is_master:
        employer_profile = None
        total_gems_value = None
        gems_choices = [] # hire_remote_agent("master") will allow the hiring of agents anyway !
    else:
        employer_profile = request.datamanager.get_character_properties()
        gems = request.datamanager.get_character_properties()["gems"]
        gems_choices = zip(gems, [_("Gem of %d Kashes")%gem for gem in gems])
        total_gems_value = sum(gems)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Agent Network Management"),
                     'global_parameters': request.datamanager.get_global_parameters(), # TODO REMOVE
                     'places_with_spies': places_with_spies,
                     'places_with_mercenaries': places_with_mercenaries,
                     'employer_profile': employer_profile,
                     'total_gems_value': total_gems_value,
                     'hiring_form': forms.AgentHiringForm(request.datamanager, gems_choices)
                    })

     
     
     
     
     
        DEPRECATED
        employer_char = self.datamanager.get_character_properties(employer_name)

        if pay_with_gems:
            if sum(pay_with_gems) < gems_price:
                raise UsageError(_("You need at least %(price)s kashes in gems to hire these agents") % SDICT(gems_price=gems_price))
                # we don't care if the player has given too many gems !

            remaining_gems = utilities.substract_lists(employer_char["gems"], pay_with_gems)

            if remaining_gems is None:
                raise UsageError(_("You don't possess the gems required"))
            else:
                employer_char["gems"] = remaining_gems


        else: # pay with bank money

            if employer_char["account"] < money_price:
                raise UsageError(_("You need at least %(price)s kashes in money to hire these agents") % SDICT(price=money_price))

            #print self.data["global_parameters"]["total_digital_money_spent"], "----",employer_char["account"]

            employer_char["account"] -= money_price
            self.datamanager.data["global_parameters"]["total_digital_money_spent"] += money_price

            #print self.data["global_parameters"]["total_digital_money_spent"], "----",employer_char["account"]




    @transaction_watcher
    def ____process_spy_activation(self, location):
        # USELESS ?
        employer_name = self.datamanager.player.username
        
        location_data = self.datamanager.get_locations()[location]
        
        spy_message = location_data["spy_message"].strip()
        spy_audio = location_data["spy_audio"]
        #print "ACTIVATING SPY %s with message %s" % (city_name, spy_message)

        sender_email = "message-forwarder@masslavia.com"
        recipient_emails = self.get_character_email(employer_name)
        subject = _("<Spying Report - %(city_name)s>") % SDICT(city_name=location.capitalize())

        default_message = _("*Report from your spies of %(city_name)s*") % SDICT(city_name=location.capitalize())

        if spy_audio:
            body = default_message
            attachment = game_file_url("spy_reports/spy_" + location.lower() + ".mp3")
        else:
            body = default_message + "\n\n-------\n\n" + spy_message
            attachment = None

        parent_id = self.post_message(user_email, recipient_emails, subject, body, attachment,
                              date_or_delay_mn=self.get_global_parameter("spy_report_delays"))


        '''
