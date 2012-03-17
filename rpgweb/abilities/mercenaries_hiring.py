# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from ._abstract_ability import *
from ..contextmanagers import *












class AgentsHiringForm(AbstractAbilityForm):

    def __init__(self, datamanager, *args, **kwargs):
        super(AgentHiringForm, self).__init__(*args, **kwargs)

        _locations = sorted(datamanager.get_locations().keys())
        _location_choices = zip(_locations, _locations)

        _gems = request.datamanager.get_character_properties(user.username)["gems"]
        _gems_choices = zip(_gems, [_("Gem of %d Kashes")%gem for gem in gems])

        if _gems_choices:
            self.fields["pay_with_money"] = forms.BooleanField(label=_("Pay with money"), initial=False)
            self.fields["gems_list"] = forms.MultipleChoiceField(required=False, label=_("Or pay with gems (press Ctrl key to select/deselect)"), choices=_gems_choices)
        else:
            self.fields["pay_with_money"] = forms.BooleanField(label=_("Pay with money"), initial=True, widget=forms.HiddenInput)

        self.fields["location"] = forms.ChoiceField(label=_lazy(u"Location"), choices=_location_choices)

        # DEPRECATED self.fields["type"] = forms.ChoiceField(label=_lazy("Type"), choices=[("spy", _lazy("Spies")), ("mercenary", _lazy("Mercenaries"))])


    def get_normalized_values(self):

        parameters = super(AgentsHiringForm, self).get_normalized_values()

        parameters.setdefault("gems_list", [])
        parameters["gems_list"] = [int(gem) for gem in parameters["gems_list"]]

        parameters["pay_with_gems"] = not parameters["pay_with_money"]

        return parameters



