#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  4 04:02:09 2018

@author: khs3z
"""

import logging
import os
import re
import importlib
import pkgutil


def get_available_parsers(pkdir="core.parser"):
    for module_loader, name, ispkg in pkgutil.iter_modules([pkdir]):
        importlib.import_module("." + name, __package__)
    parser_classes = {cls.__name__: cls for cls in defaultparser.__subclasses__()}
    return parser_classes


def instantiate_parser(fullname):
    namesplit = fullname.rpartition(".")
    if len(namesplit) != 3:
        return None
    modulename = fullname.rpartition(".")[0]
    classname = fullname.rpartition(".")[2]
    logging.debug(f"Parser modulename={modulename}, classname={classname}")
    try:
        module = importlib.import_module(modulename)
        class_ = getattr(module, classname)
        parserinstance = class_()
    except Exception:
        logging.error(f"Error instantiating {fullname} parser.")
        logging.error(Exception)
        parserinstance = None
    return parserinstance


# keys of a pattern: {PATTERN_USE: bool, PATTERN_CATEGORY: column, PATTERN_REGEX: regex}
PATTERN_USE = "Use"
PATTERN_CATEGORY = "Category"
PATTERN_REGEX = "Regex"


class defaultparser(object):
    def __init__(self):
        self.init_patterns()
        self.compile_patterns()

    def is_readonly(self):
        return True

    def get_name(self):
        return "Default Parser"

    def init_patterns(self):
        self.regexpatterns = []

    def compile_patterns(self):
        if self.regexpatterns is not None and len(self.regexpatterns) > 0:
            self.compiledpatterns = {
                rp[PATTERN_CATEGORY]: re.compile(rp[PATTERN_REGEX])
                for rp in self.regexpatterns
                if rp[PATTERN_USE]
            }
        else:
            self.compiledpatterns = {}

    def settings(self):
        """The parser (its class name) and its patterns, as ParserSettings."""
        from flim.core.settings import ParserSettings

        return ParserSettings(parser=type(self).__name__, patterns=self.regexpatterns)

    def get_regexpatterns(self):
        return self.regexpatterns

    def set_regexpatterns(self, patterns):
        self.regexpatterns = patterns
        self.compile_patterns()

    def parsefilename(self, fname):
        components = {
            "Directory": os.path.dirname(fname),
            "File": os.path.basename(fname),
        }
        fname = fname.replace("\\", "/")
        for entry in self.regexpatterns:
            # convert \ in windows style path to / in POSIX style
            if entry[PATTERN_USE]:
                match = re.search(entry[PATTERN_REGEX], fname)
                if match is not None:
                    matchstr = match.group(1)
                    if match.group(1) == "":
                        components[entry[PATTERN_CATEGORY]] = "?"
                    else:
                        components[entry[PATTERN_CATEGORY]] = str(matchstr)
        return components


class no_parser(defaultparser):
    def set_regexpatterns(self, patterns):
        pass

    def parsefilename(self, fname):
        return {}


class celltype_compartment_fov_treatment_cell_parser(defaultparser):
    def init_patterns(self):
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell line",
                PATTERN_REGEX: r".*/(.*?)/.*/",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Compartment",
                PATTERN_REGEX: r".*/(.*?)/",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class compartment_fov_treatment_cell_parser(defaultparser):
    def init_patterns(self):
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Compartment",
                PATTERN_REGEX: r".*/(.*?)/",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class compartment_treatment_fov_cell_parser(defaultparser):
    def init_patterns(self):
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Compartment",
                PATTERN_REGEX: r".*/(.*?)/",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class fov_treatment_cell_parser(defaultparser):
    def init_patterns(self):
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


#                'FOV':r'[_-](.*?)[_-]',
#                'Treatment':r'[_-].*?[_-](.*?)[_-]',
#                'Cell':r'[_-].*?[_-].*?[_-](\d*?)\.'}


class treatment_fov_cell_parser(defaultparser):
    def init_patterns(self):
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class treatment_fov_time_parser(defaultparser):
    def init_patterns(self):
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Time",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class treatment_time_parser(defaultparser):
    def init_patterns(self):
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Time",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](\d*?)\.",
            },
        ]


class fov_time_well_parser(defaultparser):
    def init_patterns(self):
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Time",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Well",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](.*?)\.",
            },
        ]


# class hyphenparser(defaultparser):
#
#    def init_patterns(self):
#        self.regexpatterns = {
#                'Treatment':r'[-](\d+?)',
#                'FOV':r'[-]\d*(\D+?)[_-]',
#                'Cell':r'[-].*?[_-].*?[_](\d*?)\.'}
