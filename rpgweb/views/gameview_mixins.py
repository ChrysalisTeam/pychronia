# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import inspect
import json

from django.http import Http404, HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render
from django.template import RequestContext, loader

from ..datamanager import GameDataManager
from ..forms import AbstractGameForm
from rpgweb.common import *
from rpgweb.datamanager.datamanager_tools import transaction_watcher
from ._abstract_game_view import AbstractGameView
from rpgweb.views._abstract_game_view import register_view



class AbstractCaptchaProtectedView(AbstractGameView):
    
    CAPTCHA_TEMPLATE = "utilities/captcha_check.html"
    
    def _is_nightmare_captcha_successful(self):
        
        request = self.request
        
        #print (">>>>>>>>", request.POST)
        captcha_id = request.POST.get("captcha_id") # CLEAR TEXT ATM
        if captcha_id:
            attempt = request.POST.get("captcha_answer", "")
            try:
                #print (">>>>>>>>", captcha_id, attempt)
                explanation = request.datamanager.check_captcha_answer_attempt(captcha_id=captcha_id, attempt=attempt)
                del explanation # how can we display it, actually ?
                request.datamanager.user.add_message(_("Captcha check successful"))
                return True
            except UsageError:
                request.datamanager.user.add_error(_("Captcha check failed"))
        return False
        
    def _generate_captcha_page(self):
    
        captcha = self.request.datamanager.get_random_captcha()
        
        return render(self.request,
                      self.CAPTCHA_TEMPLATE,
                            {
                             'page_title': _("Security Check"),
                             'captcha': captcha
                            })

    def _process_html_request(self):   
        if self._is_nightmare_captcha_successful():
            return super(AbstractCaptchaProtectedView, self)._process_html_request()
        else:
            return self._generate_captcha_page()
            
            
@register_view
class TestCaptcha(AbstractCaptchaProtectedView):
    
    NAME = "test_captcha"
    TEMPLATE = "utilities/view_media.html"    
    ACCESS = UserAccess.anonymous
    ALWAYS_AVAILABLE = True
    
    def get_template_vars(self, previous_form_data=None):
        return {"media_player": "IT WORKS"}

