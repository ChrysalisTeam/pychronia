# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.views._abstract_game_view import *



class PasswordChangeForm(AbstractGameForm):

    old_password = forms.CharField(label=_lazy("Current password"), required=True, widget=forms.PasswordInput)
    new_password1 = forms.CharField(label=_lazy("New password"), required=True, widget=forms.PasswordInput)
    new_password2 = forms.CharField(label=_lazy("New password (again)"), required=True, widget=forms.PasswordInput)
        
    def clean(self):
        cleaned_data = super(PasswordChangeForm, self).clean()
        
        new_password1 = cleaned_data.get("new_password1") # might be None
        new_password2 = cleaned_data.get("new_password2") # might be None

        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError(_("New passwords not matching"))

        # Always return the full collection of cleaned data.
        return cleaned_data
      
      
      
@register_view
class CharacterProfile(AbstractGameView):
    
    NAME = "character_profile"
    TEMPLATE = "registration/character_profile.html"    
    ACCESS = UserAccess.character
    ALWAYS_AVAILABLE = True
    
    GAME_FORMS = {"password_change_form": (PasswordChangeForm, "process_password_change_form")}
    

    def get_template_vars(self, previous_form_data=None):
    
        character_properties = self.datamanager.get_character_properties(self.datamanager.user.username)
        
        password_change_form = self._instantiate_form(new_form_name="password_change_form", 
                                                      hide_on_success=False,
                                                      previous_form_data=previous_form_data)

        return {
                 'page_title': _("User Profile"),
                 "character_properties": character_properties,
                 'password_change_form': password_change_form,
               }
    
    
    def process_password_change_form(self, old_password, new_password1, new_password2):
        assert old_password and new_password1 and new_password2
        assert self.datamanager.user.is_character
        
        if new_password1 != new_password2:
            raise AbnormalUsageError(_("New passwords not matching")) # will be logged as critical - shouldn't happen due to form checks
        
        self.datamanager.process_password_change_attempt(self.datamanager.user.username, old_password, new_password1)
        
        return _("Password change successfully performed.") 

character_profile = CharacterProfile.as_view 



