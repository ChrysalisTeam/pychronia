
FIXME TODO
BROKEN

DEAD
# TODO - redo this as special ability
@register_view(title=_lazy("Chat with Djinn"))  # (access=UserAccess.character)#(permission="contact_djinns")
def chat_with_djinn(request, template_name='specific_operations/chat_with_djinn.html'):

    bot_name = request.POST.get("djinn", None)

    # TODO BAD - add security here !!!!!!!!!!

    if not request.datamanager.is_game_staSSSSQrted():
        return HttpResponse(_("Game is not yet started"))

    if bot_name not in request.datamanager.get_bot_names():
        raise Http404

    history = request.datamanager.get_bot_history(bot_name)

    sentences = []
    for i in range(max(len(history[0]), len(history[1]))):
        if i < len(history[0]):
            sentences.append(history[0][i])  # input
        if i < len(history[1]):
            sentences.append(history[1][i])  # output

    return render(request,
                  template_name,
                    {
                     'page_title': _("Djinn Communication"),
                     'bot_name': bot_name,
                     'history': sentences
                    })


@register_view(attach_to=chat_with_djinn, title=_lazy("Consult Djinn"))  # access=UserAccess.character)(permission="contact_djinns")
def ajax_consult_djinns(request):
    user = request.datamanager.user
    message = request.REQUEST.get("message", "")
    bot_name = request.REQUEST.get("djinn", None)

    if bot_name not in request.datamanager.get_bot_names():
        raise Http404

    res = request.datamanager.get_bot_response(bot_name, message)
    return HttpResponse(escape(res))  # IMPORTANT - escape xml entities !!

    # in case of error, a "500" code will be returned


# TODO - redo this as special ability
@register_view  # (access=UserAccess.character)#(permission="contact_djinns")
def contact_djinns(request, template_name='specific_operations/contact_djinns.html'):

    user = request.datamanager.user

    bots_properties = request.datamanager.get_bots_properties()

    if user.is_master:  # FIXME
        available_bots = bots_properties.keys()
        # team_gems = None
    else:
        domain = request.datamanager.get_character_properties()["domain"]
        available_bots = [bot_name for bot_name in bots_properties.keys() if request.datamanager.is_bot_accessible(bot_name, domain)]
        # team_gems = request.datamanager.get_team_gems_count(domain)

    if available_bots:
        djinn_form = forms.DjinnContactForm(available_bots)
    else:
        djinn_form = None

    all_bots = bots_properties.items()
    all_bots.sort(key=lambda t: t[1]["gems_required"])

    return render(request,
                  template_name,
                    {
                     'page_title': _("Shrine of Oracles"),
                     'djinn_form': djinn_form,
                     'all_bots': all_bots,
                     # 'team_gems': team_gems,
                     'bots_max_answers': request.datamanager.get_global_parameter("bots_max_answers")
                    })

