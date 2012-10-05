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

from string import *
import re
def isNotStandardAttr(name, attrs=dir(3) + [ '__main__', '__module__' ]):
    return not name in attrs
def isAtom(obj):
    """ simple object's predicate,
    such object hasn't got any data field excepting standard ones
    and it isn't dictionary nor list
    """
    tobj = type(obj)
    if tobj is list or tobj is dict or tobj is tuple: return False
    for attr in dir(obj):
        if isNotStandardAttr(attr):
            if not callable(getattr(obj, attr)):
                return False
    return True

def isComplexClass(obj):
    tobj = type(obj)
    return (not isAtom(obj))
    return (not tobj is list) and (not tobj is dict) and (not tobj is tuple) and (not isAtom(obj))
""" Complex objects are printed in a column, but
simple objects are printed in a line until it overflow. 
"""
def foldLongString(string, curTab , minTab, width, minForceBreakable):
    """ curTab is a place where current line ends.
    minTab is a minimal indent at begin of line
    minForceBreakable is a minimal substring's length which can be cut from string
    """
    if curTab < minTab: raise ValueError ("current tab (%d) is less than mininum tab (%d)" % (curTab, minTab))
    if curTab > width: raise ValueError ("current tab (%d) is more than width (%d)" % (curTab, width))
    if minTab > width: raise ValueError ("minimum tab (%d) is more than width (%d)" % (minTab, width))

    def next(s): return "\n" + " "*minTab + foldLongString(s, minTab, minTab, width, minForceBreakable)
    wMt = width - curTab
    if len(string) >= wMt:
        # there is search of comfortable position for string division (where is a space)
        head = string[:wMt]
        spacePos = rfind (head, " ")
        if spacePos < wMt / 2: # a space is to far
            if wMt < minForceBreakable and minForceBreakable < width - minTab:
                # cutted piece is too short then entire word is moved
                return next(string)
            else:
                rest = string[wMt:]
                return head + next(rest)
        else:
            return string[:spacePos] + next(string[spacePos + 1:])
    else:
        return string

def printObject(obj, curTab=0, minTab=0, width=80, step=2, minForceBreakable=4):
    """
    printObject is package's main function. It prints object's data
    fields to stdout. If object's field is a complex object then the library
    prints its state recursively and so on.

    Warning! The library haven't support cycle bundles yet.

    Arguments: curTab is a distance from start line to current
    position in a line. curTab cannot be less than minTab. Usually you
    shouldn't change the curTab.

    width is maximal line's width. 

    step is a step of tab increasing.

    minForceBreakable is a minimal length of first word piece which
    can be left after divisioning on current line, and second word
    piece is moved to next line; If first piece is too short then the
    word isn't divided and it is moved to next line entirely.
    """
    if curTab < minTab: raise ValueError ("current tab (%d) is less than mininum tab (%d)" % (curTab, minTab))
    if curTab > width: raise ValueError ("current tab (%d) is more than width (%d)" % (curTab, width))
    if minTab > width: raise ValueError ("minimum tab (%d) is more than width (%d)" % (minTab, width))
    if step < 0: raise ValueError ("step (%d) must be equal or more than 0" % step)
    if width < 3: raise ValueError ("width (%d) must be more than 2" % width)
    res = traceObject(obj, curTab, minTab , width , step , minForceBreakable, False)
    print re.sub("\n *$", "", res)

def traceObject(obj, curTab=0, minTab=0, width=80, step=2, minForceBreakable=4, enclosedIntoClass=False):
    if curTab < minTab: raise ValueError ("current tab (%d) is less than mininum tab (%d)" % (curTab, minTab))
    if curTab > width: raise ValueError ("current tab (%d) is more than width (%d)" % (curTab, width))
    if minTab > width: raise ValueError ("minimum tab (%d) is more than width (%d)" % (minTab, width))
    if isAtom(obj):
        return foldLongString (str(obj) + " :: " + type(obj).__name__ , curTab, minTab, width, minForceBreakable)
    # a list
    tobj = type(obj)
    if tobj is list:
        return printListOrTuple(obj, curTab , minTab, width, step, minForceBreakable)
    if tobj is tuple:
        return printListOrTuple(obj, curTab , minTab, width, step, minForceBreakable, "( ", " )")
    # a dictionary
    if tobj is dict:
        return printDict(obj, curTab , minTab, width, step, minForceBreakable)
    # compound object
    return printCompound(obj, curTab , minTab, width, step, minForceBreakable, enclosedIntoClass)

