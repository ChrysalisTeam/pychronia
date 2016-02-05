# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager import AbstractGameView, register_view, AbstractGameForm, transaction_watcher
from pychronia_game.authentication import try_authenticating_with_credentials, logout_session
from django.http import HttpResponseRedirect
from pychronia_game import forms
from django import forms as django_forms
from pychronia_game.utilities.select2_extensions import Select2TagsField



class FriendshipMinDurationForm(AbstractGameForm):

    duration_mn = django_forms.IntegerField(label=ugettext_lazy("Set minimum friendship duration in minutes"), max_value=60 * 24 * 30, min_value=0, required=True)

    def __init__(self, datamanager, *args, **kwargs):
        super(FriendshipMinDurationForm, self).__init__(datamanager, *args, **kwargs)
        self.fields['duration_mn'].initial = datamanager.get_global_parameter("friendship_minimum_duration_mn_abs")



@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Login"), always_allow_post=True)
def login(request, template_name='profile/login.html'):

    form = None
    user = request.datamanager.user
    next_url = request.REQUEST.get("next", "")

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
                    return HttpResponseRedirect(game_view_url(secret_question,
                                                              datamanager=request.datamanager,
                                                              concerned_username=username))

            else:  # normal authentication
                with action_failure_handler(request, _("You've been successfully logged in.")):  # message won't be seen because of redirect...
                    try_authenticating_with_credentials(request, username, password)
                    if next_url:
                        _target_url = next_url
                    else:
                        _target_url = game_view_url("pychronia_game-homepage", datamanager=request.datamanager)
                    return HttpResponseRedirect(_target_url) # handy

    else:
        request.session.set_test_cookie()
        form = forms.AuthenticationForm()

    assert isinstance(next_url, basestring) # not NONE, else pb when displaying it!
    return render(request,
                  template_name,
                    {
                     'page_title': _("User Authentication"),
                     'login_form': form,
                     'next_url': next_url,
                    })


@register_view(access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("Logout"), always_allow_post=True)
def logout(request):

    logout_session(request)

    user = request.datamanager.user  # better to take user only NOW, after logout
    user.add_message(_("You've been successfully logged out."))
    return HttpResponseRedirect(game_view_url(login, datamanager=request.datamanager))




@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Password Recovery"))
def secret_question(request, concerned_username, template_name='profile/secret_question.html'):

    secret_question = None
    form = None

    try:
        secret_question = request.datamanager.get_secret_question(concerned_username)
    except UsageError:
        request.datamanager.user.add_error(_("You must provide a valid username to recover your password"))
        return HttpResponseRedirect(game_view_url("pychronia_game-homepage", datamanager=request.datamanager))


    if request.method == "POST" and request.POST.get("recover", None):

        # WARNING - manual validation, so that secret answer is checked BEFORE email address
        secret_answer_attempt = request.POST.get("secret_answer", None)
        if secret_answer_attempt:
            secret_answer_attempt = secret_answer_attempt.strip()
        target_email = request.POST.get("target_email", None)
        if target_email:
            target_email = target_email.strip()

        with action_failure_handler(request, _("Your password will be emailed to your backup address as soon as possible.")):
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

    TITLE = ugettext_lazy("Personal Profile")
    NAME = "character_profile"
    TEMPLATE = "profile/character_profile.html"
    ACCESS = UserAccess.character
    REQUIRES_GLOBAL_PERMISSION = False

    GAME_ACTIONS = dict(password_change_form=dict(title=ugettext_lazy("Change password"),
                                                          form_class=forms.PasswordChangeForm,
                                                          callback="process_password_change_form"))


    def get_template_vars(self, previous_form_data=None):

        character_properties = self.datamanager.get_character_properties()

        password_change_form = self._instantiate_game_form(new_action_name="password_change_form",
                                                      hide_on_success=False,
                                                      previous_form_data=previous_form_data)

        user_gems = [x[0] for x in character_properties["gems"]]
        user_artefacts = [value["title"] for (key, value) in self.datamanager.get_user_artefacts().items()]

        return {
                 'page_title': _("User Profile"),
                 'character_properties': character_properties,
                 'user_gems': user_gems,
                 'user_artefacts': user_artefacts,
                 'password_change_form': password_change_form,
               }


    def process_password_change_form(self, old_password, new_password1, new_password2, use_gems=()):
        assert old_password and new_password1 and new_password2
        assert self.datamanager.user.is_character

        if new_password1 != new_password2:
            raise AbnormalUsageError(_("New passwords not matching")) # will be logged as critical - shouldn't happen due to form checks

        self.datamanager.process_password_change_attempt(self.datamanager.user.username,
                                                         old_password=old_password,
                                                         new_password=new_password1)

        self.datamanager.log_game_event(ugettext_noop("User account password has been changed."),
                                         url=None,
                                         visible_by=[self.datamanager.username])

        return _("Password change successfully performed.")

character_profile = CharacterProfile.as_view





class FriendshipRequestForm(AbstractGameForm):

    other_username = None # django_forms.CharField(label=ugettext_lazy("User Identifier"), required=True)

    def __init__(self, datamanager, *args, **kwargs):
        super(FriendshipRequestForm, self).__init__(datamanager, *args, **kwargs)

        field_name = "other_username"
        self.fields[field_name] = Select2TagsField(label=_("User Identifier"), required=True)
        self.fields[field_name].choice_tags = datamanager.get_other_known_characters()
        self.fields[field_name].max_selection_size = 1 # IMPORTANT


    def clean_other_username(self):
        data = self.cleaned_data['other_username']
        assert not isinstance(data, basestring)
        return data[0] if data else None


