# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_game_view import AbstractGameView, register_view
from pychronia_game import forms
from django.http import Http404, HttpResponseRedirect, HttpResponse
import json
from pychronia_game.utilities import mediaplayers
from pychronia_game.datamanager.abstract_form import AbstractGameForm
from django import forms as django_forms


@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("World Map"))
def view_world_map(request, template_name='information/world_map.html'):

    return render(request,
                  template_name,
                    {
                     'world_map_image': request.datamanager.get_global_parameter("world_map_image"),
                     'world_map_image_bw': request.datamanager.get_global_parameter("world_map_image_bw"),
                    })






@register_view
class StaticPageView(AbstractGameView):
    """
    This view allows one to see ANY static page on its own, without any permission checking
    (jsut a "private link" notion).
    """

    TITLE = ugettext_lazy("Article")
    NAME = "view_static_page"

    TEMPLATE = "information/view_static_page.html"

    ACCESS = UserAccess.anonymous
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False


    def get_template_vars(self, previous_form_data=None):

        page_id = self.kwargs.get("page_id")

        if not page_id or page_id not in self.datamanager.static_pages:
            print(">>>>", page_id, self.datamanager.static_pages.keys())
            raise Http404 # unexisting static page

        entry = self.datamanager.static_pages[page_id]

        return dict(entry=entry)

view_static_page = StaticPageView.as_view



class EnyclopediaIndexVisibilityForm(AbstractGameForm):

    is_index_visible = django_forms.BooleanField(label=ugettext_lazy("Full Index Visibility"), required=False)

    def __init__(self, datamanager, *args, **kwargs):
        super(EnyclopediaIndexVisibilityForm, self).__init__(datamanager, *args, **kwargs)
        self.fields["is_index_visible"].initial = datamanager.is_encyclopedia_index_visible()


@register_view
class EncyclopediaView(AbstractGameView):

    TITLE = ugettext_lazy("Encyclopedia")
    NAME = "view_encyclopedia"

    # Place here dashboard forms that don't have their own containing view! #
    ADMIN_ACTIONS = dict(set_encyclopedia_index_visibility=dict(title=ugettext_lazy("Set encyclopedia index visibility"),
                                                                  form_class=EnyclopediaIndexVisibilityForm,
                                                                  callback="set_encyclopedia_index_visibility"))

    TEMPLATE = "information/encyclopedia.html"

    ACCESS = UserAccess.anonymous
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False


    def _generate_articles_index(self, index_article_ids):
        """index_article_ids might be None"""
        _pages = self.datamanager.static_pages
        index_article_ids = index_article_ids or []
        articles_index = [(index_article_id, _pages[index_article_id].get("title")) for index_article_id in index_article_ids]
        articles_index.sort(key=lambda x: x[1])  # sort by title (even is some might be None, resulting in 'identifier' to be shown instead)
        return articles_index

    def _process_standard_request(self, request, current_article_id=None):
        """
        We bypass standard GameView processing here.
        """
        ## set_encyclopedia_index_visibility

        """
        No need for novelty management in here - normal "visited link" browser system will do it.
        """
        dm = self.datamanager

        def _conditionally_update_known_article_ids(ids_list):
            assert isinstance(ids_list, list)
            assert all(isinstance(i, basestring) for i in ids_list)
            if dm.is_character() and dm.is_game_writable():  # not for master or anonymous!!
                dm.update_character_known_article_ids(article_ids=ids_list)
                #print ("Really IN _conditionally_update_known_article_ids", ids_list, self.datamanager.user.username)

        search_string = None
        search_results_ids = None
        entry = None  # current article data

        if current_article_id:
            entry = dm.get_encyclopedia_entry(current_article_id) # entry dict or None
            if not entry:
                dm.user.add_error(_("Sorry, no encyclopedia article has been found for id '%s'") % current_article_id)
            else:
                _conditionally_update_known_article_ids([current_article_id])
        else:
            search_string = request.REQUEST.get("search")  # needn't appear in browser history, but GET needed for encyclopedia links
            if search_string:
                search_results_ids = dm.get_encyclopedia_matches(search_string)
                if not search_results_ids:
                    dm.user.add_error(_("Sorry, no matching encyclopedia article has been found for '%s'") % search_string)
                else:
                    assert not isinstance(search_results_ids, basestring) # already a list
                    _conditionally_update_known_article_ids(search_results_ids)
                    if len(search_results_ids) == 1:
                        dm.user.add_message(_("Your search has led to a single article, below."))
                        return HttpResponseRedirect(redirect_to=game_view_url("pychronia_game.views.view_encyclopedia",
                                                                              datamanager=dm,
                                                                              current_article_id=search_results_ids[0]))

        # NOW only retrieve article ids, since known article ids have been updated if necessary
        index_article_ids = None
        if dm.is_encyclopedia_index_visible() or dm.is_master(): # master ALWAYS sees everything
            index_article_ids = dm.get_encyclopedia_article_ids()
        elif dm.is_character():
            index_article_ids = dm.get_character_known_article_ids()
        else:
            assert dm.is_anonymous()  # we leave article_ids to []

        articles_index = self._generate_articles_index(index_article_ids)

        search_results = self._generate_articles_index(search_results_ids)

        return TemplateResponse(request=request,
                                template=self.TEMPLATE,
                                context={
                                         'page_title': _("Pangea Encyclopedia"),
                                         'articles_index': articles_index,
                                         'current_article_id': current_article_id,
                                         'entry': entry,
                                         'search_string': search_string,
                                         'search_results': search_results
                                })

    def set_encyclopedia_index_visibility(self, is_index_visible):
        assert is_index_visible in (True, False)
        self.datamanager.set_encyclopedia_index_visibility(value=is_index_visible)
        return _("Encyclopedia index visibility has now been set to %s") % int(is_index_visible)

