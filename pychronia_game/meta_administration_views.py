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
import fileservers
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
                                                           master_real_email="?????",
                                                           master_login="????",
                                                           master_password="????????")

        except (ValueError, TypeError, LookupError, AttributeError):
            return HttpResponseForbidden("Access key not recognized")




# TODO @superuser_required
def manage_instances(request):

    try:
        if request.method == "POST":

            if request.POST.get("lock_instance"):
                game_instance_id = request.POST.get("lock_instance")
                maintenance_until = datetime.utcnow() + timedelta(minutes=GAME_INSTANCE_MAINTENANCE_LOCKING_DELAY_MN)
                datamanager_administrator.change_game_instance_status(game_instance_id=game_instance_id, maintenance_until=maintenance_until)
            elif request.POST.get("unlock_instance"):
                game_instance_id = request.POST.get("unlock_instance")
                datamanager_administrator.change_game_instance_status(game_instance_id=game_instance_id, maintenance_until=None) # removes maintenance
            else:
                raise ValueError(_("Unknwon admin action"))

    except Exception as e:
        messages.add_message(request, messages.ERROR, _(u"Unexpected error: %s") % e)
        raise # FIXME REMOVE THIS

    instances_metadata = datamanager_administrator.get_all_instances_metadata()


    return render(request,
                  "meta_administration/manage_instances.html",
                    {
                     'instances_metadata': instances_metadata,
                     'utc_now': datetime.utcnow()
                    })


# TODO @superuser_required
def edit_instance_db(request, target_instance_id):

    ## FIXME - add check on game status = maintenance here!!!

    

    if request.method == "POST" and request.POST.get("db_content"):

        yaml_input = request.POST["db_content"]
        dm = datamanager_administrator.retrieve_game_instance(game_instance_id=target_instance_id, request=None, force=True)

        try:
            data_tree = dm.load_zope_database(yaml_input) # checks data
        except Exception as e:
            messages.add_message(request, messages.ERROR, _(u"Data error: %s") % e)
            raise # FIXME REMOVE THIS
        else:
            datamanager_administrator.replace_game_instance_data(target_instance_id, new_data=data_tree)
            messages.add_message(request, messages.INFO, _(u"Game instance data was properly replaced."))
            formatted_data = None

    else:

        dm = datamanager_administrator.retrieve_game_instance(game_instance_id=target_instance_id, request=None, force=True)

        formatted_data = dm.dump_zope_database(width=90)

    return render(request,
                  "meta_administration/edit_instance_db.html",
                    {
                     'editing_allowed': True, # FIXME - make it dynamic
                     'formatted_data': formatted_data,
                    })


'''
def lock_and_edit_instance_db(request, game_instance_id):
    
    
    if request.method=POST:
        new_db_json = request.POSt.get(request
                                       utilities.convert_object_tree(self.data[key], utilities.python_to_zodb_types)
    

    
    
    
    formatted_data = request.datamanager.dump_zope_database(width=100)
    '''











