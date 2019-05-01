# -*- coding: utf-8 -*-



from pychronia_game.common import *
from pychronia_game.datamanager import AbstractGameForm, AbstractAbility, register_view, transaction_watcher

from django import forms
from django.http import Http404
from pychronia_game.datamanager import UninstantiableFormError


class GamePauseForm(AbstractGameForm):
    is_paused = forms.BooleanField(label=ugettext_lazy("Game is paused?"), required=False)

    def __init__(self, datamanager, *args, **kwargs):
        super(GamePauseForm, self).__init__(datamanager, *args, **kwargs)
        self.fields['is_paused'].initial = not datamanager.is_game_started()


class AbilityAutoresponseForm(AbstractGameForm):
    disable_ability_autoresponse = forms.BooleanField(label=ugettext_lazy("Disable ability auto-responses?"),
                                                      required=False)

    def __init__(self, datamanager, *args, **kwargs):
        super(AbilityAutoresponseForm, self).__init__(datamanager, *args, **kwargs)
        self.fields['disable_ability_autoresponse'].initial = datamanager.get_global_parameter(
            "disable_automated_ability_responses")


class ExternalNotificationForm(AbstractGameForm):
    disable_real_email_notifications = forms.BooleanField(label=ugettext_lazy("Disable real email notifications?"),
                                                          required=False)

    def __init__(self, datamanager, *args, **kwargs):
        super(ExternalNotificationForm, self).__init__(datamanager, *args, **kwargs)
        self.fields['disable_real_email_notifications'].initial = datamanager.get_global_parameter(
            "disable_real_email_notifications")


class GameViewActivationForm(AbstractGameForm):
    activated_views = forms.MultipleChoiceField(label=ugettext_lazy("Game views"), required=False,
                                                widget=forms.CheckboxSelectMultiple)

    def __init__(self, datamanager, *args, **kwargs):
        super(GameViewActivationForm, self).__init__(datamanager, *args, **kwargs)

        activable_views = datamanager.get_activable_views()  # mapping view_name -> klass

        if not activable_views:
            raise UninstantiableFormError(_("No views to be activated"))

        activable_views_choices = [(view_name, view_klass.TITLE) for (view_name, view_klass) in list(activable_views.items())]
        activable_views_choices.sort()
        self.fields['activated_views'].choices = activable_views_choices
        self.fields['activated_views'].initial = datamanager.get_activated_game_views()


class GameDurationForm(AbstractGameForm):
    num_days = forms.FloatField(label=ugettext_lazy("Set theoretical game duration in days"), max_value=365,
                                min_value=1, required=True)

    def __init__(self, datamanager, *args, **kwargs):
        super(GameDurationForm, self).__init__(datamanager, *args, **kwargs)
        self.fields['num_days'].initial = datamanager.get_global_parameter("game_theoretical_length_days")


class MasterCredentialsForm(AbstractGameForm):
    master_login = forms.CharField(label=ugettext_lazy("Master Login (immutable)"), required=False,
                                   widget=forms.TextInput(attrs={'disabled': 'disabled'}))
    master_password = forms.CharField(label=ugettext_lazy("Master Password (NOT your usual one)"),
                                      required=False)  # NOT a PasswordInput
    master_real_email = forms.EmailField(label=ugettext_lazy("Master Real Email (optional)"), required=False)

    def __init__(self, datamanager, *args, **kwargs):
        super(MasterCredentialsForm, self).__init__(datamanager, *args, **kwargs)

        self.fields['master_real_email'].initial = datamanager.get_global_parameter("master_real_email")
        self.fields['master_login'].initial = datamanager.get_global_parameter("master_login")
        self.fields['master_password'].initial = datamanager.get_global_parameter("master_password")


