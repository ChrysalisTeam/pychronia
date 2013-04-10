# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import AbstractGameView, register_view, transaction_watcher
from rpgweb import forms
from django.http import Http404, HttpResponse
import json
from rpgweb.forms import MoneyTransferForm, GemsTransferForm, UninstantiableFormError, \
    ArtefactTransferForm


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





class CharactersView(AbstractGameView):

    NAME = "characters_view"

    GAME_ACTIONS = dict(money_transfer_form=dict(title=_lazy("Transfer money"),
                                                          form_class=MoneyTransferForm,
                                                          callback="transfer_money"),
                        gems_transfer_form=dict(title=_lazy("Transfer gems"),
                                                          form_class=GemsTransferForm,
                                                          callback="transfer_gems"),
                        transfer_artefact=dict(title=_lazy("Transfer artefact"),
                                                          form_class=ArtefactTransferForm,
                                                          callback="transfer_artefact"))

    TEMPLATE = "auction/view_characters.html"

    ACCESS = UserAccess.authenticated
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True



    def get_template_vars(self, previous_form_data=None):

        # Preparing form for money transfer
        try:
            new_money_form = self._instantiate_form(new_action_name="money_transfer_form",
                                                     hide_on_success=False,
                                                     previous_form_data=previous_form_data)
        except UninstantiableFormError:
            new_money_form = None
            pass # TODO ADD MESSAGE

        # preparing gems transfer form
        try:
            new_gems_form = self._instantiate_form(new_action_name="gems_transfer_form",
                                                     hide_on_success=False,
                                                     previous_form_data=previous_form_data)
        except UninstantiableFormError:
            new_gems_form = None
            pass # TODO ADD MESSAGE

        # preparing artefact transfer form
        try:
            new_artefact_form = self._instantiate_form(new_action_name="transfer_artefact",
                                                             hide_on_success=False,
                                                             previous_form_data=previous_form_data)
        except UninstantiableFormError:
            new_artefact_form = None
            pass # TODO ADD MESSAGE

        # we display the list of available character accounts

        characters = self.datamanager.get_character_sets().items()

        sorted_characters = sorted(characters, key=lambda (key, value): key)  # sort by character username
        character_item_details = {username: self.datamanager.get_available_items_for_user(username=username).values()
                                for username, user_details in sorted_characters}

        return {
                 'page_title': _("Account Management"),
                 'pangea_domain':self.datamanager.get_global_parameter("pangea_network_domain"),
                 'money_form': new_money_form,
                 'gems_form': new_gems_form,
                 'artefact_form': new_artefact_form,
                 'char_sets': [sorted_characters], # single set ATM
                 'character_item_details': character_item_details,
               }


    @transaction_watcher
    def transfer_money(self, recipient_name, amount, sender_name=None):
        assert amount > 0 # enforced by form system
        user = self.datamanager.user
        if not user.is_master:
            assert not sender_name, sender_name
            sender_name = user.username

        self.datamanager.transfer_money_between_characters(from_name=sender_name,
                                                           to_name=recipient_name,
                                                           amount=amount)  # amount can only be positive here, thx to form validation
        return _("Money transfer successful.")


    @transaction_watcher
    def transfer_gems(self, recipient_name, gems_choices, sender_name=None):
        user = self.datamanager.user
        if not user.is_master:
            assert not sender_name, sender_name
            sender_name = user.username

        self.datamanager.transfer_gems_between_characters(from_name=sender_name,
                                                          to_name=recipient_name,
                                                          gems_choices=gems_choices)
        return _("Gems transfer successful.")


    @transaction_watcher
    def transfer_artefact(self, recipient_name, artefact_name):

        self.datamanager.transfer_object_to_character(item_name=artefact_name,
                                                      char_name=recipient_name,
                                                      previous_owner=self.datamanager.username) # redundant check, since form already ensures ownership
        return _("Artefact transfer successful.")



view_characters = CharactersView.as_view







