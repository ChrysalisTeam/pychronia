# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.forms import HouseReportForm
from pychronia_game.common import *
from pychronia_game.datamanager.abstract_ability import AbstractAbility, AbstractPartnershipAbility
from pychronia_game.datamanager.abstract_game_view import register_view
from pychronia_game.datamanager import readonly_method, \
    transaction_watcher


@register_view
class HouseReportsAbility(AbstractPartnershipAbility):

    TITLE = ugettext_lazy("Manor Surveillance Reports")
    NAME = "house_reports"

    GAME_ACTIONS = dict(get_report=dict(title=ugettext_lazy("Fetch report"),
                                          form_class=HouseReportForm,
                                          callback="fetch_house_report"),)

    TEMPLATE = "abilities/house_reports.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True

    def get_template_vars(self, previous_form_data=None):

        periods_form = self._instantiate_game_form(new_action_name="get_report",
                                                    hide_on_success=False,
                                                    previous_form_data=previous_form_data)

        return {
            'page_title': _("Manor Surveillance Reports"),
            'periods_form': periods_form
        }


    @readonly_method
    def _get_valid_report_for_period(self, period):
        report = self.settings["reports"][period]["surveillance_analysis"]
        if not report:
            raise AbnormalUsageError(_("Wrong surveillance report selected"))
        return report


    @readonly_method
    def get_available_periods(self):
        reports = self.settings["reports"]
        result = sorted((k, bool(reports[k]["surveillance_analysis"])) for k in reports.keys())
        return result


    @transaction_watcher
    def fetch_house_report(self, period, use_gems=()):

        report = self._get_valid_report_for_period(period)

        # dummy request email, to allow wiretapping
        subject = _('Manor surveillance request for period %s') % period
        body = _("Please provide me with an analysis of manor activity during this period.")
        request_msg_data = dict(subject=subject,
                                body=body)
        del subject, body

        # answer from surveillance center
        response_msg_data = None
        if report:
            subject = _("<Manor surveillance response for period %(period)s>") % SDICT(period=period)
            body = report  # as is
            response_msg_data = dict(subject=subject,
                                     body=body,
                                     attachment=None)
            del subject, body

        best_msg_id = self._process_standard_exchange_with_partner(request_msg_data=request_msg_data,
                                                                   response_msg_data=response_msg_data)

        self.log_game_event(ugettext_noop("Period '%(period)s' requested near manor surveillance center."),
                            PersistentMapping(period=period),
                            url=self.get_message_viewer_url_or_none(best_msg_id),  # best_msg_id might be None
                            visible_by=[self.username])

        return _("Request for surveillance data of period '%s' successfully submitted, you'll receive the result by email") % period


    @classmethod
    def _setup_ability_settings(cls, settings):
        pass

    def _setup_private_ability_data(self, private_data):
        pass

    def _check_data_sanity(self, strict=False):

        settings = self.settings

        house_reports = settings["reports"]

        # at least one period must have surveillance data available!
        assert utilities.usage_assert(any(x["surveillance_analysis"] for x in house_reports.values()))

        for (period, report_data) in house_reports.items():
            assert utilities.check_is_string(period)
            if report_data["gamemaster_hints"]:
                assert utilities.check_is_string(report_data["gamemaster_hints"], multiline=True)
            if report_data["surveillance_analysis"]:
                assert utilities.check_is_string(report_data["surveillance_analysis"], multiline=True)
