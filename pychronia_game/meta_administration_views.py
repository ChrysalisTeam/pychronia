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

from contextlib import contextmanager
from django.conf import settings
from django.core.mail import mail_admins
from django.http import Http404, HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden
from django.shortcuts import render
from django.template import RequestContext
from django.utils.html import escape
from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_lazy as _lazy, ungettext
from pychronia_game.common import *
from pychronia_game.datamanager import datamanager_administrator
from django.contrib.messages import get_messages






GAME_INSTANCE_MAINTENANCE_LOCKING_DELAY_MN = 15


def ____create_new_instance(request):  # TODO FINISH LATER

    if request.method != "POST":

        try:
            encrypted_data = request.POST["data"] # encrypted json containing the game id, the user login and a validity timestamp
            data = unicode_decrypt(encrypted_data)
            data_dict = json.loads(data)

            if math.fabs((datetime.utcnow() - data_dict["generation_time"]).days) > 1:
                raise ValueError("Outdated access key")

            game_instance_id = data_dict["game_instance_id"]
            creator_portal_login = data_dict["creator_portal_login"] # FIXME put into metadata

            datamanager_administrator.create_game_instance(game_instance_id=game_instance_id,
                                                           creator_login="??????",
                                                           master_real_email="?????",
                                                           master_login="????",
                                                           master_password="????????")

        except (ValueError, TypeError, LookupError, AttributeError):
            return HttpResponseForbidden("Access key not recognized")




@superuser_required
def manage_instances(request):

    try:
        if request.method == "POST":

            if request.POST.get("lock_instance"):
                game_instance_id = request.POST["lock_instance"]
                maintenance_until = datetime.utcnow() + timedelta(minutes=GAME_INSTANCE_MAINTENANCE_LOCKING_DELAY_MN)
                datamanager_administrator.change_game_instance_status(game_instance_id=game_instance_id, maintenance_until=maintenance_until)
                messages.add_message(request, messages.INFO, _(u"Game instance successfully locked"))
            elif request.POST.get("unlock_instance"):
                game_instance_id = request.POST["unlock_instance"]
                datamanager_administrator.change_game_instance_status(game_instance_id=game_instance_id, maintenance_until=None) # removes maintenance
                messages.add_message(request, messages.INFO, _(u"Game instance successfully unlocked"))
            else:
                raise ValueError(_("Unknown admin action"))

    except Exception as e:
        messages.add_message(request, messages.ERROR, _(u"Unexpected error: %s") % e)

    instances_metadata = datamanager_administrator.get_all_instances_metadata()


    return render(request,
                  "meta_administration/manage_instances.html",
                    {
                     'instances_metadata': instances_metadata,
                     'utc_now': datetime.utcnow(),
                     'notifications': get_messages(request),
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
                data_tree = dm.load_zope_database(yaml_input) # checks data
            except Exception as e:
                messages.add_message(request, messages.ERROR, _(u"Data check error, see details below.") % e)
                special_message = traceback.format_exc()
                formatted_data = None # we force refresh of data
            else:
                datamanager_administrator.replace_game_instance_data(target_instance_id, new_data=data_tree)
                messages.add_message(request, messages.INFO, _(u"Game instance data was properly replaced."))

        if not formatted_data: # even if success occurred
            assert not special_message
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