@register_view
class AdminDashboardAbility(AbstractAbility):
    TITLE = ugettext_lazy("Admin Dashboard")
    NAME = "admin_dashboard"

    GAME_ACTIONS = dict(save_admin_widgets_order=dict(title=ugettext_lazy("Save admin widgets' order"),
                                                      form_class=None,
                                                      callback="save_admin_widgets_order"))

    # Place here dashboard forms that don't have their own containing view! #
    ADMIN_ACTIONS = dict(choose_activated_views=dict(title=ugettext_lazy("Activate views"),
                                                     form_class=GameViewActivationForm,
                                                     callback="choose_activated_views"),
                         set_theoretical_game_duration=dict(title=ugettext_lazy("Set game duration"),
                                                            form_class=GameDurationForm,
                                                            callback="set_theoretical_game_duration"),
                         set_game_pause_state=dict(title=ugettext_lazy("Set game pause state"),
                                                   form_class=GamePauseForm,
                                                   callback="set_game_pause_state"),
                         change_master_credentials=dict(title=ugettext_lazy("Change game master credentials"),
                                                        form_class=MasterCredentialsForm,
                                                        callback="change_master_credentials"),
                         ability_autoresponse_mode=dict(title=ugettext_lazy("Set ability autoresponses"),
                                                        form_class=AbilityAutoresponseForm,
                                                        callback="disable_ability_autoresponse"),
                         external_email_mode=dict(title=ugettext_lazy("Set external notifications"),
                                                  form_class=ExternalNotificationForm,
                                                  callback="disable_external_notifications"),
                         )

    TEMPLATE = "administration/admin_dashboard.html"

    ACCESS = UserAccess.master
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False

    @transaction_watcher
    def save_admin_widgets_order(self, ids_list):
        #print(">>>>>>>>>", ids_list)
        self.settings["sorted_widget_ids"] = PersistentList(ids_list)

    def _process_html_post_data(self):
        """
        We override this to redirect some requests to GameView admin widgets.
        """
        request = self.request
        admin_widget_identifier = request.POST.get("target_form_id")

        if not admin_widget_identifier:
            return super(AdminDashboardAbility, self)._process_html_post_data()  # UGLY, FIXME
        else:
            # special part: we execute a single admin widget handler, and return the HTML result.

            components = self.datamanager.resolve_admin_widget_identifier(identifier=admin_widget_identifier)
            if not components:
                raise Http404

            instance, action_name = components
            res = instance.process_admin_request(request, action_name)
            return res

    def get_template_vars(self, previous_form_data=None):

        existing_widget_ids = self.datamanager.get_admin_widget_identifiers()

        theoretical_widget_ids = self.settings["sorted_widget_ids"]

        well_sorted_widget_ids = [id for id in theoretical_widget_ids if
                                  id in existing_widget_ids]  # in case some widgets would have disappeared since then
        remaining_widget_ids = sorted(set(existing_widget_ids) - set(well_sorted_widget_ids))

        final_ids = well_sorted_widget_ids + remaining_widget_ids
        del existing_widget_ids, theoretical_widget_ids, well_sorted_widget_ids, remaining_widget_ids

        widgets = []
        for widget_id in final_ids:
            instance, action_name = self.datamanager.resolve_admin_widget_identifier(
                identifier=widget_id)  # might instantiate THIS same gameview class, but not a problem
            widget_vars = instance.compute_admin_template_variables(action_name,
                                                                    previous_form_data=previous_form_data)  # dict for a single form
            widgets.append(widget_vars)

        #compute_admin_template_variables
        return dict(  #page_title=_("Master Dashboard"),
            widgets=widgets, )

    @classmethod
    def _setup_ability_settings(cls, settings):
        settings.setdefault("sorted_widget_ids", PersistentList())
        pass

    def _setup_private_ability_data(self, private_data):
        pass  # HERE store the preferred order of widgets

    def _check_data_sanity(self, strict=False):

        settings = self.settings

        utilities.check_is_list(settings["sorted_widget_ids"])
        utilities.check_no_duplicates(settings["sorted_widget_ids"])

        if strict:
            pass

    @transaction_watcher
    def choose_activated_views(self, activated_views):
        self.set_activated_game_views(activated_views)  # checked by form
        return _("Views status well saved.")

    @transaction_watcher
    def set_theoretical_game_duration(self, num_days):
        self.set_global_parameter("game_theoretical_length_days", num_days)  # checked by form
        return _("Game theoretical duration well saved.")

    @transaction_watcher
    def set_game_pause_state(self, is_paused):
        self.datamanager.set_game_state(started=not is_paused)  # checked by form
        return _("Game state well saved.")

    @transaction_watcher
    def change_master_credentials(self, master_real_email, master_password):
        """
        The master_login shall NEVER be changed after game got created!!
        """
        self.datamanager.override_master_credentials(master_real_email=master_real_email,
                                                     master_password=master_password)
        return _("Game master credentials well changed.")

    @transaction_watcher
    def disable_ability_autoresponse(self, disable_ability_autoresponse):
        assert disable_ability_autoresponse in (True, False)
        self.set_global_parameter("disable_automated_ability_responses", disable_ability_autoresponse)
        return _("Automated ability responses well %(new_state)s.") % SDICT(
            new_state=_("enabled") if not disable_ability_autoresponse else _("disabled"))

    @transaction_watcher
    def disable_external_notifications(self, disable_real_email_notifications):
        assert disable_real_email_notifications in (True, False)
        self.set_global_parameter("disable_real_email_notifications", disable_real_email_notifications)
        return _("External email notifications well %(new_state)s.") % SDICT(
            new_state=_("enabled") if not disable_real_email_notifications else _("disabled"))
