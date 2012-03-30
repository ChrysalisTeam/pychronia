# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from ._abstract_ability import *
from django.http import Http404



@register_view
class AdminDashboardAbility(AbstractAbility):
    
    NAME = "admin_dashboard"

    ACTIONS = {"store_widget_order": "store_widget_order"}
    TEMPLATE = "administration/admin_dashboard.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True 

    

    
    def _process_ajax_request(self):
        """
        We override this to redirect some requests to GameView admin widgets.
        """
        request = self.request
        admin_widget_identifier = request.GET.get("target_form_id")
        
        if not admin_widget_identifier:
            return super(AdminDashboardAbility._klass, self)._process_ajax_request() # UGLY, FIXME
        else:
            # special part: we execute a single admin widget handler, and return the HTML result.
            
            components = self.datamanager.resolve_admin_widget_identifier(identifier=admin_widget_identifier)
            if not components:
                raise Http404
            
            instance, form_name = components
            html_res = instance.process_admin_request(request, form_name)
            return html_res
        
 
    def get_template_vars(self, previous_form_data=None):
        
        
        #compute_admin_template_variables
        return {
                 'page_title': _("Admin Dashboard"),
               }


    def store_widget_order(self, tokens_csv=None):
        pass 

    @classmethod
    def _setup_ability_settings(cls, settings):
        pass

    def _setup_private_ability_data(self, private_data):
        pass # HERE store the preferred order of widgets


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        if strict:
            pass