@register_view(access=UserAccess.authenticated, always_available=True) # fixme ? always available ?
def view_sales(request, template_name='auction/view_sales.html'):
    # FIXME - needs a review ########
    user = request.datamanager.user

    if user.is_master:
        # we process sale management operations - BEWARE, input checking is LOW here!
        params = request.POST
        if "buy" in params and "username" in params and "object" in params:
            with action_failure_handler(request, _("Object successfully transferred to %s.") % params["username"].capitalize()):
                request.datamanager.transfer_object_to_character(params["object"], char_name=params["username"])
        elif "unbuy" in params and "username" in params and "object" in params:
            with action_failure_handler(request, _("Sale successfully canceled for %s.") % params["username"].capitalize()):
                request.datamanager.transfer_object_to_character(params["object"], char_name=None)


    # IMPORTANT - we copy, so that we can modify the object without changing DBs !
    items_for_sales = copy.deepcopy(request.datamanager.get_auction_items())

    ''' Useless
    # we inject the official name of object owner
    for item in items_for_sales.values():
        if item["owner"]:
            item["owner_official_name"] = request.datamanager.get_official_name(item["owner"])
        else:
            item["owner_official_name"] = None
    '''

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
                     'usernames':  request.datamanager.get_character_usernames(),
                     #'character_names': request.datamanager.get_character_official_names(),
                     'total_items_price': total_items_price,
                     'total_cold_cash_available': total_cold_cash_available,
                     'total_bank_account_available': total_bank_account_available,
                     'total_gems_number': total_gems_number,
                     'total_archaeological_objects_number': total_archaeological_objects_number
                    })



@register_view(access=UserAccess.anonymous)
def auction_items_slideshow(request, template_name='auction/items_slideshow.html'):
    """
    Contains ALL auction items, WITHOUT 3D viewers.
    """
    page_title = _("Auction Items")
    items = request.datamanager.get_auction_items()
    sorted_items = list(sorted(items.items()))# pairs key/dict

    return render(request,
                  template_name,
                    {
                     'page_title': page_title,
                     'items': sorted_items,
                     'items_3D_settings': None
                    })



@register_view(access=UserAccess.authenticated)
def personal_items_slideshow(request, template_name='auction/items_slideshow.html'):
    """
    Contains both auction and external items, all necessarily owned by user hismelf.
    """
    page_title = _("My Items")
    items = request.datamanager.get_available_items_for_user()
    items_3D_settings = request.datamanager.get_items_3d_settings()

    sorted_items = [(key, items[key]) for key in sorted(items.keys())]

    return render(request,
                  template_name,
                    {
                     'page_title': page_title,
                     'items': sorted_items,
                     'items_3D_settings': items_3D_settings
                    })


@register_view(attach_to=personal_items_slideshow)
def item_3d_view(request, item, template_name='utilities/item_3d_viewer.html'):

    available_items = request.datamanager.get_available_items_for_user()

    if item not in available_items.keys():
        raise Http404 # important security

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
















@register_view(access=UserAccess.authenticated)
def ajax_chat(request):

    if request.method == "POST":
        # User has sent new data.
        msg_text = request.POST.get('message', "")
        msg_text = msg_text.strip()
        if msg_text:  # Just ignore empty strings.
            request.datamanager.send_chatroom_message(msg_text)  # will fail if user is master

        return HttpResponse("OK")

    else:
        slice_index = int(request.GET['slice_index'])  # may raise exceptions

        (new_slice_index, previous_msg_timestamp, new_messages) = request.datamanager.get_chatroom_messages(slice_index)
        msg_format = "<b>%(official_name)s</b> - %(message)s"
        time_format = "<i>=== %d/%m/%Y - %H:%M:%S UTC ===</i>"

        threshold = request.datamanager.get_global_parameter("chatroom_timestamp_display_threshold_s")
        chatroom_timestamp_display_threshold = timedelta(seconds=threshold)
        text_lines = []
        for msg in new_messages:
            if not previous_msg_timestamp or (msg["time"] - previous_msg_timestamp) > chatroom_timestamp_display_threshold:
                text_lines.append(msg["time"].strftime(time_format))
            if msg["username"] in request.datamanager.get_character_usernames():
                official_name = request.datamanager.get_official_name(msg["username"])
                color = request.datamanager.get_character_color_or_none(msg["username"])
            else:  # system message
                official_name = _("system")
                color = "grey"
            data = dict(official_name=official_name,
                        message=msg["message"])
            text_lines.append({"username": msg["username"],
                               "color": color,
                               "message": msg_format % data})
            previous_msg_timestamp = msg["time"]

        all_data = {"slice_index": new_slice_index,
                    "messages": text_lines,
                    'chatting_users': request.datamanager.get_chatting_users(), }

        response = HttpResponse(json.dumps(all_data))
        response['Content-Type'] = 'text/plain; charset=utf-8'
        response['Cache-Control'] = 'no-cache'

        #  -> n

        return response





@register_view(access=UserAccess.authenticated)  # game master can view too
def chatroom(request, template_name='auction/chatroom.html'):

    return render(request,
                  template_name,
                    {
                     'page_title': _("Common Chatroom"),
                    })

