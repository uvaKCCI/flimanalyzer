#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

from flim.plugin import plugin
import flim.tools.data as tools
from flim.plugin import AbstractPlugin


@plugin(plugintype="Data")
class CategoryOrder(AbstractPlugin):
    def __init__(self, name="Order Categories", **kwargs):
        AbstractPlugin.__init__(
            self, name=name, **kwargs
        )  # categories={}, default='unassigned')

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return []

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "categories": {},
                "inplace": False,
            }
        )
        return params

    def execute(self):
        return self.run_tool(tools.CategoryOrder, list(self.input.values())[0])
