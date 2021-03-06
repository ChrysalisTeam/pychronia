# -*- coding: utf-8 -*-



### NO import from pychronia_game.common, else circular import !! ###

import io
import sys, os, collections.abc, logging, inspect, types, traceback, re, glob, copy
import yaml, random, contextlib
from collections.abc import Callable
from collections import Counter, OrderedDict
from datetime import datetime, timedelta

import ZODB  # must be first !
import transaction
from persistent import Persistent
from persistent.mapping import PersistentMapping
from persistent.list import PersistentList

from django_zodb import database
from django.conf import settings as django_settings
from django.template import Template, Context

from .. import default_game_settings

# NOT very safe, borrowed from old Django, and adding brackets
email_re = re.compile(
    r"(^\[?[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
    # quoted-string, see also http://tools.ietf.org/html/rfc2822#section-3.2.5
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011\013\014\016-\177])*"'
    r')\]?@((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$)'  # domain
    r'|\[(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\]$',
    re.IGNORECASE)  # literal form, ipv4 address (SMTP 4.1.3)


class Conf(object):
    """
    Helper class which handles default game settings.
    """

    def __getattr__(self, name):
        try:
            return getattr(django_settings, name)
        except AttributeError:
            return getattr(default_game_settings, name)

    def __setattr__(self, name, value):
        raise NotImplementedError("Game conf is currently readonly")


config = Conf()
del Conf


def safe_copy(value):
    """
    dict.copy() and copy.copy() are not safe regarding ZODB persistent objects, 
    so we use our own function.
    """
    if isinstance(value, (dict, PersistentMapping)):
        return dict(value)
    elif isinstance(value, (list, PersistentList)):
        return list(value)
    else:
        return copy.copy(value)


def normalize(v):
    """
    Mainly used for strings, so that their yaml dump has a pretty format.
    """
    if hasattr(v, "strip"):
        v = v.strip(" \t")  # we LET extra newlines, might be necessary for RST markups
        v = v.replace("\r\n", "\n")  # all UNIX newlines
        v = re.sub("[ \t]+\n", "\n", v, flags=re.MULTILINE)  # remove trailing spaces/tabs at ends of regular lines
    return v


## Python <-> ZODB types conversion and checking ##

ATOMIC_PYTHON_TYPES = (type(None), int, int, float, str, datetime, Callable)

python_to_zodb_types = {list: PersistentList,
                        dict: PersistentMapping,
                        str: lambda x: normalize(x),
                        str: lambda x: normalize(x)}
zodb_to_python_types = dict((value, key) if isinstance(value, type) else (key, value)  # NOT ALL are reversed
                            for (key, value) in list(python_to_zodb_types.items()))

allowed_zodb_types = (tuple, PersistentMapping, PersistentList) + ATOMIC_PYTHON_TYPES
allowed_python_types = (tuple, dict, list) + ATOMIC_PYTHON_TYPES


def usage_assert(value, comment=None):
    from pychronia_game.common import UsageError
    if not value:
        raise UsageError("Check failed: %r (comment: %r)" % (value, comment))
    return True


class Enum(set):
    """
    Takes a string of values, or a list, and exposes the corresponding enumeration.
    """

    def __init__(self, iterable=[]):
        set.__init__(self)
        self.update(iterable)

    def update(self, iterable):
        if isinstance(iterable, str):
            iterable = iterable.split()
        set.update(self, iterable)

    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError(name)


class SDICT(dict):
    def __getitem__(self, name):
        try:
            return dict.__getitem__(self, name)
        except KeyError:
            logging.critical("Wrong key %s looked up in dict %r", name, self)
            return "<UNKNOWN>"

    ''' obsolete
    def SDICT(**kwargs):
        import collections
        # TODO - log errors when wrong lookup happens!!!
        mydict = collections.defaultdict(lambda: "<UNKNOWN>") # for safe string substitutions
        for (name, value) in kwargs.items():
            mydict[name] = value # we mimic the normal dict constructor
        return mydict
    '''

''' FIXME REMOVE THIS
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
'''

def open_zodb_url(zodb_url):
    db = database.get_database_from_uris([zodb_url])
    return db


