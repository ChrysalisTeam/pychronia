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






@register_view
class FriendshipManagementAbility(AbstractGameView):


    NAME = "friendship_management"

    GAME_FORMS = {}
    ACTIONS = {"propose_friendship": "do_propose_friendship",
               "accept_friendship": "do_accept_friendship",
               "cancel_friendship": "do_cancel_friendship"}

    ADMIN_FORMS = {}

    TEMPLATE = "generic_operations/friendship_management.html"

    ACCESS = UserAccess.character
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    def get_template_vars(self, previous_form_data=None):

        username = self.datamanager.user.username
        friendship_statuses = self.datamanager.get_other_characters_friendship_statuses(username)
        friendship_statuses = sorted(friendship_statuses.items()) # list of pairs (other_username, relation_type) 

        return {
                 'page_title': _("Friendship Management"),
                 "friendship_statuses": friendship_statuses,
               }



    def do_propose_friendship(self, other_username):
        res = self.datamanager.propose_friendship(proposer=self.datamanager.user.username,
                                                  recipient=other_username)
        if res:
            return _("You're now friend with %s, as that user concurrently proposed friendship too.") % other_username # should be fairly rare
        else:
            return _("Your friendship proposal to %s has been recorded.") % other_username


    def do_accept_friendship(self, other_username):
        res = self.datamanager.propose_friendship(proposer=self.datamanager.user.username,
                                                  recipient=other_username)
        if res:
            return _("You're now friend with %s.") % other_username
        else:
            return _("Your friendship proposal to user %s has been recorded, as he has cancelled his own friendship proposal.") % other_username  # should be fairly rare


    def do_cancel_friendship(self, other_username):

        if not self.datamanager.are_friends(username1=self.datamanager.user.username,
                                            username2=other_username):
            return _("You're not friend anymore with user %s, as he's concurrently canceled his firendship with you") % other_username

        self.datamanager.terminate_friendship(username1=self.datamanager.user.username,
                                              username2=other_username)
        return _("Your friendship with %s has been properly canceled.") % other_username


friendship_management = FriendshipManagementAbility.as_view



