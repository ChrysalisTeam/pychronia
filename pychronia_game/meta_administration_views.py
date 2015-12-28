# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os
from datetime import datetime, timedelta
import json
import traceback
import collections
import copy
import math
from smtplib import SMTPException
from contextlib import contextmanager

from django.conf import settings
from django.core.mail import mail_admins, send_mail
from django.http import Http404, HttpResponseRedirect, HttpResponse, \
     HttpResponseForbidden
from django.shortcuts import render
from django.template import RequestContext
from django.utils.html import escape
from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_lazy, ungettext
from django import forms
from django.contrib.messages import get_messages
from django.utils.http import urlencode

from pychronia_game.common import *
from pychronia_game.datamanager import datamanager_administrator
from pychronia_game.datamanager.datamanager_administrator import GAME_STATUSES
from pychronia_game import authentication
from pychronia_game.utilities import encryption
from pychronia_game.datamanager.abstract_form import SimpleForm




class GameInstanceCreationForm(SimpleForm):
    game_instance_id = forms.SlugField(label=ugettext_lazy("Game instance ID (slug)"), required=True)
    creator_login = forms.CharField(label=ugettext_lazy("Creator login"), required=True)
    creator_email = forms.EmailField(label=ugettext_lazy("Creator email"), required=False) # only required for non-superuser

    def __init__(self, require_email, *args, **kwargs):
        super(GameInstanceCreationForm, self).__init__(*args, **kwargs)
        assert hasattr(self.fields["creator_email"], "required")
        self.fields["creator_email"].required = require_email


GAME_INSTANCE_MAINTENANCE_LOCKING_DELAY_MN = 15

GAME_ACTIVATION_EMAIL_SUBJECT = ugettext_lazy("New game instance of Chrysalis RPG")
GAME_ACTIVATION_EMAIL_BODY_TPL = ugettext_lazy("""\
Dear %(creator_login)s,

here is the link that will allow you to complete the creation of your Chrysalis game, \
and to automatically sign in as the game master.

%(activation_link)s

regards,
The Chrysalis Team
""")



def compute_game_activation_token(game_instance_id, creator_login, creator_email):
    assert game_instance_id
    assert creator_login
    creator_email = creator_email or ""
    activation_data = "%s|%s|%s" % (game_instance_id, creator_login, creator_email)
    return encryption.unicode_encrypt(activation_data)

def decode_game_activation_token(activation_token):
    activation_data = encryption.unicode_decrypt(activation_token)
    (game_instance_id, creator_login, creator_email) = activation_data.split("|")
    return (game_instance_id, creator_login, creator_email or None)


def _build_activation_url(**kwargs):
    token = compute_game_activation_token(**kwargs)
    activation_link = config.SITE_DOMAIN + reverse(activate_instance) + "?" + urlencode(dict(token=token))
    return activation_link


# no authentication!
def create_instance(request):
    """
    Workflow to create an instance through email validation, for non-superusers.
    """
    require_email = True # important

    game_creation_form = None

    information = _("Please provide a valid email address, so that we can send you the activation link for your new game. "
                    "If after several attempts you don't manage to create your game, please contact the game staff. ")

    if request.method == "POST":

        game_creation_form = GameInstanceCreationForm(require_email=require_email, data=request.POST)
        if game_creation_form.is_valid():
            cleaned_data = game_creation_form.cleaned_data
            game_instance_id = cleaned_data["game_instance_id"]
            creator_login = cleaned_data["creator_login"]
            creator_email = cleaned_data["creator_email"] or None

            if datamanager_administrator.game_instance_exists(game_instance_id):
                messages.add_message(request, messages.ERROR, _(u"Please choose another game identifier."))

            else:

                activation_link = _build_activation_url(game_instance_id=game_instance_id, creator_login=creator_login, creator_email=creator_email)

                message = GAME_ACTIVATION_EMAIL_BODY_TPL % locals()

                try:
                    send_mail(subject=GAME_ACTIVATION_EMAIL_SUBJECT,
                              message=message,
                              from_email=settings.SERVER_EMAIL,
                              recipient_list=[creator_email],
                              fail_silently=False)
                except (SMTPException, EnvironmentError), e:
                    logging.error("Couldn't send game instance activation email to %s", creator_email, exc_info=True)
                    messages.add_message(request, messages.ERROR, _(u"Couldn't send activation email."))
                else:
                    messages.add_message(request, messages.INFO, _(u"Game instance '%(game_instance_id)s' successfully created for '%(creator_login)s/%(creator_email)s'") %
                                         SDICT(game_instance_id=game_instance_id, creator_login=creator_login, creator_email=creator_email))
                    game_creation_form = None
                    information = _("The activation email has been sent to %(creator_email)s.") % SDICT(creator_email=creator_email)

                if settings.DEBUG and request.GET.get("_debug_"): # even if we haven't managed to send the activation email
                    information += " " + _("Debug Information: [%(activation_link)s].") % SDICT(activation_link=activation_link)
        else:
            messages.add_message(request, messages.ERROR, _(u"Invalid game creation form submitted."))


    return render(request,
                  "meta_administration/create_instance.html",
                    {
                     'notifications': get_messages(request),
                     'game_creation_form': game_creation_form or GameInstanceCreationForm(require_email=require_email),
                     'information': information,
                    })