class MercenariesHiringAbility(AbstractAbilityHandler):

    NAME = "mercenaries_hiring"

    LEVEL = "player"

    FORMS = {"agents_form": (AgentsHiringForm, "hire_remote_agent")}

    TEMPLATE = "abilities/mercenaries_hiring.html"

    REQUIRES = ["messaging"]



    def get_template_vars(self, previous_form_data=None):

        employer_profile = request.datamanager.get_character_properties(user.username)
        gems = request.datamanager.get_character_properties(user.username)["gems"]
        total_gems_value = sum(gems)

        hiring_form = self._instantiate_form(new_form_name="agents_form", 
                                             hide_on_success=False,
                                             previous_form_data)

        return {
                 'page_title': _("Mercenaries Network Management"),
                 'global_parameters': request.datamanager.get_global_parameters(), # TODO CHANGE THAT
                 'places_with_mercenaries': places_with_mercenaries,
                 'employer_profile': employer_profile,
                 'total_gems_value': total_gems_value,
                 'hiring_form': hiring_form
               }





    @transaction_watcher
    def hire_remote_agent(self, location, pay_with_gems=False, gems_list=None):
        # warning - several users might be able to hire agents, but in any case these agents belong to Masslavia !

        employer_name = self.datamanager.player.username

        location_data = self.datamanager.get_locations()[location]
        private_data = self.private_data

        gems_price = self.get_ability_parameter("mercenary_cost_gems")
        money_price = self.get_ability_parameter("mercenary_cost_money")

        if location in private_data["mercenaries_locations"]:
            raise UsageError(_("You already control mercenaries in this location"))


        employer_char = self.datamanager.get_character_properties(employer_name)

        if pay_with_gems:
            if not gems_list or sum(gems_list) < gems_price:
                raise UsageError(_("You need at least %(price)s kashes in gems to hire these agents") % SDICT(gems_price=gems_price))
                # we don't care if the agent has given too many gems !

            remaining_gems = utilities.substract_lists(employer_char["gems"], gems_list)

            if remaining_gems is None:
                raise UsageError(_("You don't possess the gems required"))
            else:
                employer_char["gems"] = remaining_gems


        else: # paying with bank money

            if gems_list:
                raise UsageError(_("You can't pay with both gems and bank money"))

            if employer_char["account"] < money_price:
                raise UsageError(_("You need at least %(price)s kashes in money to hire these agents") % SDICT(
                    price=money_price))

            #print self.data["global_parameters"]["total_digital_money_spent"], "----",employer_char["account"]

            employer_char["account"] -= money_price
            self.datamanager.data["global_parameters"]["total_digital_money_spent"] += money_price

            #print self.data["global_parameters"]["total_digital_money_spent"], "----",employer_char["account"]

        private_data["mercenaries_locations"].append(location)

        self._process_spy_activation(location)

        self.log_game_event(_noop("Mercenary hired by %(employer_name)s in %(location)s"),
                             PersistentDict(employer_name=employer_name, location=location),
                             url=None)




    @transaction_watcher
    def _process_spy_activation(self, location):

        employer_name = self.datamanager.player.username

        spy_message = self.get_locations()[location]["spy_message"].strip()
        spy_audio = self.get_locations()[location]["spy_audio"]
        #print "ACTIVATING SPY %s with message %s" % (city_name, spy_message)

        sender_email = "message-forwarder@masslavia.com"
        recipient_emails = self.get_character_email(employer_name)
        subject = _("<Spying Report - %(city_name)s>") % SDICT(city_name=city_name.capitalize())

        default_message = _("*Report from your spies of %(city_name)s*") % SDICT(city_name=city_name.capitalize())

        if spy_audio:
            body = default_message
            attachment = config.GAME_FILES_URL + "spy_reports/spy_" + city_name.lower() + ".mp3"
        else:
            body = default_message + "\n\n-------\n\n" + spy_message
            attachment = None

        self.post_message(sender_email, recipient_emails, subject, body, attachment,
                          date_or_delay_mn=self.get_global_parameter("spy_report_delays"))









    @classmethod
    def _setup_ability_settings(cls, settings):
        pass # Nothing to do

    def _setup_private_ability_data(self, private_data):

        private_data.setdefault("mercenaries_locations", PersistentList())


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        _reference = dict(
                            mercenary_cost_money = utilities.check_is_positive_int,
                            mercenary_cost_gems = utilities.check_is_positive_int
                         )
        utilities.check_dictionary_with_template(settings, _reference, strict=strict)


        for data in self.all_private_data.values():

            if strict:
                utilities.check_num_keys(data, 1)

            assert len(set(data["mercenaries_locations"])) == len(data["mercenaries_locations"]) # unicity

            all_locations = self.datamanager.get_locations().keys()
            for location in data["mercenaries_locations"]:
                assert location all_locations








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
            request.datamanager.hire_remote_agent(user.username, location, mercenary, not pay_with_money, selected_gems) # free for the game master

    places_with_spies = [key for key in sorted(locations.keys()) if locations[key]['has_spy']]
    places_with_mercenaries = [key for key in sorted(locations.keys()) if locations[key]['has_mercenary']]


    if user.is_master:
        employer_profile = None
        total_gems_value = None
        gems_choices = [] # hire_remote_agent("master") will allow the hiring of agents anyway !
    else:
        employer_profile = request.datamanager.get_character_properties(user.username)
        gems = request.datamanager.get_character_properties(user.username)["gems"]
        gems_choices = zip(gems, [_("Gem of %d Kashes")%gem for gem in gems])
        total_gems_value = sum(gems)

    return render_to_response(template_name,
                            {
                             'page_title': _("Agent Network Management"),
                             'global_parameters': request.datamanager.get_global_parameters(), # TODO REMOVE
                             'places_with_spies': places_with_spies,
                             'places_with_mercenaries': places_with_mercenaries,
                             'employer_profile': employer_profile,
                             'total_gems_value': total_gems_value,
                             'hiring_form': forms.AgentHiringForm(request.datamanager, gems_choices)
                            },
                            context_instance=RequestContext(request))
