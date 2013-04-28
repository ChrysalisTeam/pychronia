# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import AbstractGameForm, AbstractAbility, register_view, transaction_watcher

from django import forms
from django.http import Http404





class GameViewActivationForm(AbstractGameForm):

    activated_views = forms.MultipleChoiceField(label=_lazy("Game views"), required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, datamanager, *args, **kwargs):
        super(GameViewActivationForm, self).__init__(datamanager, *args, **kwargs)

        activable_views = datamanager.get_activable_views() # mapping view_name -> klass
        activable_views_choices = [(view_name, view_klass.NAME) for (view_name, view_klass) in activable_views.items()]

        if not activable_views:
            raise

        self.fields['activated_views'].choices = activable_views_choices
        self.fields['activated_views'].initial = datamanager.get_activated_game_views()




@register_view
class AdminDashboardAbility(AbstractAbility):

    TITLE = _lazy("Admin Dashboard")
    NAME = "admin_dashboard"

    GAME_ACTIONS = dict(save_admin_widgets_order=dict(title=_lazy("Save admin widgets' order"),
                                                          form_class=None,
                                                          callback="save_admin_widgets_order"))

    # Place here dashboard forms that don't have their own containing view! #
    ADMIN_ACTIONS = dict(choose_activated_views=dict(title=_lazy("Activate views"),
                                                          form_class=GameViewActivationForm,
                                                          callback="choose_activated_views"))

    TEMPLATE = "administration/admin_dashboard.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_ACTIVATED = True



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
            return super(AdminDashboardAbility, self)._process_html_post_data() # UGLY, FIXME
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

        well_sorted_widget_ids = [id for id in theoretical_widget_ids if id in existing_widget_ids] # in case some widgets would have disappeared since then
        remaining_widget_ids = sorted(set(existing_widget_ids) - set(well_sorted_widget_ids))

        final_ids = well_sorted_widget_ids + remaining_widget_ids
        del existing_widget_ids, theoretical_widget_ids, well_sorted_widget_ids, remaining_widget_ids


        widgets = []
        for widget_id in final_ids:
            instance, action_name = self.datamanager.resolve_admin_widget_identifier(identifier=widget_id) # might instantiate THIS same gameview class, but not a problem
            widget_vars = instance.compute_admin_template_variables(action_name, previous_form_data=previous_form_data) # dict for a single form
            widgets.append(widget_vars)

        #compute_admin_template_variables
        return dict(#page_title=_("Master Dashboard"),
                    widgets=widgets,)




    @classmethod
    def _setup_ability_settings(cls, settings):
        settings.setdefault("sorted_widget_ids", PersistentList())
        pass

    def _setup_private_ability_data(self, private_data):
        pass # HERE store the preferred order of widgets


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        utilities.check_is_list(settings["sorted_widget_ids"])
        utilities.check_no_duplicates(settings["sorted_widget_ids"])

        if strict:
            pass


    @transaction_watcher
    def choose_activated_views(self, activated_views):
        self.set_activated_game_views(activated_views) # checked by form
        return _("Views status well saved.")







