# -*- coding: utf-8 -*-
"""
Python Objects' Recursive Printer 

pafo is a help debug library. it allows programmer to observer  data
fields' state of a complex object or a bundle of objects. Even if some
objects in the bundle haven't __str__ or __repr__ methods. Such
situation is very usual. Nobody want to writer code only that to print
the state of an object two-three times.

import and use function "printObject" 
"""

# pafo/main.py - main code for pafo
#
# Copyright (C) 2010 Daneel S. Yaitskov <rtfm.rtfm.rtfm@gmail.com>
#
# pafo is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pafo is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
# License for more details.

from main import printObject, traceObject
__all__ = [ 'printObject' ] # , 'traceObject' ]
