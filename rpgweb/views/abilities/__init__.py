# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


from .house_locking import HouseLockingAbility
house_locking_view = HouseLockingAbility.as_view

from .runic_translation import RunicTranslationAbility
runic_translation_view = RunicTranslationAbility.as_view

from .wiretapping_management import WiretappingAbility
wiretapping_management_view = WiretappingAbility.as_view

from .admin_dashboard import AdminDashboardAbility
admin_dashboard_view = AdminDashboardAbility.as_view

from .mercenaries_hiring import MercenariesHiringAbility
mercenaries_hiring_view = MercenariesHiringAbility.as_view

from .matter_analysis import MatterAnalysisAbility
matter_analysis_view = MatterAnalysisAbility.as_view

from .world_scanning import WorldScanAbility
worl_scan_view = WorldScanAbility.as_view