def open_zodb_file(zodb_file):
    #print ("RETRIEVING DB FROM FILE", zodb_file)
    url = "file:///" + zodb_file.replace("\\", "/")  # note the 3 "/" after scheme!
    return open_zodb_url(url)
    # .replace(":", "|") # or "mem://"    # we have problems with URIs in win32, so replace : with |
    #print (">>>>>>", URI)


def convert_object_tree(tree, type_mapping):
    """
    Recursively transforms a tree of objects (lists, dicts, instances...)
    into an equivalent structure with alternative types.
    
    Operations might occur IN PLACE.
    """

    for (A, B) in list(type_mapping.items()):
        if isinstance(tree, A):
            tree = B(tree)
            break

    if isinstance(tree, ATOMIC_PYTHON_TYPES):
        return tree  # Warning - we must thus avoid infinite recursion on character sequences (aka strings)...
    elif isinstance(tree, collections.abc.MutableSequence):
        for (index, item) in enumerate(tree):
            tree[index] = convert_object_tree(item, type_mapping)
    elif isinstance(tree, collections.abc.MutableMapping):
        for (key, value) in sorted(tree.items()):
            tree[key] = convert_object_tree(value, type_mapping)
    elif isinstance(tree, collections.abc.MutableSet):
        for value in tree:
            tree.remove(value)
            tree.add(convert_object_tree(value, type_mapping))
    elif isinstance(tree, tuple):
        tree = tuple(convert_object_tree(value, type_mapping) for value in tree)
    elif hasattr(tree, "__dict__"):
        for (key, value) in list(tree.__dict__.items()):
            setattr(tree, key, convert_object_tree(value, type_mapping))
    else:
        raise ValueError("Can't handle value %r (type=%s) in convert_object_tree" % (tree, type(tree)))
    return tree


def check_object_tree(tree, allowed_types, path):

    if not isinstance(tree, allowed_types):
        raise RuntimeError("Bad object type detected : %s - %s via path %s" % (type(tree), tree, path))

    if isinstance(tree, ATOMIC_PYTHON_TYPES):
        return
    elif isinstance(tree, collections.abc.MutableSequence):
        for (index, item) in enumerate(tree):
            check_object_tree(item, allowed_types, path + [index])
    elif isinstance(tree, collections.abc.MutableMapping):
        for (key, value) in reversed(sorted(tree.items())):
            check_object_tree(value, allowed_types, path + [key])
    elif isinstance(tree, collections.abc.MutableSet):
        for value in tree:
            check_object_tree(value, allowed_types, path + ["<set-item>"])
    elif isinstance(tree, tuple):
        for value in tree:
            check_object_tree(value, allowed_types, path + ["<tuple>"])
    elif hasattr(tree, "__dict__"):
        for (key, value) in list(tree.__dict__.items()):
            check_object_tree(value, allowed_types, path + [key])
    else:
        raise ValueError("Can't check value %r (type=%s) in check_object_tree" % (tree, type(tree)))


def substract_lists(available_gems, given_gems):
    """
    Returns None if operation is impossible.
    """
    available_gems = Counter(available_gems)
    given_gems = Counter(given_gems)

    if (given_gems & available_gems) != given_gems:
        return None  # operation impossible

    gems_remaining = available_gems - given_gems
    return PersistentList(gems_remaining.elements())


def add_to_ordered_dict(odict, idx, name, value):
    """
    returns the altered ordered dict.
    """
    data = list(odict.items())
    data.insert(idx, (name, value))
    return OrderedDict(data)


def string_similarity(first, second):
    """Find the Levenshtein distance between two strings.
    Returns a positive integer, with 0 <-> identity."""
    if len(first) > len(second):
        first, second = second, first
    if len(second) == 0:
        return len(first)
    first_length = len(first) + 1
    second_length = len(second) + 1
    distance_matrix = [[0] * second_length for _ in range(first_length)]
    for i in range(first_length):
        distance_matrix[i][0] = i
    for j in range(second_length):
        distance_matrix[0][j] = j
    for i in range(1, first_length):
        for j in range(1, second_length):
            deletion = distance_matrix[i - 1][j] + 1
            insertion = distance_matrix[i][j - 1] + 1
            substitution = distance_matrix[i - 1][j - 1]
            if first[i - 1] != second[j - 1]:
                substitution += 1
            distance_matrix[i][j] = min(insertion, deletion, substitution)
    return distance_matrix[first_length - 1][second_length - 1]


