# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager import AbstractGameView, register_view, transaction_watcher
from pychronia_game import forms
from django.http import Http404, HttpResponse
import json
from pychronia_game.forms import (MoneyTransferForm, GemsTransferForm, ArtefactTransferForm)




@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Homepage"))
def homepage(request, template_name='auction/homepage.html'):

    return render(request,
                  template_name,
                    {
                     'page_title': _("Welcome to Anthropia, %s") % request.datamanager.username.capitalize(),
                    })


@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Opening"))
def ___opening(request, template_name='auction/opening.html'): # NEEDS FIXING !!!!

    return render(request,
                  template_name,
                    {
                     'page_title': None,
                    })




@register_view
class CharactersView(AbstractGameView):

    TITLE = ugettext_lazy("Auction Bidders")
    TITLE_FOR_MASTER = ugettext_lazy("Characters")

    NAME = "characters_view"

    GAME_ACTIONS = dict(money_transfer_form=dict(title=ugettext_lazy("Transfer money"),
                                                          form_class=MoneyTransferForm,
                                                          callback="transfer_money"),
                        gems_transfer_form=dict(title=ugettext_lazy("Transfer gems"),
                                                          form_class=GemsTransferForm,
                                                          callback="transfer_gems"),
                        transfer_artefact=dict(title=ugettext_lazy("Transfer artefact"),
                                                          form_class=ArtefactTransferForm,
                                                          callback="transfer_artefact"))

    TEMPLATE = "auction/view_characters.html"

    ACCESS = UserAccess.authenticated
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False

    EXTRA_PERMISSIONS = ["view_others_belongings"]


    def get_template_vars(self, previous_form_data=None):

        ## All of these forms might be None ##

        # Preparing form for money transfer
        new_money_form = self._instantiate_game_form(new_action_name="money_transfer_form",
                                                     previous_form_data=previous_form_data)

        # preparing gems transfer form
        new_gems_form = self._instantiate_game_form(new_action_name="gems_transfer_form",
                                                    previous_form_data=previous_form_data)


        # preparing artefact transfer form
        new_artefact_form = self._instantiate_game_form(new_action_name="transfer_artefact",
                                                         previous_form_data=previous_form_data)


        # we display the list of available character accounts

        if self.datamanager.is_master():
            characters = self.datamanager.get_character_sets().items()
        else:
            characters = [(k, v) for (k, v) in self.datamanager.get_character_sets().items() if not v["is_npc"]]

        characters = copy.deepcopy(characters) # we ensure we don't touch real DB data

        show_others_belongings = self.datamanager.is_master() or self.datamanager.has_permission(permission="view_others_belongings")



        for username, user_data in characters:
            user_data["username"] = username
            user_data["email_address"] = self.datamanager.get_character_email(username=username)
            if username == self.datamanager.user.username or show_others_belongings:
                user_data["user_items"] = sorted(self.datamanager.get_available_items_for_user(username=username, auction_only=False).values(),
                                                  key=lambda x:x["title"]) # it's all or nothing, we don't discriminate by auction
            else:
                del user_data["account"] # security

        characters = sorted((v for (k, v) in characters), # now all is in user data dict
                            key=lambda value: (value["is_npc"], value["username"])) # sort by type and then login

        # NOW WRONG {% comment %} character is at least {'gems': [], 'items': [], 'domain': 'akaris.com', 'password': 'xxxx', 'account': 0} {% endcomment %}
        return {
                 'show_others_belongings': show_others_belongings,
                 'character_groups': [characters], # single set ATM
                 'money_form': new_money_form,
                 'gems_form': new_gems_form,
                 'artefact_form': new_artefact_form,
               }


    @transaction_watcher
    def transfer_money(self, recipient_name, amount, sender_name=None, reason=None, 
                       use_gems=()):  # required by action middlewares
        assert amount > 0 # enforced by form system
        user = self.datamanager.user
        if not user.is_master:
            assert not sender_name, sender_name
            sender_name = user.username

        self.datamanager.transfer_money_between_characters(from_name=sender_name,
                                                           to_name=recipient_name,
                                                           amount=amount, # amount can only be positive here, thx to form validation
                                                           reason=reason)
        return _("Money transfer successful.")


    @transaction_watcher
    def transfer_gems(self, recipient_name, gems_choices, sender_name=None, 
                      use_gems=()):  # required by action middlewares
        user = self.datamanager.user
        if not user.is_master:
            assert not sender_name, sender_name
            sender_name = user.username
        
        bank_name = self.datamanager.get_global_parameter("bank_name")

        if sender_name == recipient_name:
            raise UsageError(_("Sender and recipient must be different"))
        elif sender_name == bank_name:
            self.datamanager.credit_character_gems(username=recipient_name, gems_choices=gems_choices)
        elif recipient_name == bank_name:
            self.datamanager.debit_character_gems(username=sender_name, gems_choices=gems_choices)
        else:
            assert recipient_name in self.datamanager.get_character_usernames()
            self.datamanager.transfer_gems_between_characters(from_name=sender_name,
                                                              to_name=recipient_name,
                                                              gems_choices=gems_choices)
        return _("Gems transfer successful.")


    @transaction_watcher
    def transfer_artefact(self, recipient_name, artefact_name, use_gems=()):
        previous_owner = self.datamanager.username if not self.datamanager.is_master() else None
        self.datamanager.transfer_object_to_character(item_name=artefact_name,
                                                      char_name=recipient_name,
                                                      previous_owner=previous_owner) # redundant check, since form already ensures ownership
        return _("Artefact transfer successful.")


