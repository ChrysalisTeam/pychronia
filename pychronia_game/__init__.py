# Workaround for ABC aliases removed in Python 3.10+
import collections
collections.abc.Callable = collections.abc.Callable
collections.abc.Mapping = collections.abc.Mapping