@register_view
class FriendshipManagementView(AbstractGameView):

    TITLE = ugettext_lazy("Friendship Management")
    NAME = "friendship_management"

    GAME_ACTIONS = dict(do_propose_friendship=dict(title=ugettext_lazy("Propose friendship"),
                                                          form_class=FriendshipRequestForm,
                                                          callback="do_propose_friendship"),
                        do_accept_friendship=dict(title=ugettext_lazy("Accept friendship"),
                                                          form_class=None,
                                                          callback="do_accept_friendship"),
                        do_cancel_proposal=dict(title=ugettext_lazy("Cancel friendship proposal"),
                                                          form_class=None,
                                                          callback="do_cancel_proposal"),
                        do_cancel_friendship=dict(title=ugettext_lazy("Cancel friendship"),
                                                          form_class=None,
                                                          callback="do_cancel_friendship"))

    ADMIN_ACTIONS = dict(set_friendship_minimum_duration=dict(title=ugettext_lazy("Set minimum friendship duration"),
                                                    form_class=FriendshipMinDurationForm,
                                                    callback="set_friendship_minimum_duration"),)

    TEMPLATE = "profile/friendship_management.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False


    @transaction_watcher
    def set_friendship_minimum_duration(self, duration_mn):
        self.datamanager.set_global_parameter("friendship_minimum_duration_mn_abs", duration_mn) # checked by form
        return _("Minimum friendship duration well set.")



    def _relation_type_to_action(self, relation_type):
        if relation_type == "proposed_to":
            return ("do_cancel_proposal", _("Cancel friendship proposal."), _("You've proposed a friendship to that user."))
        elif relation_type == "requested_by":
            return ("do_accept_friendship", _("Accept friendship proposal."), _("You've been proposed a friendship by that user."))
        elif relation_type == "recent_friend":
            return (None, None, _("You've been friend with that user for a short time (impossible to break that friendship at the moment)."))
        elif relation_type == "old_friend":
            return ("do_cancel_friendship", _("Abort friendship."), _("You're friends with that user."))
        else:
            assert relation_type is None, repr(relation_type)
            return ("do_propose_friendship", _("Propose friendship."), _("You're not friends with that user."))


    def get_template_vars(self, previous_form_data=None):

        friendship_statuses = self.datamanager.get_other_characters_friendship_statuses()

        friendship_actions = sorted([(other_username, self._relation_type_to_action(relation_type))
                                     for (other_username, relation_type) in friendship_statuses.items()
                                     if relation_type]) # list of pairs (other_username, relation_type), ONLY when a relation of some kind exists

        return {
                 'page_title': _("Friendship Management"),
                 'current_friends': self.datamanager.get_friends_for_character(),
                 "friendship_actions": friendship_actions,
                 'friendship_request_form': self._instantiate_game_form(new_action_name="do_propose_friendship")
               }

    def do_propose_friendship(self, other_username, use_gems=()):

        if not self.datamanager.is_character(other_username):
            raise NormalUsageError(_("Invalid username '%s'") % other_username)

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
            return _("Your friendship with %s has been properly canceled, since he had accepted it concurrently.") % other_username
        else:

            return _("Your friendship proposal to user %s has been properly canceled.") % other_username


    def do_cancel_friendship(self, other_username):

        res = self.datamanager.terminate_friendship(rejected_user=other_username) # might raise exception if (rare) concurrent cancelation occurred
        if res:
            return _("Your friendship with %s has been properly canceled.") % other_username
        else:
            return _("Your friendship proposal to user %s has been properly canceled.") % other_username  # weirdest case...


friendship_management = FriendshipManagementView.as_view





@register_view(access=UserAccess.authenticated, title=ugettext_lazy("System Events"))
def game_events(request, template_name='administration/game_events.html'):

    events = request.datamanager.get_game_events() # FILTERS by current user

    trans_events = []
    for event in events:
        trans_event = dict(**event) # dont use dict.copy() or copy.copy(), else nasty side effects
        if trans_event["substitutions"]:
            try:
                trans_event["final_message"] = trans_event["message"] % utilities.SDICT(**trans_event["substitutions"])
            except Exception:  # eg. in case where a rogue "%" appears in message...
                trans_event["final_message"] = trans_event["message"] + " " + repr(trans_event["substitutions"])
        else:
            trans_event["final_message"] = trans_event["message"]
        del trans_event["message"]
        del trans_event["substitutions"]
        trans_events.append(trans_event)

    trans_events = list(reversed(trans_events))  # most recent first

    return render(request,
                  template_name,
                    {
                     'events': trans_events
                    })





@register_view(access=UserAccess.character, requires_global_permission=False, title=ugettext_lazy("Instructions"))
def ___instructions(request, template_name='profile/instructions.html'): # TODO - remove that ?????

    user = request.datamanager.user
    intro_data = request.datamanager.get_game_instructions()

    return render(request,
                  template_name,
                    {
                     'page_title': _("Instructions"),
                     'intro_data': intro_data,
                    })


