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

from contextlib import contextmanager
from django.conf import settings
from django.core.mail import mail_admins
from django.http import Http404, HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden
from django.shortcuts import render
from django.template import RequestContext
from django.utils.html import escape
from django.utils.translation import ugettext as _, ugettext_lazy as _lazy, ungettext
from pychronia_game.common import *
from pychronia_game.datamanager import datamanager_administrator
import math



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





def manage_instances(request):

    instances_metadata = datamanager_administrator.get_all_instances_metadata()


    return render(request,
                  "meta_administration/manage_instances.html",
                    {
                     'instances_metadata': instances_metadata,
                    })


'''
def lock_and_edit_instance_db(request, game_instance_id):
    
    
    if request.method=POST:
        new_db_json = request.POSt.get(request
                                       utilities.convert_object_tree(self.data[key], utilities.python_to_zodb_types)
    
    maintenance_until = datetime.utcnow() + timedelta(minutes=GAME_INSTANCE_MAINTENANCE_LOCKING_DELAY_MN)
    
    datamanager_administrator.change_game_instance_status(game_instance_id=game_instance_id, maintenance_until=maintenance_until)
    
    
    
    formatted_data = request.datamanager.dump_zope_database(width=100)
    '''