def foldTwoStrings(string1, string2, curTab, minTab, width):
    """it joins strings string1 and string2.
        curTab is position of last letter of last line in string1
    """
    posLastEnter = rfind(string2 , "\n")
    # позици�? в �?троке
    if posLastEnter >= 0: #   объект не уме�?тил�?�? на той же �?троке
        curTab = len(string2) - rfind(string2, "\n") - 1
    else:
        curTab = curTab + len(string2)
    return (string1 + string2, curTab)

def appendFoldIfLong(string1, string2, curTab, minTab, width):
    """it adds short string (string2) to buffer (string1) controlling its length"""
    if len(string2) > width - curTab:
        curTab = minTab
        string1 += "\n" + (" "*minTab) + string2
    else:
        curTab += len(string2)
        string1 += string2
    return (string1, curTab)

def printListOrTuple(lst, curTab , minTab, width, step, minForceBreakable, openBrace="[ ", closeBrace=" ]"):
    openSeq = openBrace
    res = openSeq
    curTab += len(openSeq)
    if width < curTab:
        curTab = minTab + len(openSeq)
        res = "\n" + res
    newMinTab = minTab + step
    for elem in lst:
        if isComplexClass(elem):
            curTab = newMinTab
            res += "\n" + " "*newMinTab
        strElem = traceObject(elem, curTab, newMinTab, width, step, minForceBreakable)
        res, curTab = foldTwoStrings(res, strElem, curTab, newMinTab, width)
        # add comma
        res, curTab = appendFoldIfLong (res, ", ", curTab, newMinTab, width)
    if len(res) > 2:
        # test for division is redundant 
        res = res[:-2] + closeBrace[:2]
        closeBrace = closeBrace[2:]
        if closeBrace:
            res, curTab = appendFoldIfLong(res , closeBrace, curTab, newMinTab, width)
            return res
        return res
    else:
        return strip(openBrace) + strip(closeBrace)

def printDict(dct, curTab , minTab, width, step, minForceBreakable):
    """
    print dictionary <dct>
    """
    res = "{ "
    curTab += 2
    if width < curTab:
        curTab = minTab + 2
        res = "\n" + res
    newMinTab = minTab + step
    dctKeys = dct.keys()
    dctKeys.sort()
    for key in dctKeys:
        if isComplexClass(key):
            curTab = newMinTab
            res += "\n" + " "*newMinTab
        strKey = traceObject(key, curTab, newMinTab, width, step, minForceBreakable)
        res, curTab = foldTwoStrings (res, strKey, curTab, newMinTab, width)
        # add colons
        res, curTab = appendFoldIfLong (res, " : ", curTab, newMinTab, width)
        if isComplexClass(dct[key]):
            curTab = newMinTab
            res += "\n" + " "*newMinTab
        strVal = traceObject(dct[key], curTab, newMinTab, width, step, minForceBreakable)
        res, curTab = foldTwoStrings (res, strVal, curTab, newMinTab, width)
        # add comma
        res, curTab = appendFoldIfLong (res, ", ", curTab, newMinTab, width)
    if len(res) > 2:
        return res[:-2 ] + " }"
    else:
        return "{}"


def printCompound(obj, curTab , minTab, width, step, minForceBreakable, enclosedIntoClass):
    """ print a compound obje�?t --- some class with data fields"""
    newMinTab = minTab + step
    theMinTab = "\n" + newMinTab * " "
    res, curTab = appendFoldIfLong ("", "class " + obj.__class__.__name__ + ":", curTab, minTab, width)
    for attr in dir(obj):
        if isNotStandardAttr(attr):
            theAttr = getattr(obj, attr)
            if not callable(theAttr):
                res += theMinTab
                curTab = newMinTab
                res += attr + " = "
                curTab += len(attr + " = ")
                strAttr = traceObject(theAttr, curTab, curTab, width, step, minForceBreakable, True)
                res, curTab = foldTwoStrings(res, strAttr, curTab, newMinTab, width)
    if not enclosedIntoClass: res += "\n" + " " * minTab
    return res