def remove_duplicates(seq):
    """
    Remove duplicates (in the "equality" sense) from a sequence, without requiring hashability.
    Preserves order of elements, and first elements win.
    """
    res = []
    for item in seq:
        if item not in res:
            res.append(item)
    return res


def sanitize_query_dict(query_dict):
    """
    We remove terminal '[]' in request data keys and replace enforce their value to be a list
    to allow mapping of these to methods arguments (which can't contain '[]').
    
    *query_dict* must be mutable.
    """
    for key in query_dict:
        if key.endswith("[]"):  # standard js/php array notation
            new_key = key[:-2]
            query_dict[new_key] = query_dict.getlist(key)
            del query_dict[key]
    #print ("NE QUERY DICT", query_dict)
    return query_dict


def adapt_parameters_to_func(all_parameters, func):
    """
    Strips unwanted parameters in a dict of parameters (eg. obtained via GET or POST),
    and ensures no argument is missing.

    Returns a dict of relevant parameters, or raises common signature exceptions.
    """

    (args, _varargs, keywords, _defaults) = inspect.getargspec(func)
    ##print("########>>>", func, all_parameters, args)

    if keywords is not None:
        relevant_args = all_parameters  # exceeding args will be handled properly
    else:
        relevant_args = dict((key, value) for (key, value) in list(all_parameters.items()) if key in args)

    try:
        #print("#<<<<<<<", func, relevant_args)
        inspect.getcallargs(func, **relevant_args)
    except (TypeError, ValueError) as e:
        raise  # signature problem, probably

    return relevant_args


def load_multipart_rst(val):
    if val is None or isinstance(val, str):
        return val
    assert isinstance(val, (list, tuple))
    return "\n\n".join(val)  # we assume a sequence of strings dedicated to restructuredtext format!


# IMPORTANT - globally registered encoder for unicode strings and OrderedDict #
yaml.add_representer(str, lambda dumper, value: dumper.represent_scalar('tag:yaml.org,2002:str', value))

_mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG


def dict_representer(dumper, data):
    return dumper.represent_dict(iter(list(data.items())))


def dict_constructor(loader, node):
    return OrderedDict(loader.construct_pairs(node))


yaml.add_representer(OrderedDict, dict_representer)
yaml.add_constructor(_mapping_tag, dict_constructor)


def write_to_file(filename, content):
    """Write an Unicode string to a file in utf8 encoding."""
    with open(filename, "w", encoding="utf8") as f:
        f.write(content)


def dump_data_tree_to_yaml(data_tree, convert_types=True, **kwargs):
    """
    BEWARE - if the end of a string is made of spaces, the double-quotes dump style is forced,
    see (http://sourceforge.net/p/yaml/mailman/message/30159253/)
    
    Valid keywords for the method def dump(data, stream=None, Dumper=Dumper, **kwds) in python-yaml :
    
        default_style : indicates the style of the scalar. Possible values are None, '', '\'', '"', '|', '>'.

        default_flow_style :  indicates if a collection is block or flow. The possible values are None, True, False.

        canonical : if True export tag type to the output file

        indent :  sets the preferred indentation

        width : set the preferred line width

        allow_unicode : allow unicode in output file

        line_break : specify the line break you need

        encoding : output encoding, defaults to utf-8

        explicit_start : if True, adds an explicit start using “—”

        explicit_end: if True, adds an explicit end using “—”

        version : version of the YAML parser, tuple (major, minor), supports only major version 1

        tags : I didn’t find any information about this parameter … and no time to test it ;-). Comments are welcome !

    Returns an unicode string.
    """
    if convert_types:
        data_tree = convert_object_tree(data_tree, zodb_to_python_types)

    dump_args = dict(width=100,  # NOT canonical
                     indent=4,
                     default_style="|",
                     default_flow_style=False,  # not BLOCK
                     allow_unicode=True,
                     Dumper=yaml.Dumper)
    dump_args.update(kwargs)

    string = yaml.dump(data_tree, **dump_args)

    assert isinstance(string, str), string
    return string


