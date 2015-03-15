# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _

from userprofiles.forms import RegistrationForm as DefaultRegistrationForm
from pychronia_cms.models import Profile




# OUTDATED - DOESN'T SUPPORT DJANGO1.7 DUE TO SORTEDICT

class RegistrationForm(DefaultRegistrationForm):

    antibot_check = forms.CharField(label=_('How much is "2 * 7" (in digits)?'), required=True)

    def clean_antibot_check(self):

        antibot_check = self.cleaned_data['antibot_check'].strip().lower()

        if antibot_check != "14" and antibot_check != "fourteen":
            raise forms.ValidationError(_(u'Improper answer to special question.'))

        return antibot_check


    def save_profile(self, new_user, *args, **kwargs):
        """
        Called by RegistrationForm.save().
        """
        Profile.objects.get_or_create(user=new_user)

