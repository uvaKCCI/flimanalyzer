#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import numpy as np

from flim.core.filter import RangeFilter
from flim.plugin import plugin
import flim.tools.data as tools
from flim.plugin import AbstractPlugin


@plugin(plugintype="Data")
class Filter(AbstractPlugin):
    def __init__(self, name="Filter", **kwargs):
        AbstractPlugin.__init__(
            self, name=name, **kwargs
        )  # categories={}, default='unassigned')
        default_filters = [
            RangeFilter("trp t1", 0, 2500).get_params(),
            RangeFilter("trp t2", 0, 8000).get_params(),
            RangeFilter("trp tm", 0, 4000, selected=False).get_params(),
            RangeFilter("trp a1[%]", 0, 100).get_params(),
            RangeFilter("trp a2[%]", 0, 100).get_params(),
            RangeFilter("trp a1[%]/a2[%]", 0, 2).get_params(),
            RangeFilter("trp E%1", 0, 100).get_params(),
            RangeFilter("trp E%2", 0, 100).get_params(),
            RangeFilter("trp E%3", 0, 100).get_params(),
            RangeFilter("trp r1", 0, 15).get_params(),
            RangeFilter("trp r2", 0, 3).get_params(),
            RangeFilter("trp r3", 0, 3).get_params(),
            RangeFilter("trp chi", 0, 4.7).get_params(),
            RangeFilter("trp photons", 0, 160).get_params(),
            RangeFilter("NAD(P)H a1", 10, 800, selected=True).get_params(),
            RangeFilter("NAD(P)H a1[%]", 0, 100).get_params(),
            RangeFilter("NAD(P)H a2", 5, 300, selected=True).get_params(),
            RangeFilter("NAD(P)H a2[%]", 0, 100).get_params(),
            RangeFilter("NAD(P)H t1", 10, 1000, selected=True).get_params(),
            RangeFilter("NAD(P)H t2", 2000, 7000, selected=True).get_params(),
            RangeFilter("NAD(P)H tm", 0, 2000).get_params(),
            RangeFilter("NAD(P)H photons", 10, 2000, selected=True).get_params(),
            RangeFilter("NAD(P)H a2[%]", 0, 100).get_params(),
            RangeFilter("NADPH %", 0, 99).get_params(),
            RangeFilter("NADH %", 0, 100).get_params(),
            RangeFilter("NADPH/NADH", 0, 3).get_params(),
            RangeFilter("NAD(P)H chi", 0.7, 2.0).get_params(),
            RangeFilter("FAD t1", 10, 1500, selected=True).get_params(),
            RangeFilter("FAD t2", 1000, 6000, selected=True).get_params(),
            RangeFilter("FAD tm", 0, 2500).get_params(),
            RangeFilter("FAD a1", 10, 800, selected=True).get_params(),
            RangeFilter("FAD a1[%]", 0, 100).get_params(),
            RangeFilter("FAD a2", 5, 300, selected=True).get_params(),
            RangeFilter("FAD a2[%]", 0, 100).get_params(),
            RangeFilter("FAD a1[%]/a2[%]", 0, 16).get_params(),
            RangeFilter("FLIRR", 0, 2.4).get_params(),
            RangeFilter("FAD chi", 0.7, 2.0).get_params(),
            RangeFilter("FAD photons", 10, 2000, selected=True).get_params(),
            RangeFilter("FAD photons/NAD(P)H photons", 0, 2).get_params(),
        ]
        self.default_filters = {filter["name"]: filter for filter in default_filters}

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return []

    def _sort_category(values, sort_algo):
        return values

    def _update_filter_params(self, data, filter_params=[]):
        updated_params = []
        if data is not None:
            number_cols = list(data.select_dtypes(np.number).columns.values)
            updated_params = [
                fparam for fparam in filter_params if fparam["name"] in number_cols
            ]
            existing_names = [fparam["name"] for fparam in filter_params]
            missing_names = [n for n in number_cols if n not in existing_names]
            # create defaults for missing filters
            for col in missing_names:
                fparams = self.default_filters.get(col, RangeFilter(col).get_params())
                updated_params.append(fparams)
        return updated_params

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "category_filters": {},
                "range_filters": self._update_filter_params(None),
                "use": True,
                "show_dropped": False,
                "inplace": False,
            }
        )
        return params

    def output_definition(self):
        return {"Table: Filtered": None}

    def execute(self):
        return self.run_tool(tools.Filter, list(self.input.values())[0])
