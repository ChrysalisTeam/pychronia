# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager.abstract_game_view import AbstractGameView, register_view
from rpgweb import forms

@register_view(access=UserAccess.anonymous, always_available=True)
def homepage(request, template_name='auction/homepage.html'):

    return render(request,
                  template_name,
                    {
                     'page_title': _("Welcome to Anthropia, %s") % request.datamanager.username,
                    })


@register_view(access=UserAccess.anonymous, always_available=True)
def opening(request, template_name='auction/opening.html'): # NEEDS FIXING !!!!

    return render(request,
                  template_name,
                    {
                     'page_title': None,
                    })




@register_view(access=UserAccess.authenticated)
def view_characters(request, template_name='auction/view_characters.html'):

    user = request.datamanager.user

    def refreshed_gems_choice():
        # computing available gems
        if user.is_master:
            available_gems = []
            for character, properties in request.datamanager.get_character_sets().items():
                available_gems += properties["gems"]
        else:
            # FIXME, bugged
            available_gems = request.datamanager.get_character_properties(user.username)["gems"]
        gems_choices = zip([str(i[0]) for i in available_gems], [_("Gem of %s Kashes") % str(available_gem) for available_gem in available_gems])
        return gems_choices


    if request.method == "POST":
        if request.POST.get("money_transfer"):

            money_form = forms.MoneyTransferForm(request.datamanager, user, request.POST)
            if money_form.is_valid():

                if user.is_master:
                    sender = money_form.cleaned_data['sender_name']
                else:
                    sender = user.username

                recipient = money_form.cleaned_data['recipient_name']

                with action_failure_handler(request, _("Money transfer successful.")):
                    request.datamanager.transfer_money_between_characters(sender,
                                                                  recipient,
                                                                  money_form.cleaned_data['amount'])  # amount can only be positive here
            else:
                user.add_error(_("Money transfer failed - invalid parameters."))


        elif request.POST.get("gems_transfer"):
            gems_choices = refreshed_gems_choice()
            gems_form = forms.GemsTransferForm(request.datamanager, user, gems_choices, request.POST)
            if gems_form.is_valid():

                if user.is_master:
                    sender = gems_form.cleaned_data['sender_name']
                else:
                    sender = user.username

                with action_failure_handler(request, _("Gems transfer successful.")):
                    selected_gems = [int(gem) for gem in gems_form.cleaned_data['gems_choices']]
                    request.datamanager.transfer_gems_between_characters(sender,
                                                                  gems_form.cleaned_data['recipient_name'],
                                                                  selected_gems)
            else:
                user.add_error(_("Gems transfer failed - invalid parameters."))



    ### IN ANY WAY WE RESET FORMS, BECAUSE CHARACTER SETTINGS MAY HAVE CHANGED ! ###

    # Preparing form for money transfer
    if user.is_master or request.datamanager.get_character_properties(user.username)["account"]:
        new_money_form = forms.MoneyTransferForm(request.datamanager, user)
    else:
        new_money_form = None

    # preparing gems transfer form
    gems_choices = refreshed_gems_choice()
    if gems_choices:
        new_gems_form = forms.GemsTransferForm(request.datamanager, user, gems_choices)
    else:
        new_gems_form = None


    # we display the list of available character accounts

    characters = request.datamanager.get_character_sets().items()

    sorted_characters = sorted(characters, key=lambda (key, value): key)  # sort by character name

    char_sets = [sorted_characters]  # only one list for now...
    '''
    temp_set = []
    old_domain = None
    for key, value in sorted_characters:
        if old_domain is not None and value["domain"] != old_domain:
            char_sets.append(temp_set)
            temp_set = []
        temp_set.append((key, value))
        old_domain = value["domain"]
    if temp_set:
        char_sets.append(temp_set)
    '''

    if user.is_master:
        show_official_identities = True
    else:
        domain = request.datamanager.get_character_properties(user.username)["domains"][0]
        show_official_identities = request.datamanager.get_domain_properties(domain)["show_official_identities"]
    return render(request,
                  template_name,
                    {
                     'page_title': _("Account Management"),
                     'pangea_domain':request.datamanager.get_global_parameter("pangea_network_domain"),
                     'money_form': new_money_form,
                     'gems_form': new_gems_form,
                     'char_sets': char_sets,
                     'bank_data': (request.datamanager.get_global_parameter("bank_name"), request.datamanager.get_global_parameter("bank_account")),
                     'show_official_identities': show_official_identities,
                    })