view_encyclopedia = EncyclopediaView.as_view







# we don't put any security there, at worst a pirate might play with this and prevent playing
# some audio notifications, but it's neither critical nor discreet
@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Ajax Audio Message Finished"))
def ajax_notify_audio_message_finished(request, requires_global_permission=False):

    audio_id = request.GET.get("audio_id", None)

    try:
        audio_id = audio_id.decode("base64")
    except:
        return HttpResponse("ERROR")

    res = request.datamanager.notify_audio_message_termination(audio_id)

    return HttpResponse("OK" if res else "IGNORED")
    # in case of error, a "500" code will be returned (should never happen here)


# we don't put any security there either
@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Ajax Next Audio Message"))
def ajax_get_next_audio_message(request):
    radio_is_on = request.datamanager.get_global_parameter("radio_is_on")

    if radio_is_on:
        next_audio_id = request.datamanager.get_next_audio_message()
        if next_audio_id:
            fileurl = determine_asset_url(request.datamanager.get_audio_message_properties(next_audio_id))
            next_audio_id = next_audio_id.encode("base64")
        else:
            fileurl = None
    else:
        next_audio_id = fileurl = None

    response = json.dumps([next_audio_id, fileurl])
    return HttpResponse(response)





@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Pangea Webradio"))
def personal_webradio_page(request, template_name='information/web_radio_page.html'):

    dm = request.datamanager
    current_playlist = dm.get_all_next_audio_messages()
    current_audio_messages = [dm.get_audio_message_properties(audio_id) for audio_id in current_playlist]

    return render(request,
                  template_name,
                    {
                     'page_title': _("Pangea Webradio"),
                     'playlist': current_audio_messages,
                    })


@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Webradio Popup"))
def personal_webradio_popup(request, template_name='information/web_radio_popup.html'):
    return render(request,
                  template_name)