def activate_instance(request):

    token = request.GET.get("token", "")

    try:
        encrypted_data = token.encode("ascii") # encrypted json containing the game id, the user login and a validity timestamp
        (game_instance_id, creator_login, creator_email) = decode_game_activation_token(encrypted_data)

        if not datamanager_administrator.game_instance_exists(game_instance_id):
            datamanager_administrator.create_game_instance(game_instance_id=game_instance_id,
                                                           creator_login=creator_login,
                                                           creator_email=creator_email,
                                                           skip_randomizations=False)
        else:
            metadata = datamanager_administrator.get_game_instance_metadata_copy(game_instance_id) # shall NOT raise errors
            if (metadata["creator_login"] != creator_login or metadata["creator_email"] != creator_email):
                raise ValueError("Creator data doesn't match for game instance %(game_instance_id)s" % SDICT(game_instance_id=game_instance_id))

        # we retrieve the datamanager whatever its possible maintenance status
        dm = datamanager_administrator.retrieve_game_instance(game_instance_id, request=None, metadata_checker=lambda *args, **kwargs: True)
        master_login = dm.get_global_parameter("master_login")

        authentication_token = authentication.compute_enforced_login_token(game_instance_id=game_instance_id, login=master_login, is_observer=False)
        session_token_display = urlencode({authentication.ENFORCED_SESSION_TICKET_NAME: authentication_token})

        import pychronia_game.views
        target_url = config.SITE_DOMAIN + reverse(pychronia_game.views.homepage, kwargs=dict(game_instance_id=game_instance_id, game_username=master_login))
        target_url += "?" + session_token_display

        content = _("In case you don't get properly redirected, please copy this link into our URL bar: %(target_url)s") % SDICT(target_url=target_url)
        return HttpResponseRedirect(target_url, content=content)

    except (ValueError, TypeError, LookupError, AttributeError, UnicodeError), e:
        logging.warning("Game activation key not recognized : %s", token, exc_info=True)
        return HttpResponseForbidden(_("Activation key not recognized"))



@superuser_required
def manage_instances(request):

    session_token_display = None
    game_creation_form = None
    require_email = False # superuser does what he wants

    try:
        if request.method == "POST":

            if request.POST.get("create_game_instance"):
                game_creation_form = GameInstanceCreationForm(require_email=require_email, data=request.POST)
                if game_creation_form.is_valid():
                    cleaned_data = game_creation_form.cleaned_data
                    game_instance_id = cleaned_data["game_instance_id"]
                    creator_login = cleaned_data["creator_login"]
                    creator_email = cleaned_data["creator_email"] or None
                    datamanager_administrator.create_game_instance(game_instance_id=game_instance_id,
                                                                     creator_login=creator_login,
                                                                     creator_email=creator_email,
                                                                     skip_randomizations=False)
                    messages.add_message(request, messages.INFO, _(u"Game instance '%(game_instance_id)s' successfully created for '%(creator_login)s/%(creator_email)s'") %
                                                                    SDICT(game_instance_id=game_instance_id, creator_login=creator_login, creator_email=creator_email))
                    game_creation_form = None
                else:
                    messages.add_message(request, messages.ERROR, _(u"Invalid game creation form submitted."))
            elif request.POST.get("lock_instance"):
                game_instance_id = request.POST["lock_instance"]
                maintenance_until = datetime.utcnow() + timedelta(minutes=GAME_INSTANCE_MAINTENANCE_LOCKING_DELAY_MN)
                datamanager_administrator.change_game_instance_status(game_instance_id=game_instance_id, maintenance_until=maintenance_until)
                messages.add_message(request, messages.INFO, _(u"Game instance '%(game_instance_id)s' successfully locked") % SDICT(game_instance_id=game_instance_id))
            elif request.POST.get("unlock_instance"):
                game_instance_id = request.POST["unlock_instance"]
                datamanager_administrator.change_game_instance_status(game_instance_id=game_instance_id, maintenance_until=None) # removes maintenance
                messages.add_message(request, messages.INFO, _(u"Game instance '%(game_instance_id)s' successfully unlocked") % SDICT(game_instance_id=game_instance_id))
            elif request.POST.get("change_instance_status"):
                game_instance_id = request.POST["change_instance_status"]
                new_status = request.POST["new_status"]
                datamanager_administrator.change_game_instance_status(game_instance_id=game_instance_id, new_status=new_status) # change status
                messages.add_message(request, messages.INFO, _(u"Game instance '%(game_instance_id)s' status changed to '%(new_status)s'") % SDICT(game_instance_id=game_instance_id, new_status=new_status))
            elif request.POST.get("delete_game_instance"):
                game_instance_id = request.POST["delete_game_instance"]
                datamanager_administrator.delete_game_instance(game_instance_id=game_instance_id)
                messages.add_message(request, messages.INFO, _(u"Game instance '%(game_instance_id)s' was deleted") % SDICT(game_instance_id=game_instance_id))
            elif request.POST.get("backup_game_instance"):
                game_instance_id = request.POST["backup_game_instance"]
                backup_comment = slugify(request.POST["backup_comment"].strip()) or None
                datamanager_administrator.backup_game_instance_data(game_instance_id=game_instance_id, comment=backup_comment)
                messages.add_message(request, messages.INFO, _(u"Game instance '%(game_instance_id)s' backup with comment '%(backup_comment)s' done") %
                                                               SDICT(game_instance_id=game_instance_id, backup_comment=(backup_comment or u"<empty>")))
            elif request.POST.get("compute_enforced_session_ticket"):
                game_instance_id = request.POST["game_instance_id"].strip() # manually entered
                login = request.POST["login"].strip()
                is_observer = bool(request.POST.get("is_observer"))
                authentication_token = authentication.compute_enforced_login_token(game_instance_id=game_instance_id, login=login, is_observer=is_observer)
                messages.add_message(request, messages.INFO, _(u"Auto-connection token for instance=%(game_instance_id)s, login=%(login)s and is_observer=%(is_observer)s is displayed below") %
                                                               SDICT(game_instance_id=game_instance_id, login=login, is_observer=is_observer))
                session_token_display = urlencode({authentication.ENFORCED_SESSION_TICKET_NAME: authentication_token})
            else:
                raise ValueError(_("Unknown admin action"))

    except Exception as e:
        messages.add_message(request, messages.ERROR, _(u"Unexpected error: %s") % e)

    instances_metadata = datamanager_administrator.get_all_instances_metadata()

    for _meta in instances_metadata:
        _activation_link = _build_activation_url(game_instance_id=_meta["instance_id"], creator_login=_meta["creator_login"], creator_email=_meta["creator_email"])
        _meta["activation_link"] = _activation_link

    return render(request,
                  "meta_administration/manage_instances.html",
                    {
                     'instances_metadata': instances_metadata, # enriched info
                     'utc_now': datetime.utcnow(),
                     'notifications': get_messages(request),
                     'possible_game_statuses': sorted(GAME_STATUSES),
                     'deletable_statuses': [GAME_STATUSES.terminated, GAME_STATUSES.aborted],
                     'game_creation_form': game_creation_form or GameInstanceCreationForm(require_email=require_email),
                     'session_token_display': session_token_display,
                    })