def load_data_tree_from_yaml(string, convert_types=True):
    assert "Ã©" not in string  # corrupted utf8 input...
    data_tree = yaml.load(string, Loader=yaml.FullLoader)  # FullLoader necessary for python tuples

    if convert_types:
        data_tree = convert_object_tree(data_tree, python_to_zodb_types)

    return data_tree


## Tools for database sanity checks ##



def check_no_duplicates(value):
    usage_assert(len(set(value)) == len(value), value)
    return True


def check_is_range_or_num(value):
    if isinstance(value, (int, float)):
        pass  # nothing to check
    else:
        usage_assert(isinstance(value, (tuple, PersistentList)), value)
        usage_assert(len(value) == 2, value)
        usage_assert(isinstance(value[0], (int, float)), value)
        usage_assert(isinstance(value[1], (int, float)), value)
        usage_assert(value[0] <= value[1], value)
    return True


def check_is_lazy_translation(value):
    from django.utils.functional import Promise
    usage_assert(isinstance(value, Promise), type(value))
    return True


def check_is_string(value, multiline=True, forbidden_chars=None, empty=False, comment=None):
    usage_assert(isinstance(value, str), value or comment)
    if not empty:
        usage_assert(value.strip(), comment)
    if not multiline:
        usage_assert("\n" not in value, comment)
    if forbidden_chars:
        usage_assert(not any(x in value for x in forbidden_chars), comment)
    return True


""" TODO : use this utility in datamanager checks!
def check_is_ascii_string(value)
    try:
        value.encode("ascii")
    except (TypeError, ValueError) as e:
        raise UsageError(.......)
"""

def check_is_float(value):
    usage_assert(isinstance(value, (int, float)), value)  # integers are considered as floats too!!
    return True


def check_is_int(value):
    usage_assert(isinstance(value, int), value)
    return True


def check_is_datetime(value):
    usage_assert(isinstance(value, datetime), value)
    return True


def check_is_email(value):
    assert value == value.strip()
    usage_assert(email_re.match(value), value)
    return True


def check_is_slug(value):
    usage_assert(isinstance(value, str) and value, repr(value))
    usage_assert(" " not in value, repr(value))
    usage_assert("\n" not in value, repr(value))
    return True


def check_is_bool(value):
    usage_assert(isinstance(value, bool), value)
    return True


def check_is_in_set(value, main_set):
    usage_assert(value in main_set, (value, main_set))
    return True


def check_is_subset(value, main_set):
    usage_assert(set(value) <= set(main_set), (value, main_set))
    return True


def check_is_list(value):
    usage_assert(isinstance(value, collections.abc.Sequence), value)
    return True


def check_is_dict(value):
    usage_assert(isinstance(value, collections.abc.Mapping), value)
    return True


def check_has_keys(value, keys, strict=False):
    actual_keys = list(value.keys())
    if strict:
        usage_assert(len(actual_keys) == len(keys))
    for key in keys:
        usage_assert(key in actual_keys, (key, actual_keys))


def check_num_keys(value, num):
    usage_assert(len(list(value.keys())) == num, (value, num))
    return True


def check_num_custom_settings(value, num):
    if "middlewares" in value:
        num += 1  # not counted by default
    return check_num_keys(value, num)


def check_is_positive_float(value, non_zero=True):
    check_is_float(value)
    usage_assert(value >= 0)
    if non_zero:
        usage_assert(value != 0)
    return True


def check_is_positive_int(value, non_zero=True):
    check_is_int(value)
    usage_assert(value >= 0)
    if non_zero:
        usage_assert(value != 0)
    return True


def check_is_django_template(value):
    assert isinstance(value, str)
    assert render_template_string(value, ctx={}).strip()
    return True


def check_is_restructuredtext(value, strict):
    from pychronia_game.templatetags.helpers import advanced_restructuredtext
    assert isinstance(value, str)  # NOT A LIST
    #print("LOADING RST...", repr(value[0:70]))

    regex = r"""\[\s*(GAME_FILE_URL|GAME_THUMBNAIL_URL).+?\s*]"""
    sanitized_value = re.sub(regex, "http://dummy_check_is_restructuredtext_url/file.flv", value)

    with io.StringIO() as warning_stream:
        output = advanced_restructuredtext(sanitized_value,
                                           report_level=1,
                                           warning_stream=warning_stream)
        usage_assert(output)
        warnings = warning_stream.getvalue()
        if strict and warnings:
            raise ValueError("Restructuredtext format errors for %s...\n%s" % (repr(value[0:70]), warnings))

    return True