@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Radio Conf"))
def get_radio_xml_conf(request, template_name='information/web_radio_conf.xml'):
    dm = request.datamanager
    current_playlist = dm.get_all_next_audio_messages()
    current_audio_messages = [dm.get_audio_message_properties(audio_id) for audio_id in current_playlist]

    if not current_audio_messages:
        # we had better not let the player empty, it's not tweaked for that case
        current_audio_messages = [dict(file="[None]", title=_("[No radio spot currently available]"))]

    audio_urls = "|".join([determine_asset_url(msg) for msg in current_audio_messages])  # we expect no "|" inside a single url
    audio_titles = "|".join([msg["title"].replace("|", "") for msg in current_audio_messages])  # here we can cleanup

    if dm.is_game_writable():
        dm.mark_current_playlist_read() # THAT view is symptomatic of actual listening of personal radio (in both popup and normal window)

    return render(request,
                  template_name,
                  dict(audio_urls=audio_urls,
                       audio_titles=audio_titles))



@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Radio Station"))
def public_webradio(request, template_name='information/web_radio_public.html'):

    access_authorized = False

    if request.method == "POST":
        with action_failure_handler(request, _("You're listening to Pangea Radio.")):
            frequency = request.POST.get("frequency", None)
            if frequency:
                frequency = frequency.strip()
            request.datamanager.check_radio_frequency(frequency)  # raises UsageError on failure
            access_authorized = True

    if access_authorized:
        form = None
    else:
        form = forms.RadioFrequencyForm()


    assert (form and not access_authorized) or (not form and access_authorized)

    return render(request,
                  template_name,
                    {
                     'page_title': _("Radio Station"),
                     'access_authorized': access_authorized,
                     'form': form
                    })









@register_view(access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("Personal Files"))
def personal_folder(request, template_name='information/personal_folder.html'):

    user = request.datamanager.user

    try:

        personal_files = request.datamanager.get_personal_files(absolute_urls=False)  # to allow easier stealing of files from Loyd's session

    except EnvironmentError, e:
        personal_files = []
        user.add_error(_("Your personal folder is unreachable."))


    files_to_display = zip([os.path.basename(file) for file in personal_files], personal_files)

    if not files_to_display:
        user.add_message = _("You currently don't have any files in your personal folder.")

    return render(request,
                  template_name,
                    {
                        "page_title": _("Personal Folder"),
                        "files": files_to_display,
                        "display_maintenance_notice": True,  # upload disabled notification
                    })



# This page is meant for inclusion in pages offering all the required css/js files !
@register_view(access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("View Media"))
def view_media(request, template_name='utilities/view_media.html'):

    fileurl = request.REQUEST.get("url", None)
    autostart = (request.REQUEST.get("autostart", "false") == "true")

    if fileurl:
        media_player = mediaplayers.build_proper_viewer(fileurl, autostart=autostart)
    else:
        media_player = "<p>" + _("You must provide a valid media url.") + "</p>"

    return render(request,
                  template_name,
                    {
                     'media_player': media_player
                    })








@register_view(access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Encrypted Folder"))  # anonymous because links in emails must NEVER be broken
def encrypted_folder(request, folder, entry_template_name="information/encrypted_folder.html", display_template_name='information/personal_folder.html'):

    if not request.datamanager.encrypted_folder_exists(folder):
        raise Http404

    user = request.datamanager.user
    files = None
    form = None

    if request.method == "POST":
        form = forms.CleartextPasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data["simple_password"].lower()  # normalized !

            with action_failure_handler(request, _("Folder decryption successful.")):
                files = request.datamanager.get_encrypted_files(user.username, folder, password, absolute_urls=False)
                form = None  # triggers the display of files

    else:
        form = forms.CleartextPasswordForm()


    if form:
        return render(request,
                      entry_template_name,
                        {
                            "page_title": _("Encrypted archive '%s'") % folder,
                            "password_form": form,
                            "folder": folder
                        })


    else:  # necessarily, we've managed to decrypt the folder
        assert files is not None
        files_to_display = zip([os.path.basename(myfile) for myfile in files], files)

        if not files_to_display:
            user.add_message = _("No files were found in the folder.")


        return render(request,
                      display_template_name,
                        {
                            "page_title": _("Decrypted archive"),
                            "files": files_to_display,
                            "display_maintenance_notice": False,  # upload disabled notification
                        })









