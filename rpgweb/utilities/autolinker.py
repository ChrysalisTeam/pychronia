# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from bs4 import BeautifulSoup, NavigableString, Tag
import re, functools


clean_parser = functools.partial(BeautifulSoup, features="html.parser")
del BeautifulSoup

SKIPPED_TAGS = ["head", "a", "textarea", "pre", "code"]



def join_regular_expressions_as_disjunction(regexes, as_words=False):
    if as_words:
        regexes = (r"(?:\b" + regex + r"\b)" for regex in regexes)
    else:
        regexes = (r"(?:" + regex + r")" for regex in regexes)
    return "|".join(regexes)


def generate_links(html_snippet, regex, link_attr_generator):

    soup = clean_parser(html_snippet) # that parser doesn't add <html> or <xml> tags

    def generate_link_str(match_obj):
        attrs = link_attr_generator(match_obj)
        tag = soup.new_tag("a", **attrs)
        tag.string = match_obj.group(0) # the entire matched keyword
        return unicode(tag)

    def insert_links(string):
        new_string, occurences = re.subn(regex,
                                         generate_link_str,
                                         string,
                                         flags=re.IGNORECASE | re.UNICODE | re.DOTALL | re.MULTILINE)
        if not occurences:
            assert string == new_string
            None
        else:
            mini_soup = clean_parser(new_string)
            new_children = mini_soup.contents
            return new_children

    def recurse_elements(element):
        children = tuple(element.contents) # we freeze current children, as they'll be modified here
        for child in children: # no enumerate() here, as the tree changes all the time
            if isinstance(child, NavigableString):
                new_children = insert_links(unicode(child))
                if new_children:
                    current_index = element.index(child)
                    child.extract()
                    for new_child in reversed(new_children):
                        element.insert(current_index, new_child)
            elif child.name not in SKIPPED_TAGS: # necessarily a Tag
                recurse_elements(child)

    recurse_elements(soup)
    return unicode(soup)


if __name__ == "__main__":

    #Create the soup
    input = '''<html>
    <head><title>Page title one</title></head>
    <body>
    <p id="firstpara" align="center">This is one paragraph <b>one</b>.</a>
    <a href="http://aaa">This is one paragraph <b>one</b>.</a>
    </html>'''

    res = generate_links(input, "one", lambda x: dict(href="TARGET", title="mytitle"))

    print(res)