def check_is_game_file(filename):
    assert not os.path.isabs(filename)
    fullpath = os.path.join(config.GAME_FILES_ROOT, filename)
    usage_assert(os.path.isfile(fullpath), fullpath)
    return True


def check_is_game_file_or_url(filename):
    """
    Used for field that allow either RELATIVE local game files, or absolute (external) urls.
    """
    if is_absolute_url(filename):
        return filename
    return check_is_game_file(filename)


def is_email(email):
    return bool(email_re.match(email))


def is_absolute_url(string):
    """We do NOT consider that "/my-url/" is absolute, here - we want a really FULL url"""
    return string.startswith(("http://", "https://"))


def find_game_file(*rel_path_glob):
    """
    Returns the SINGLE file called filename, in the glob path join(*rel_path_glob) and its subdirs.
    """
    assert rel_path_glob, rel_path_glob
    game_files_root = config.GAME_FILES_ROOT

    filename = rel_path_glob[-1]
    rel_path_glob = rel_path_glob[:-1]

    if os.path.basename(filename) != filename:  # we already get a relative game file path
        full_file_path = os.path.join(game_files_root, filename)  # we then ignore rel_path_glob
        if not os.path.exists(full_file_path):
            raise RuntimeError("Unexisting game file detected: %r", full_file_path)
        return filename

    if not rel_path_glob:
        search_trees = [game_files_root]
    else:
        rel_path_glob = os.path.join(*rel_path_glob)
        # we hope that game_files_root contains no special chars...
        search_trees = glob.glob(os.path.join(game_files_root, rel_path_glob))
    assert search_trees

    result_folders = []
    for search_tree in search_trees:
        for root, dirs, files in os.walk(search_tree):
            if filename in files:
                result_folders.append(root)
                pass  # for robustness, we keep searching
    if not result_folders:
        raise RuntimeError("Game file %r not found in %r", filename, search_trees)
    elif len(result_folders) > 1:
        raise RuntimeError("Multiple game files with name %r found: %r", filename, result_folders)
    assert len(result_folders)
    full_file_path = os.path.join(result_folders[0], filename)
    assert full_file_path.startswith(game_files_root)
    rel_file_path = os.path.relpath(full_file_path, start=game_files_root)
    assert not os.path.isabs(rel_file_path)
    return rel_file_path


def find_game_file_or_url(*rel_path_globs):
    """
    Used for field that allow either RELATIVE local game files, or absolute (external) urls.
    """
    assert rel_path_globs
    if is_absolute_url(rel_path_globs[-1]):
        return rel_path_globs[-1]
    return find_game_file(*rel_path_globs)


def ___complete_game_file_path(filename, *elements):
    """
    Now SUPERSEDED by find_game_file().
    """
    assert filename
    basename = os.path.basename(filename)
    if basename == filename:
        return os.path.join(*(elements + (filename,)))
    return filename  # already contains dirs...


def _make_elements_hashable(sequence):
    # mass conversion here, eg. for gems that are sequences of unhashable lists
    return [tuple(i) if isinstance(i, (list, PersistentList)) else i for i in sequence]


def _compare_container(a, b):
    exceeding_keys1 = a - b
    if exceeding_keys1:
        raise ValueError("Exceeding keys in first container: %r" % repr(exceeding_keys1))

    exceeding_keys2 = b - a
    if exceeding_keys2:
        raise ValueError("Exceeding keys in second container: %r" % repr(exceeding_keys2))

    usage_assert(a == b)  # else major coding error
    return True


def assert_counters_equal(list1, list2):
    c1 = Counter(_make_elements_hashable(list1))
    c2 = Counter(_make_elements_hashable(list2))
    return _compare_container(c1, c2)


def assert_sets_equal(set1, set2):
    set1 = set(_make_elements_hashable(set1))
    set2 = set(_make_elements_hashable(set2))
    return _compare_container(set1, set2)


