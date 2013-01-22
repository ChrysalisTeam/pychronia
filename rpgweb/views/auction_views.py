# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager.abstract_game_view import AbstractGameView, register_view
from rpgweb import forms
from django.http import Http404


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








@register_view(access=UserAccess.authenticated)
def view_sales(request, template_name='auction/view_sales.html'):

    user = request.datamanager.user

    if user.is_master:
        # we process sale management operations
        params = request.POST
        if "buy" in params and "character" in params and "object" in params:
            with action_failure_handler(request, _("Object successfully transferred to %s.") % params["character"]):
                request.datamanager.transfer_object_to_character(params["object"], request.datamanager.get_username_from_official_name(params["character"]))
        elif "unbuy" in params and "character" in params and "object" in params:
            with action_failure_handler(request, _("Sale successfully canceled for %s.") % params["character"]):
                request.datamanager.undo_object_transfer(params["object"], request.datamanager.get_username_from_official_name(params["character"]))


    # IMPORTANT - we copy, so that we can modify the object without changing DBs !
    items_for_sales = copy.deepcopy(request.datamanager.get_auction_items())

    # we inject the official name of object owner
    for item in items_for_sales.values():
        if item["owner"]:
            item["owner_official_name"] = request.datamanager.get_official_name_from_username(item["owner"])
        else:
            item["owner_official_name"] = None

    sorted_items_for_sale = items_for_sales.items()
    sorted_items_for_sale.sort(key=lambda x: x[1]['auction'])

    if user.is_master:
        total_items_price = sum(item["total_price"] for item in items_for_sales.values())
        total_cold_cash_available = sum(character["initial_cold_cash"] for character in request.datamanager.get_character_sets().values())
        total_bank_account_available = sum(character["account"] for character in request.datamanager.get_character_sets().values())
    else:
        total_items_price = None
        total_cold_cash_available = None
        total_bank_account_available = None

    total_gems_number = sum(item["num_items"] for item in items_for_sales.values() if item["is_gem"])
    total_archaeological_objects_number = sum(item["num_items"] for item in items_for_sales.values() if not item["is_gem"])

    return render(request,
                  template_name,
                    {
                     'page_title': _("Auction"),
                     'items_for_sale': sorted_items_for_sale,
                     'character_names': request.datamanager.get_character_official_names(),
                     'total_items_price': total_items_price,
                     'total_cold_cash_available': total_cold_cash_available,
                     'total_bank_account_available': total_bank_account_available,
                     'total_gems_number': total_gems_number,
                     'total_archaeological_objects_number': total_archaeological_objects_number
                    })









@register_view(access=UserAccess.anonymous)  # not always available
def items_slideshow(request, template_name='auction/items_slideshow.html'):

    user = request.datamanager.user

    if user.is_authenticated:
        page_title = _("Team Items")
        items = request.datamanager.get_available_items_for_user(user.username)
        items_3D_settings = request.datamanager.get_items_3d_settings()
    else:
        page_title = _("Auction Items")
        items = request.datamanager.get_available_items_for_user(None)  # all items
        items_3D_settings = {}  # IMPORTANT - no access to 3D views here

    sorted_items = [(key, items[key]) for key in sorted(items.keys())]

    return render(request,
                  template_name,
                    {
                     'page_title': page_title,
                     'items': sorted_items,
                     'items_3D_settings': items_3D_settings
                    })

@register_view(access=UserAccess.authenticated)  # not always available, so beware!! TODO FIXME ensure it's not displayed if not available!
def item_3d_view(request, item, template_name='utilities/item_3d_viewer.html'):

    user = request.datamanager.user

    available_items = request.datamanager.get_available_items_for_user(user.username)

    if item not in available_items.keys():
        raise Http404

    viewers_settings = request.datamanager.get_items_3d_settings()
    if item not in viewers_settings.keys():
        raise Http404

    viewer_settings = viewers_settings[item]

    return render(request,
                  template_name,
                    {
                     'settings': _build_display_data_from_viewer_settings(viewer_settings),
                    })

def _build_display_data_from_viewer_settings(viewer_settings):

    image_urls = []
    for level in range(viewer_settings["levels"]):
        level_urls = []
        for rel_index in range(viewer_settings["per_level"] * level, viewer_settings["per_level"] * (level + 1)):
            abs_index = viewer_settings["index_offset"] + rel_index * viewer_settings["index_steps"]
            rel_url = viewer_settings["file_template"] % abs_index
            level_urls.append(game_file_url(rel_url))
        if viewer_settings["autoreverse"]:
            level_urls = level_urls + list(reversed(level_urls))
        image_urls.append(level_urls)

    real_per_level = viewer_settings["per_level"] * (2 if viewer_settings["autoreverse"] else 1)
    assert set([len(imgs) for imgs in image_urls]) == set([real_per_level])  # all levels have the same number of images

    display_data = dict(levels=viewer_settings["levels"],
                            per_level=real_per_level,
                            x_coefficient=viewer_settings["x_coefficient"],
                            y_coefficient=viewer_settings["y_coefficient"],
                            rotomatic=viewer_settings["rotomatic"],  # ms between rotations
                            image_width=viewer_settings["image_width"],
                            image_height=viewer_settings["image_height"],
                            start_level=viewer_settings["start_level"],
                            mode=viewer_settings["mode"],
                            image_urls=image_urls,  # multi-level array
                            music_url=game_file_url(viewer_settings["music"]) if viewer_settings["music"] else None,)
    return display_data
