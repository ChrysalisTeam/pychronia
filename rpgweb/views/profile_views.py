# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import AbstractGameView, register_view, AbstractGameForm
from rpgweb.authentication import try_authenticating_with_credentials, logout_session
from django.http import HttpResponseRedirect
from rpgweb import forms


@register_view(access=UserAccess.anonymous, always_available=True, title=_lazy("Login"))
def login(request, template_name='registration/login.html'):

    form = None
    user = request.datamanager.user

    if request.method == "POST":
        if not request.session.test_cookie_worked():
            user.add_error(_("Your Web browser might have cookies disabled. Cookies are required to properly log in."))

        form = forms.AuthenticationForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data["secret_username"].strip()
            password = form.cleaned_data["secret_password"].strip()

            if request.POST.get("password_forgotten", None): # password recovery system
                with action_failure_handler(request, success_message=None):
                    request.datamanager.get_secret_question(username)  # check that it's OK
                    return HttpResponseRedirect(reverse(secret_question, kwargs=dict(game_instance_id=request.datamanager.game_instance_id, concerned_username=username)))

            else:  # normal authentication
                with action_failure_handler(request, _("You've been successfully logged in.")):  # message won't be seen because of redirect...
                    try_authenticating_with_credentials(request, username, password)
                    return HttpResponseRedirect(reverse("rpgweb-homepage", kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))

    else:
        request.session.set_test_cookie()
        form = forms.AuthenticationForm()

    return render(request,
                  template_name,
                    {
                     'page_title': _("User Authentication"),
                     'login_form': form
                    })


@register_view(access=UserAccess.authenticated, always_available=True, title=_lazy("Logout"))
def logout(request, template_name='registration/logout.html'):

    logout_session(request)

    user = request.datamanager.user  # better to take user only NOW, after logout
    user.add_message(_("You've been successfully logged out."))
    return HttpResponseRedirect(reverse(login, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))




@register_view(access=UserAccess.anonymous, title=_lazy("Password Recovery"))
def secret_question(request, concerned_username, template_name='registration/secret_question.html'):

    secret_question = None
    form = None

    try:
        secret_question = request.datamanager.get_secret_question(concerned_username)
    except UsageError:
        request.datamanager.user.add_error(_("You must provide a valid username to recover your password"))
        return HttpResponseRedirect(reverse("rpgweb-homepage", kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))


    if request.method == "POST" and request.POST.get("recover", None):

        # WARNING - manual validation, so that secret answer is checked BEFORE email address
        secret_answer_attempt = request.POST.get("secret_answer", None)
        if secret_answer_attempt:
            secret_answer_attempt = secret_answer_attempt.strip()
        target_email = request.POST.get("target_email", None)
        if target_email:
            target_email = target_email.strip()

        with action_failure_handler(request, _("Your password has been successfully emailed to your backup address.")):
            try:
                request.datamanager.process_secret_answer_attempt(concerned_username, secret_answer_attempt, target_email)  # raises error on bad answer/email
                # success
                secret_question = None
                form = None

            except:
                form = forms.SecretQuestionForm(concerned_username, data=request.POST)
                form.full_clean()
                raise

    else:
        form = forms.SecretQuestionForm(concerned_username)

    assert (not form and not secret_question) or (form and secret_question)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Password Recovery"),
                     'concerned_username': concerned_username,
                     'secret_question': secret_question,
                     'secret_question_form': form,
                    })









