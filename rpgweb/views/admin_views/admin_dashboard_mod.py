# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager.abstract_ability import AbstractAbility
from django.http import Http404
from rpgweb.datamanager.abstract_game_view import register_view
from rpgweb.datamanager.datamanager_tools import transaction_watcher



@register_view
class AdminDashboardAbility(AbstractAbility):

    NAME = "admin_dashboard"

    ACTIONS = {"save_admin_widgets_order": "save_admin_widgets_order"}
    TEMPLATE = "administration/admin_dashboard.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True



    @transaction_watcher
    def save_admin_widgets_order(self, ids_list):
        #print(">>>>>>>>>", ids_list)
        self.settings["sorted_widget_ids"] = PersistentList(ids_list)

    def _process_ajax_request(self):
        """
        We override this to redirect some requests to GameView admin widgets.
        """
        request = self.request
        admin_widget_identifier = request.GET.get("target_form_id")

        if not admin_widget_identifier:
            return super(AdminDashboardAbility, self)._process_ajax_request() # UGLY, FIXME
        else:
            # special part: we execute a single admin widget handler, and return the HTML result.

            components = self.datamanager.resolve_admin_widget_identifier(identifier=admin_widget_identifier)
            if not components:
                raise Http404

            instance, form_name = components
            html_res = instance.process_admin_request(request, form_name)
            return html_res


    def get_template_vars(self, previous_form_data=None):

        existing_widget_ids = self.datamanager.get_admin_widget_identifiers()

        theoretical_widget_ids = self.settings["sorted_widget_ids"]

        well_sorted_widget_ids = [id for id in theoretical_widget_ids if id in existing_widget_ids] # in case some widgets would have disappeared since then
        remaining_widget_ids = sorted(set(existing_widget_ids) - set(well_sorted_widget_ids))


        final_ids = well_sorted_widget_ids + remaining_widget_ids
        del existing_widget_ids, theoretical_widget_ids, well_sorted_widget_ids, remaining_widget_ids

        # Here we might do some filtering !!

        widgets = []
        for widget_id in final_ids:
            instance, form_name = self.datamanager.resolve_admin_widget_identifier(identifier=widget_id)
            widget_vars = instance.compute_admin_template_variables(form_name, previous_form_data=None)
            widgets.append(widget_vars)

        #compute_admin_template_variables
        return dict(page_title=_("Admin Dashboard"),
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