def assert_set_smaller_or_equal(set1, set2):
    set1 = set(_make_elements_hashable(set1))
    set2 = set(_make_elements_hashable(set2))
    return usage_assert(set1 <= set2, set1 - set2)


def validate_value(value, validator):
    if issubclass(type(validator), type) or isinstance(validator, (list, tuple)):  # should be a list of types
        usage_assert(isinstance(value, validator), locals())

    elif isinstance(validator, Callable):
        res = validator(value)
        usage_assert(res, (repr(res), repr(validator)))

    else:
        raise RuntimeError("Invalid configuration validator %r for value %r" % (validator, value))


def check_dictionary_with_template(my_dict, template, strict=False):
    # checks that the keys and value types of a dictionary matches that of a template
    #print("==> we check_dictionary_with_template", my_dict, template)
    if strict:
        assert_sets_equal(list(my_dict.keys()), list(template.keys()))
    else:
        usage_assert(set(template.keys()) <= set(my_dict.keys()),
                     comment=(set(template.keys()) - set(my_dict.keys()), my_dict))

    for key in list(template.keys()):
        #print("WE VALIDATE MORE PRECISELY", key, my_dict[key], template[key])
        validate_value(my_dict[key], template[key])


def check_settings_dictionary_with_template(my_dict, template, strict=False):
    my_dict = safe_copy(my_dict)
    my_dict.pop("middlewares", None)  # may or nor exist
    return check_dictionary_with_template(my_dict, template, strict=strict)


def recursive_dict_sum(d1, d2, appendable_fields):
    """Sums dictionaries recursively, depending on the concerned fields."""

    def _append_or_replace(key, a, b):
        if isinstance(a, (list, tuple)) and key in appendable_fields:
            return a + b
        return b  # replace with latest value then!

    if not isinstance(d1, dict) or not isinstance(d2, dict):
        raise ValueError([d1, d2])

    all_keys = list(d1.keys()) + list(d2.keys())
    #print("---->", repr(all_keys)[0:30])
    return dict((k, ((d1[k] if k in d1 else d2[k])
                     if k not in d1 or k not in d2
                     else (_append_or_replace(k, d1[k], d2[k])
                           if not isinstance(d1[k], dict)
                           else recursive_dict_sum(d1[k], d2[k],
                                                   appendable_fields=appendable_fields))))
                for k in set(all_keys))


def load_yaml_file(yaml_file, pretreatment=None, convert_types=False):
    """Load yaml data from a file, without coherence check.

    pretreatment can be a callback applied on the string before it gets actually parsed as yaml.
    """
    logging.info("Loading yaml fixture %s" % yaml_file)
    with open(yaml_file, "r", encoding="utf-8-sig") as f:  # beware of the unicode BOM
        raw_data = f.read()

    for (lineno, linestr) in enumerate(raw_data.split("\n"), start=1):
        if "\t" in linestr:
            raise ValueError(
                "Forbidden tabulation found at line %d in yaml file %s : '%r'!" % (lineno, yaml_file, linestr))

    if pretreatment:
        raw_data = pretreatment(raw_data)
    #print("LOADING RAW DATA", repr(raw_data[:100]))

    data = load_data_tree_from_yaml(raw_data, convert_types=convert_types)
    return data


YAML_FILE_GLOBS = ["*.yaml", "*.yml", "*/*.yaml", "*/*.yml"]  # works on windows too

# fields which should be concatenated instead of replaces, when merging yaml trees
APPENDABLE_FIELDS = """manual_messages_templates messages_dispatched messages_queued game_items""".split()