@register_view
class CharacterProfile(AbstractGameView):

    TITLE = _lazy("Personal Profile")
    NAME = "character_profile"
    TEMPLATE = "registration/character_profile.html"
    ACCESS = UserAccess.character
    ALWAYS_AVAILABLE = True

    GAME_ACTIONS = dict(password_change_form=dict(title=_lazy("Change password"),
                                                          form_class=forms.PasswordChangeForm,
                                                          callback="process_password_change_form"))

                                                          
    def get_template_vars(self, previous_form_data=None):

        character_properties = self.datamanager.get_character_properties()

        password_change_form = self._instantiate_game_form(new_action_name="password_change_form",
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

        self.datamanager.process_password_change_attempt(self.datamanager.user.username,
                                                         old_password=old_password,
                                                         new_password=new_password1)

        return _("Password change successfully performed.")

character_profile = CharacterProfile.as_view






@register_view
class FriendshipManagementAbility(AbstractGameView):

    TITLE = _lazy("Friendship Management")
    NAME = "friendship_management"

    GAME_ACTIONS = dict(do_propose_friendship=dict(title=_lazy("Propose friendship"),
                                                          form_class=None,
                                                          callback="do_propose_friendship"),
                        do_accept_friendship=dict(title=_lazy("Accept friendship"),
                                                          form_class=None,
                                                          callback="do_accept_friendship"),
                        do_cancel_proposal=dict(title=_lazy("Cancel friendship proposal"),
                                                          form_class=None,
                                                          callback="do_cancel_proposal"),
                        do_cancel_friendship=dict(title=_lazy("Cancel friendship"),
                                                          form_class=None,
                                                          callback="do_cancel_friendship"))

    TEMPLATE = "generic_operations/friendship_management.html"

    ACCESS = UserAccess.character
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    def _relation_type_to_action(self, relation_type):
        if relation_type == "proposed_to":
            return ("do_cancel_proposal", _("Cancel friendship proposal"), _("You've proposed a friendship to that user"))
        elif relation_type == "requested_by":
            return ("do_accept_friendship", _("Accept friendship proposal"), _("You've been proposed a friendship by that user"))
        elif relation_type == "recent_friend":
            return (None, None, _("You've been friend with that user for a short time (impossible to break that friendship at the moment)"))
        elif relation_type == "old_friend":
            return ("do_cancel_friendship", _("Abort friendship proposal"), _("You're friends with that user"))
        else:
            assert relation_type is None, repr(relation_type)
            return ("do_propose_friendship", _("Propose friendship"), _("You're not friends with that user"))


    def get_template_vars(self, previous_form_data=None):

        friendship_statuses = self.datamanager.get_other_characters_friendship_statuses()

        friendship_actions = sorted([(other_username, self._relation_type_to_action(relation_type))
                                     for (other_username, relation_type) in friendship_statuses.items()]) # list of pairs (other_username, relation_type)

        return {
                 'page_title': _("Friendship Management"),
                 'current_friends': self.datamanager.get_friends(),
                 "friendship_actions": friendship_actions,
               }

    def do_propose_friendship(self, other_username):
        res = self.datamanager.propose_friendship(recipient=other_username)
        if res:
            return _("You're now friend with %s, as that user concurrently proposed friendship too.") % other_username # should be fairly rare
        else:
            return _("Your friendship proposal to %s has been recorded.") % other_username


    def do_accept_friendship(self, other_username):
        res = self.datamanager.propose_friendship(recipient=other_username)
        if res:
            return _("You're now friend with %s.") % other_username
        else:
            return _("Your friendship proposal to user %s has been recorded, since he has cancelled his own friendship proposal.") % other_username  # should be fairly rare


    def do_cancel_proposal(self, other_username):

        res = self.datamanager.terminate_friendship(rejected_user=other_username) # might raise exception if (rare) concurrent cancelation occurred
        if res:
            return _("Your friendship with %s has been properly canceled, as he had accepted it concurrently.") % other_username
        else:

            return _("Your friendship proposal to user %s has been properly canceled.") % other_username


    def do_cancel_friendship(self, other_username):

        res = self.datamanager.terminate_friendship(rejected_user=other_username) # might raise exception if (rare) concurrent cancelation occurred
        if res:
            return _("Your friendship with %s has been properly canceled.") % other_username
        else:
            return _("Your friendship proposal to user %s has been properly canceled.") % other_username  # weirdest case...


friendship_management = FriendshipManagementAbility.as_view

