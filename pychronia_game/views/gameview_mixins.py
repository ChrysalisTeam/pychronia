# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import inspect
import json

from django.http import Http404, HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render
from django.template import RequestContext, loader

from ..datamanager import GameDataManager
from ..forms import AbstractGameForm
from pychronia_game.common import *
from pychronia_game.datamanager.datamanager_tools import transaction_watcher
from pychronia_game.datamanager.abstract_game_view import AbstractGameView, register_view



## TODO - test and move to datamanager package ####

class AbstractCaptchaProtectedView(AbstractGameView):
    """
    Protects a view with a captcha (atm no html post requests should be issues from that view, 
    else it will interfere with the captcha system).
    """

    CAPTCHA_TEMPLATE = "utilities/captcha_check.html"

    def __init__(self, *args, **kwargs):
        assert not self.GAME_ACTIONS # views protected by captchas should not use POST requests, at the moment
        return super(AbstractCaptchaProtectedView, self).__init__(*args, **kwargs)


    def _is_nightmare_captcha_successful(self):

        request = self.request

        #print (">>>>>>>>", request.POST)
        captcha_id = request.POST.get("captcha_id") # CLEAR TEXT ATM
        if captcha_id:
            attempt = request.POST.get("captcha_answer", "")
            try:
                #print (">>>>>>>>", captcha_id, attempt)
                explanation = request.datamanager.check_captcha_answer_attempt(captcha_id=captcha_id, attempt=attempt)
                assert explanation, repr(explanation)  # necessarily, if "answer" wasn't null in DB
                request.datamanager.user.add_message(_("Captcha check successful."))
                request.datamanager.user.add_message(explanation) # to please users...
                return True
            except UsageError:
                request.datamanager.user.add_error(_("Captcha check failed."))
        return False


    def _generate_captcha_page(self):

        self.DISPLAY_STATIC_CONTENT = False # IMPORTANT - hide explanations etc.

        captcha = self.request.datamanager.get_random_captcha()

        return render(self.request,
                      self.CAPTCHA_TEMPLATE,
                            {
                             'page_title': _("Security Check"),
                             'captcha': captcha
                            })


    def _process_html_request(self):
        if self._is_nightmare_captcha_successful():
            self.request.method = "GET" # dirty hack
            return super(AbstractCaptchaProtectedView, self)._process_html_request()
        else:
            return self._generate_captcha_page()


@register_view
class TestCaptcha(AbstractCaptchaProtectedView):

    TITLE = ugettext_lazy("Security Captcha")
    NAME = "test_captcha"
    TEMPLATE = "utilities/view_media.html"
    ACCESS = UserAccess.anonymous
    REQUIRES_GLOBAL_PERMISSION = False

    def get_template_vars(self, previous_form_data=None):
        return {"media_player": "IT WORKS"}

test_captcha = TestCaptcha.as_view # fixme
