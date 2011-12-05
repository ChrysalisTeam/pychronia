# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

### NO import from rpgweb.common, else circular import !! ###

import sys, os, collections, logging, inspect, types
import yaml, random, contextlib
from .counter import Counter
from datetime import datetime, timedelta

import ZODB # must be first !
import transaction
from persistent import Persistent
from persistent.dict import PersistentDict
from persistent.list import PersistentList
 
from django_zodb import database
from django.core.validators import email_re
from django.conf import settings as django_settings
from .. import default_settings as game_default_settings
  
class Conf(object):
    """
    Helper class which handles default game settings.
    """
    def __getattr__(self, name):
        try:
            return getattr(django_settings, name)
        except AttributeError:
            return getattr(game_default_settings, name)
    def __setattr__(self, name, value):
        raise NotImplementedError("Game conf is currently readonly")

config = Conf()
del Conf

## Python <-> ZODB types conversion and checking ##
 
python_to_zodb_types = {list: PersistentList,
                        dict: PersistentDict}

zodb_to_python_types = dict((value, key) for (key, value) in python_to_zodb_types.items())

allowed_zodb_types = (types.NoneType, int, long, float, basestring, tuple, datetime, collections.Callable, PersistentDict, PersistentList)



def monkey_patch_django_zodb_parser():
    import django_zodb.utils, django_zodb.config, django_zodb.tests.test_utils
    from django_zodb.utils import parse_uri as original_parse_uri
    
    def fixed_parse_uri(uri):
        # HACK to make it work for windows file paths !!
        if uri.startswith("file://"):
            return dict(scheme="file", path=uri[len("file://"):])
        return original_parse_uri(uri)
    
    # injection of fixed uri parser
    django_zodb.utils.parse_uri = fixed_parse_uri
    django_zodb.config.parse_uri = fixed_parse_uri
monkey_patch_django_zodb_parser()

def open_zodb_file(zodb_file):
    #print ("RETRIEVING DB FROM FILE", zodb_file)
    URI = "file://" + zodb_file.replace("\\", "/")
    # .replace(":", "|") # or "mem://"    # we have problems with URIs in win32, so replace : with |
    print (">>>>>>", URI)
    db = database.get_database_from_uris([URI])
    return db

 
def convert_object_tree(tree, type_mapping):
    """
    Recursively transform a tree of objects (lists, dicts, instances...)
    into an equivalent structure with alternative types.
    """

    for (A, B) in type_mapping.items():
        if isinstance(tree, A):
            tree = B(tree)
            break

    if isinstance(tree, (types.NoneType, int, long, float, basestring, tuple, datetime, collections.Callable)):
        return tree # Warning - we must thus avoid infinite recursion on character sequences (aka strings)...
    elif isinstance(tree, collections.MutableSequence):
        for (index, item) in enumerate(tree):
            tree[index] = convert_object_tree(item, type_mapping)
    elif isinstance(tree, collections.MutableMapping):
        for (key, value) in tree.items():
            tree[key] = convert_object_tree(value, type_mapping)
    elif isinstance(tree, collections.MutableSet):
        for value in tree:
            tree.remove(value)
            tree.add(convert_object_tree(value, type_mapping))
    elif hasattr(tree, "__dict__"):
        for (key, value) in tree.__dict__.items():
            setattr(tree, key, convert_object_tree(value, type_mapping))
    return tree



def check_object_tree(tree, allowed_types, path):

    if not isinstance(tree, allowed_types):
        raise RuntimeError("Bad object type detected : %s - %s via path %s" % (type(tree), tree, path))


    if isinstance(tree, (int, long, basestring)):
        return

    elif isinstance(tree, collections.MutableSequence):
        for (index, item) in enumerate(tree):
            check_object_tree(item, allowed_types, path + [index])
    elif isinstance(tree, collections.MutableMapping):
        for (key, value) in tree.items():
            check_object_tree(value, allowed_types, path + [key])
    elif isinstance(tree, collections.MutableSet):
        for value in tree:
            check_object_tree(value, allowed_types, path + ["<set-item>"])
    elif hasattr(tree, "__dict__"):
        for (key, value) in tree.__dict__.items():
            check_object_tree(value, allowed_types, path + [key])



def substract_lists(available_gems, given_gems):
    available_gems = Counter(available_gems)
    given_gems = Counter(given_gems)

    if given_gems & available_gems != given_gems:
        return None # operation impossible

    gems_remaining = available_gems - given_gems
    return PersistentList(gems_remaining.elements())




## Tools for database sanity checks ##


def adapt_parameters_to_func(all_parameters, func):
    """
    Strips unwanted parameters in a dict of parameters (eg. obtained via GET or POST),
    and ensures no argument is missing.

    Returns a dict of relevant parameters, or raises common signature exceptions.
    """

    (args, varargs, keywords, defaults) = inspect.getargspec(func)

    if keywords is not None:
        relevant_args = all_parameters # exceeding args will be handled properly
    else:
        relevant_args = dict((key, value) for (key, value) in all_parameters.items() if key in args)

    try:
        inspect.getcallargs(func, **relevant_args)
    except (TypeError, ValueError), e:
        raise

    return relevant_args

