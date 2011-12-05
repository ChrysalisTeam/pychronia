# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals



from . import datamanager_core
from . import datamanager_modules

from .datamanager_tools import *
from .datamanager_core import *  # only for temporary compatibility


AllBases = tuple(reversed(datamanager_modules.MODULES_REGISTRY)) # latest classes must be first in hierarchy


GameDataManager = type(str('GameDataManager'), AllBases, {})


#print(GameDataManager.__mro__)

assert GameDataManager.__mro__[-3:] == (BaseDataManager, datamanager_core.Persistent, object) # IMPORTANT - modules must be BEFORE BaseDataManager


