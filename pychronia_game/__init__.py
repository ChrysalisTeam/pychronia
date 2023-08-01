# -*- coding: utf-8 -*-


# Workaround for ABC aliases removed in Python 3.10+
import collections
collections.Callable = collections.abc.Callable
collections.Mapping = collections.abc.Mapping