view_characters = CharactersView.as_view


def _sorted_game_items(items_dict):
    """
    items_dict must map item id to item data
    
    A modified COPY of item data is returned, as a list of (k, v) pairs.
    """
    items_list = copy.deepcopy(items_dict.items())
    res = sorted(items_list, key=lambda x: (x[1]['auction'] if x[1]['auction'] else "ZZZZZZZ", x[0]))
    return res


@register_view(access=UserAccess.authenticated, title=ugettext_lazy("Auction Items"), title_for_master=ugettext_lazy("All Items")) # fixme ? always available ?
def view_sales(request, template_name='auction/view_sales.html'):
    # FIXME - needs a review ########
    user = request.datamanager.user

    if user.is_master:
        # we process sale management operations - BEWARE, input checking is LOW here!
        params = request.POST
        if "buy" in params and "username" in params and "object" in params:
            with action_failure_handler(request, _("Object successfully transferred to '%s'.") % params["username"].capitalize()):
                if not params["username"]:
                    raise UsageError(_("Improper recipient"))
                request.datamanager.transfer_object_to_character(params["object"], char_name=params["username"])
        elif "unbuy" in params and "username" in params and "object" in params:
            with action_failure_handler(request, _("Sale successfully canceled for '%s'.") % params["username"].capitalize()):
                request.datamanager.transfer_object_to_character(params["object"], char_name=None)


    # IMPORTANT - we copy, so that we can modify the object without changing DBs !
    if user.is_master:
        items_for_sales = request.datamanager.get_all_items()
    else:
        # only AUCTION stuffs!
        items_for_sales = request.datamanager.get_auction_items()

    ''' Useless
    # we inject the official name of object owner
    for item in items_for_sales.values():
        if item["owner"]:
            item["owner_official_name"] = request.datamanager.get_official_name(item["owner"])
        else:
            item["owner_official_name"] = None
    '''

    sorted_items_for_sale = _sorted_game_items(items_for_sales) # we push non-auction items to the end of list

    if request.datamanager.should_display_admin_tips():  # security
        total_items_price = sum((item["total_price"] or 0) for item in items_for_sales.values())
        total_bank_account_available = sum(character["account"] for character in request.datamanager.get_character_sets().values())
    else:
        total_items_price = None
        total_bank_account_available = None

    total_gems_number = sum(item["num_items"] for item in items_for_sales.values() if item["is_gem"])
    total_archaeological_objects_number = sum(item["num_items"] for item in items_for_sales.values() if not item["is_gem"])

    return render(request,
                  template_name,
                    {
                     'items_for_sale': sorted_items_for_sale,
                     'usernames':  request.datamanager.get_character_usernames(),
                     #'character_names': request.datamanager.get_character_official_names(),
                     'total_items_price': total_items_price,
                     'total_bank_account_available': total_bank_account_available,
                     'total_gems_number': total_gems_number,
                     'total_archaeological_objects_number': total_archaeological_objects_number
                    })



