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



def create_new_instance(request):

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