@superuser_required
def edit_instance_db(request, target_instance_id):

    ## FIXME - add check on game status = maintenance here!!!

    special_message = None
    formatted_data = None
    editing_allowed = True

    try:

        if request.method == "POST" and request.POST.get("db_content"):

            yaml_input = request.POST["db_content"]
            formatted_data = yaml_input # by default, we redisplay buggy content

            dm = datamanager_administrator.retrieve_game_instance(game_instance_id=target_instance_id, request=None,
                                                                  metadata_checker=datamanager_administrator.check_game_is_in_maintenance)

            try:
                data_tree = dm.load_zope_database_from_string(yaml_input) # checks data
            except Exception as e:
                messages.add_message(request, messages.ERROR, _(u"Data check error (%(exception)r), see details below.") % SDICT(exception=e))
                special_message = traceback.format_exc()
                formatted_data = None # we force refresh of data
            else:
                datamanager_administrator.replace_existing_game_instance_data(target_instance_id, new_data=data_tree)
                messages.add_message(request, messages.INFO, _(u"Game instance data was properly replaced."))

        if not formatted_data: # even if success occurred
            if not special_message:
                special_message = _("Current DB content is displayed here for editing.")
            dm = datamanager_administrator.retrieve_game_instance(game_instance_id=target_instance_id, request=None,
                                                                  metadata_checker=datamanager_administrator.check_game_is_in_maintenance)
            formatted_data = dm.dump_zope_database(width=90)

    except GameMaintenanceError, e:
        # formatted_data might remain as yaml_input
        messages.add_message(request, messages.ERROR, unicode(e))
        editing_allowed = False
        special_message = _("DB modification is now forbidden, please stash your potential modifications elsewhere and begin the process again.")

    return render(request,
                  "meta_administration/edit_instance_db.html",
                    {
                     'target_instance_id': target_instance_id,
                     'special_message': special_message,
                     'editing_allowed': editing_allowed, # FIXME - make it dynamic depending on context - MSG ""
                     'formatted_data': formatted_data,
                     'notifications': get_messages(request),
                    })


'''
def lock_and_edit_instance_db(request, game_instance_id):
    
    
    if request.method=POST:
        new_db_json = request.POSt.get(request
                                       utilities.convert_object_tree(self.data[key], utilities.python_to_zodb_types)
    

    
    
    
    formatted_data = request.datamanager.dump_zope_database(width=100)
    '''