def load_yaml_fixture(yaml_fixture):
    """
    Can load a single yaml file, or a list of files or directories containing y[a]ml files.
    Each file must only contain a single yaml document (which must be a mapping).
    """

    if isinstance(yaml_fixture, str):
        yaml_entries =  [yaml_fixture]
    else:
        assert isinstance(yaml_fixture, list)
        yaml_entries = yaml_fixture

    data = {}

    for yaml_entry in yaml_entries:

        if not os.path.exists(yaml_entry):
            raise ValueError(yaml_entry)

        if os.path.isfile(yaml_entry):
            yaml_files = [yaml_entry]

        else:
            assert os.path.isdir(yaml_entry)

            yaml_files = [path for pattern in YAML_FILE_GLOBS
                          for path in glob.glob(os.path.join(yaml_entry, pattern))]

        for yaml_file in yaml_files:

            if os.path.basename(yaml_file).startswith("_"):
                continue  # skip deactivated yaml file

            part = load_yaml_file(yaml_file)

            if not isinstance(part, dict):
                raise ValueError("Improper content in %s" % yaml_file)

            data = recursive_dict_sum(data, part, appendable_fields=APPENDABLE_FIELDS)

    return data


### Date operations ###

def utc_to_local(utc_time):
    timedelta = datetime.now() - datetime.utcnow()
    return utc_time + timedelta


def is_past_datetime(dt):
    # WARNING - to compute delays, we always work in UTC TIME
    return (dt <= datetime.utcnow())


def render_template_string(string, ctx):
    """
    Render a string using django templates and the provided context dict.
    """
    t = Template(string)
    c = Context(ctx)
    return t.render(c)


def make_bi_usage_decorator(decorator):
    """
    Transforms a decorator taking default arguments, into a decorator that can both
    be applied directly to a callable, or first parameterized with keyword arguments and then applied.
    
    i.e:
    
        @decorator(a=3, b=5)
        def myfunc...
        
        OR
        
        @decorator # default arguments are applied
        def myfunc...
        
    The trouble is that static code analysis loses track of decorator signature...
    """

    def bidecorator(object=None, **kwargs):
        factory = lambda x: decorator(x, **kwargs)
        if object:
            return factory(object)
        return factory

    return bidecorator


def make_request_querydicts_mutable(request):
    """Screw the immutability of Django QueryDicts, we need FREEDOM"""
    request._post = request.POST.copy()
    request._get = request.GET.copy()
    if hasattr(request, "_request"):
        del request._request  # force regeneration of MergeDict
    assert request._post._mutable and request._get._mutable


class TechnicalEventsMixin(object):
    """
    This private registry keeps track of miscellaneous events sent throughout the datamanager system.
    This feature should solely be used for debugging purpose, with function calls protected by
    ``if __debug__:`` statements for optimization.
    To prevent naming collisions, an error is raised if events with the same name
    are sent from different locations.
    """

    def __init__(self, *args, **kwargs):
        super(TechnicalEventsMixin, self).__init__(*args, **kwargs)
        self._event_registry = {}  # stores, for each event name, a (calling_frame, count) tuple

    def notify_event(self, event_name):
        """
        Records the sending of event *event_name*.
        """
        calling_frame = traceback.extract_stack(limit=2)[0]  # we capture the frame which called notify_event()
        if event_name not in self._event_registry:
            self._event_registry[event_name] = (calling_frame, 1)
        else:
            (old_calling_frame, cur_count) = self._event_registry[event_name]
            if calling_frame != old_calling_frame:
                raise RuntimeError("Duplicated event name %s found for locations '%s' and '%s'" % (
                    event_name, old_calling_frame, calling_frame))
            self._event_registry[event_name] = (calling_frame, cur_count + 1)

    def get_event_count(self, event_name):
        """
        Returns the number of times the event *event_name* has been sent since the last
        clearing of its statistics.
        """
        if event_name not in self._event_registry:
            return 0
        else:
            return self._event_registry[event_name][1]

    def clear_event_stats(self, event_name):
        """
        Resets to 0 the counter of the event *event_name*.
        """
        del self._event_registry[event_name]

    def clear_all_event_stats(self):
        """
        Resets entirely the event system, eg. at the beginning of a test sequence.
        """
        self._event_registry = {}


## conversions between variable naming conventions ##

def to_snake_case(text):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def to_pascal_case(text):
    if "_" in text:
        callback = lambda pat: pat.group(1).lower() + pat.group(2).upper()
        text = re.sub("(\w)_(\w)", callback, text)
        if text[0].islower():
            text = text[0].upper() + text[1:]
        return text
    return text[0].upper() + text[1:]


def to_camel_case(text):
    text = to_pascal_case(text)
    return text[0].lower() + text[1:]