def check_no_duplicates(value):
    assert len(set(value)) == len(value), value

def check_is_range_or_num(value):
    if isinstance(value, (int, long, float)):
        pass # nothing to check
    else:
        assert isinstance(value, (tuple, PersistentList)), value
        assert len(value) == 2, value
        assert isinstance(value[0], (int, long, float)), value
        assert isinstance(value[1], (int, long, float)), value
        assert value[0] <= value[1], value
    return True

def check_is_lazy_object(value):
    assert value.__class__.__name__ == "__proxy__", type(value)
    return True

def check_is_string(value):
    assert isinstance(value, basestring) and value, value
    return True

def check_is_int(value):
    assert isinstance(value, (int, long)), value
    return True

def check_is_email(email):
    assert email_re.match(email)

def check_is_slug(value):
    assert isinstance(value, basestring) and value and " " not in value, repr(value)
    return True

def check_is_bool(value):
    assert isinstance(value, bool), value
    return True

def check_is_list(value):
    assert isinstance(value, collections.Sequence), value
    return True

def check_is_dict(value):
    assert isinstance(value, collections.Mapping), value
    return True

def check_num_keys(value, num):
    assert len(value.keys()) == num, (value, num)
    return True

def check_positive_int(value, non_zero=True):
    assert isinstance(value, (int, long))
    assert value >= 0
    if non_zero:
        assert value != 0
    return True

def assert_sets_equal(set1, set2):

    # in case they are lists
    set1 = set(set1)
    set2 = set(set2)

    exceeding_keys1 = set1 - set2
    if exceeding_keys1:
        raise ValueError("Exceeding keys in first set: %r" % repr(exceeding_keys1))

    exceeding_keys2 = set2 - set1
    if exceeding_keys2:
        raise ValueError("Exceeding keys in second set: %r" % repr(exceeding_keys2))

    assert set1 == set2 # else major coding error
    return True




def validate_value(value, validator):

    if issubclass(type(validator), types.TypeType) or isinstance(validator, (list, tuple)): # should be a list of types
        assert isinstance(value, validator)

    elif isinstance(validator, collections.Callable):
        res = validator(value)
        assert res, (repr(res), repr(validator))

    else:
        raise RuntimeError("Invalid configuration validator %r for value %r" % (validator, value))


def check_dictionary_with_template(my_dict, template, strict=False):
    # checks that the keys and value types of a dictionary matches that of a template

    if strict:
        assert_sets_equal(my_dict.keys(), template.keys())
    else:
        for key in template.keys():
            assert key in my_dict.keys(), key

    for key in template.keys():
        validate_value(my_dict[key], template[key])


def load_yaml_fixture(yaml_file):

    with open(yaml_file, "U") as f:
        raw_data = f.read()

    for (lineno, linestr) in enumerate(raw_data.split(b"\n"), start=1):
        if b"\t" in linestr:
            raise ValueError(
                "Forbidden tabulation found at line %d in yaml file %s : '%r'!" % (lineno, yaml_file, linestr))

    new_data = yaml.load(raw_data)

    return new_data





### Date operations ###

def utc_to_local(utc_time):
    timedelta = datetime.now() - datetime.utcnow()
    return utc_time + timedelta



def compute_remote_datetime(delay_mn):
    # delay can be a number or a range (of type int or float)
    # we always work in UTC

    new_time = datetime.utcnow()

    if delay_mn:
        if not isinstance(delay_mn, (int, long, float)):
            delay_s_min = int(60 * delay_mn[0])
            delay_s_max = int(60 * delay_mn[1])
            assert delay_s_min <= delay_s_max, "delay min must be < delay max"

            delay_s = random.randint(delay_s_min, delay_s_max) # time range in seconds


        else:
            delay_s = 60 * delay_mn  # no need to coerce to integer

        #print "DELAY ADDED : %s s" % delay_s

        new_time += timedelta(seconds=delay_s)

    return new_time


def is_past_datetime(dt):
    # WARNING - to compute delays, we always work in UTC TIME
    return (dt <= datetime.utcnow())





@contextlib.contextmanager
def exception_swallower():
    """
    When called, this function returns a context manager which
    catches and logs all exceptions raised inside its
    block of code (useful for rarely crossed try...except clauses,
    to swallow unexpected name or string formatting errors).
    """

    try:
        yield
    except Exception, e:
        try:
            logging.critical(_("Unexpected exception occurred in exception swallower context : %r !"), e, exc_info=True)
        except Exception:
            print >> sys.stderr, _("Exception Swallower logging is broken !!!")

        if __debug__:
            raise RuntimeError(_("Unexpected exception occurred in exception swallower context : %r !") % e)