@register_view(access=UserAccess.authenticated, title=ugettext_lazy("Auction Slideshow"), title_for_master=ugettext_lazy("Items Slideshow"))
def auction_items_slideshow(request, template_name='auction/items_slideshow.html'):
    """
    Contains ALL auction items, WITHOUT 3D viewers.
    """
    items = (request.datamanager.get_auction_items()
             if not request.datamanager.is_master()
             else request.datamanager.get_all_items()) # master can see EVERYTHING, but without 3D
    sorted_items = _sorted_game_items(items)

    return render(request,
                  template_name,
                    {
                     'items': sorted_items,
                     'items_3D_settings': None,
                     'gems_may_be_memo': False,
                    })



@register_view(access=UserAccess.authenticated, title=ugettext_lazy("My Items"))
def personal_items_slideshow(request, template_name='auction/items_slideshow.html'):
    """
    Contains both auction and external items, all necessarily owned by user hismelf.
    """
    items = request.datamanager.get_available_items_for_user()
    items_3D_settings = request.datamanager.get_items_3d_settings()

    items_3D_titles = sorted(items[k]["title"] for k in items_3D_settings.keys() if k in items)

    sorted_items = _sorted_game_items(items)

    return render(request,
                  template_name,
                    {
                     'items': sorted_items,
                     'items_3D_titles': items_3D_titles,
                     'items_3D_settings': items_3D_settings,
                     'gems_may_be_memo': True,
                    })


@register_view(access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("Item 3D View"))
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
















@register_view(access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("Ajax Chat"))
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
        time_format = "<i>=== %d/%m/%Y %H:%M:%S ===</i>"

        threshold = request.datamanager.get_global_parameter("chatroom_timestamp_display_threshold_s")
        chatroom_timestamp_display_threshold = timedelta(seconds=threshold)
        text_lines = []
        usernames = request.datamanager.get_character_usernames()
        for msg in new_messages:
            if not previous_msg_timestamp or (msg["time"] - previous_msg_timestamp) > chatroom_timestamp_display_threshold:
                record = {"username": None,
                       "color": "grey",
                       "message": utctolocal(msg["time"]).strftime(time_format)}
                text_lines.append(record)
            if msg["username"] in usernames:
                official_name = msg["username"]
                color = request.datamanager.get_character_color_or_none(msg["username"])
            else:  # system message
                official_name = _("system")
                color = "#666666" # medium grey, works on both light and dark backgrounds
            data = dict(official_name=official_name,
                        message=msg["message"])
            record = {"username": msg["username"],
                       "color": color,
                       "message": msg_format % data}
            text_lines.append(record)
            previous_msg_timestamp = msg["time"]

        chatting_users = sorted(request.datamanager.build_visible_character_names(request.datamanager.get_chatting_users()))

        #print("RETURNING TEXT LINES AJAX ", new_slice_index, text_lines, chatting_users)

        all_data = {"slice_index": new_slice_index,
                    "messages": text_lines,
                    'chatting_users': chatting_users, }

        response = HttpResponse(json.dumps(all_data))
        response['Content-Type'] = 'text/plain; charset=utf-8'
        response['Cache-Control'] = 'no-cache'

        return response





@register_view(access=UserAccess.authenticated, title=ugettext_lazy("Auction Chatroom"))  # game master can view too
def chatroom(request, template_name='auction/chatroom.html'):

    return render(request,
                  template_name,
                    {
                    })

