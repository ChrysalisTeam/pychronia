# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.views._abstract_game_view import register_view
from rpgweb.authentication import authenticate_with_credentials, logout_session
from django.http import HttpResponseRedirect
from rpgweb import forms

@register_view(access=UserAccess.anonymous, always_available=True)
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

            if request.POST.get("password_forgotten", None):

                # TODO MOVE THIS - + '?' + urllib.urlencode(kwargs)
                if username == "master":
                    user.add_error(_("Game master can't recover his password through a secret question."))
                elif username not in request.datamanager.get_character_usernames():
                    user.add_error(_("You must provide a valid username to recover your password."))
                else:
                    return secret_question(request)

            else:  # normal authentication
                with action_failure_handler(request, _("You've been successfully logged in.")):  # message won't be seen because of redirect...
                    authenticate_with_credentials(request, username, password)
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


@register_view(access=UserAccess.authenticated, always_available=True)
def logout(request, template_name='registration/logout.html'):

    logout_session(request)

    user = request.datamanager.user  # take user only NOW, after logout
    user.add_message(_("You've been successfully logged out."))  # will not be seen with redirection
    return HttpResponseRedirect(reverse(login, kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))




@register_view(access=UserAccess.anonymous)
def secret_question(request, template_name='registration/secret_question.html'):

    secret_question = None
    form = None

    username = request.REQUEST.get("secret_username", None)
    if not username or username not in request.datamanager.get_character_usernames():
        # user.add_error("You must provide a valid username to recover your password") -> no, won't work with redirect !
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
                request.datamanager.process_secret_answer_attempt(username, secret_answer_attempt, target_email)  # raises error on bad answer/email
                # success
                form = None
                secret_question = None
            except:
                secret_question = request.datamanager.get_secret_question(username)
                form = forms.SecretQuestionForm(username, data=request.POST)
                form.full_clean()
                raise

    else:
        secret_question = request.datamanager.get_secret_question(username)
        form = forms.SecretQuestionForm(username)

    assert (not form and not secret_question) or (form and secret_question)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Password Recovery"),
                     'secret_question': secret_question,
                     'secret_question_form': form,
                    })

