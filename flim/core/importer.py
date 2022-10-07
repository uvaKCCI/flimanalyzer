#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  4 02:53:40 2018

@author: khs3z
"""

import itertools
import logging
import os
import glob
import pandas as pd
import numpy as np

import flim.core.configuration as cfg
<<<<<<< HEAD
from flim.core.parser import  defaultparser
import flim.core.preprocessor as pp

DEFAULT_EXT = ['.txt','.csv']
=======
from flim.core.parser import defaultparser
import flim.core.preprocessor as pp
>>>>>>> prefect

DEFAULT_EXT = [".txt", ".csv"]


class dataimporter:
    def __init__(self):
        self.files = []
        self.delimiter = "\t,"
        self.data = pd.DataFrame()
        self.excluded_files = []
        self.parser = defaultparser()
        self.preprocessor = None
<<<<<<< HEAD
        self.combolist = None
    
    def get_config(self):
        config = {
                cfg.CONFIG_EXCLUDE_FILES: self.excluded_files,
                cfg.CONFIG_INCLUDE_FILES: self.files,
                cfg.CONFIG_DELIMITER: self.delimiter,
                cfg.CONFIG_PARSER: self.parser.get_config(),
                cfg.CONFIG_CATEGORY_COLUMNS: self.get_reserved_categorycols(),
                cfg.CONFIG_FITTING_COLUMNS: [],
                cfg.CONFIG_CATEGORY_COMBINATIONS: self.combolist
                }
=======

    def get_config(self):
        config = {
            cfg.CONFIG_EXCLUDE_FILES: self.excluded_files,
            cfg.CONFIG_INCLUDE_FILES: self.files,
            cfg.CONFIG_DELIMITER: self.delimiter,
            cfg.CONFIG_PARSER: self.parser.get_config(),
            cfg.CONFIG_CATEGORY_COLUMNS: self.get_reserved_categorycols(),
            cfg.CONFIG_FITTING_COLUMNS: [],
        }
>>>>>>> prefect
        return config

    def set_parser(self, parser):
        if parser is not None:
            self.parser = parser

    def get_parser(self):
        return self.parser

    def set_preprocessor(self, preprocessor):
        self.preprocessor = preprocessor

    def get_preprocessor(self):
        return self.preprocessor

    def set_delimiter(self, delimiter):
        if delimiter is not None:
            self.delimiter = delimiter

    def get_delimiter(self):
        return self.delimiter

<<<<<<< HEAD

    def set_column_combos(self, combolist):
        self.combolist = combolist
    
=======
>>>>>>> prefect
    def set_files(self, files, extensions=DEFAULT_EXT, exclude=None, sort=True):
        if exclude is None:
            exclude = self.excluded_files
        self.files = []
        self.add_files(files, extensions, exclude, sort)

    def set_excluded_files(self, exclude):
        if exclude is None:
            exclude = []
        self.excluded_files = exclude

    def get_excluded_files(self):
        return self.excluded_files
<<<<<<< HEAD
        
    
=======

>>>>>>> prefect
    def add_files(self, files, extensions=DEFAULT_EXT, exclude=None, sort=True):
        if files is None:
            return None, 0
        if exclude is None:
            exclude = self.excluded_files
        added_files = 0
        skipped_files = 0
        files = [os.path.abspath(f) for f in set(files)]
        ext = tuple(extensions)
        for f in files:
            if os.path.isdir(f):
                filesindir = glob.glob(os.path.join(f, "*"))
                added, skipped = self.add_files(
                    filesindir, extensions=extensions, exclude=exclude
                )
                added_files += added
                skipped_files += skipped
            else:
                if (
                    os.path.isfile(f)
                    and f.endswith(ext)
                    and not f in self.files
                    and not os.path.basename(f) in exclude
                ):
                    self.files.append(f)
                    added_files += 1
                else:
                    skipped_files += 1
        if sort:
            self.files = sorted(self.files)
        return (added_files, skipped_files)

    def remove_files(self, rfiles):
        logging.debug(f"removing {rfiles}")
        if rfiles is not None:
            self.files = [f for f in self.files if f not in rfiles]

    def remove_allfiles(self):
        self.files = []

    def get_files(self):
        return self.files

    def get_reserved_categorycols(self, parser=None):
        if parser is None:
            parser = self.parser
<<<<<<< HEAD
        rcatnames = ['Cell line', 'Category', 'Cat', 'FOV', 'Well', 'Cell',
         'Treatment', 'Treatment 1', 'Treatment 2', 'Treatment 1 & 2', 'Time',
          'Compartment', 'New Cat', 'Origin', 'AE Label', 'Cluster', 'Combined']    
        rcatnames.extend([entry[cfg.CONFIG_PARSER_CATEGORY] for entry in parser.get_regexpatterns() for key in entry])
=======
        rcatnames = [
            "Cell line",
            "Category",
            "Cat",
            "Cluster",
            "FOV",
            "Well",
            "Cell",
            "Treatment",
            "Treatment 1",
            "Treatment 2",
            "Treatment 1 & 2",
            "Time",
            "Compartment",
            "New Cat",
            "Origin",
            "AE Label",
            "Source",
        ]
        rcatnames.extend(
            [
                entry[cfg.CONFIG_PARSER_CATEGORY]
                for entry in parser.get_regexpatterns()
                for key in entry
            ]
        )
>>>>>>> prefect
        return sorted(set(rcatnames))

    def import_data(self, delimiter=None, parser=None, preprocessor=None, nrows=None):
        if delimiter is None:
            delimiter = self.delimiter
        delimiter = "|".join(delimiter)
        if parser is None:
            parser = self.parser
        if preprocessor is None:
            preprocessor = self.preprocessor
        dflist = []
        filenames = []
        fheaders = []
        comboheaders = []
        cdflist = []
        for f in self.files:
            if not os.path.isfile(f):
                continue
            # columns defined by parser regexpatterns will use 'category' as dtype
            category_dtypes = {
                col: "object" for col in self.get_reserved_categorycols(parser)
            }
            df = pd.read_table(
                f,
                delimiter=delimiter,
                engine="python",
                dtype=category_dtypes,
                nrows=nrows,
            )
            headers = parser.parsefilename(f)
            for key in headers:
                df[key] = headers[key]
            if preprocessor is not None:
                df, ch = preprocessor.rename_headers(df)
                df, dl = preprocessor.drop_columns(df)
            dflist.append(df)
            fheaders.extend(list(headers.keys()))
            filenames.append(f)
            
            filecdf = None
            if self.combolist is not None:
                if len(self.combolist) == 0:
                    categories = [cat for cat in category_dtypes if cat in df.select_dtypes(['object']).columns]
                    self.combolist = [combo for combo in itertools.combinations(categories, 2)]
                for combo in self.combolist:
                    combocol = "-".join(combo)
                    cdf = pd.DataFrame(df[combo[0]].str.cat([df[c] for c in combo[1:]], sep="-").astype("category")).reset_index(drop=True)
                    cdf.columns = [combocol]
                    if filecdf is None:
                        filecdf = cdf
                    else:
                        filecdf = pd.concat([filecdf, cdf], axis=1) #add col
                    comboheaders.append(combocol)
            if filecdf is not None:
                cdflist.append(filecdf)
            
        if len(dflist) == 0:
            return  # None, filenames, None
        else:
            fheaders = set(fheaders+comboheaders)
            df = pd.concat(dflist).reset_index(drop=True)
            if len(cdflist) > 0:
                cdf = pd.concat(cdflist).reset_index(drop=True)
                df = pd.concat([df, cdf], axis=1, copy=True)
            #df.reset_index(inplace=True, drop=True)

            #if 'ROI' not in df.columns.values:
            #    df['ROI'] = np.arange(1,len(df)+1) 
            #print ('done')
            allheaders = list(df.columns.values)
<<<<<<< HEAD
            logging.debug (self.get_reserved_categorycols(parser))
            categories = [key for key in self.get_reserved_categorycols(parser) if key in allheaders]+comboheaders
            '''df['ROI'] = df.groupby(categories).cumcount() + 1
            df['ROI'] = [str(roi) for roi in df['ROI']]
            categories.append('ROI')'''
            
            for ckey in categories:
                df[ckey] = df[ckey].astype('category')
            if preprocessor is None:
                dp = pp.defaultpreprocessor()
                df = dp.reorder_columns(df)
            else:
                df = preprocessor.reorder_columns(df)
                df,_,_ = preprocessor.calculate(df)
            return df, filenames, fheaders 
=======
            logging.debug(self.get_reserved_categorycols(parser))
            categories = [
                key
                for key in self.get_reserved_categorycols(parser)
                if key in allheaders
            ]
>>>>>>> prefect

            # if 'ROI' not in df.columns.values:
            #    df['ROI'] = df.groupby(categories).cumcount() + 1
            #    df['ROI'] = [str(roi) for roi in df['ROI']]
            #    categories.append('ROI')

            for ckey in categories:
                df[ckey] = df[ckey].astype("category")
            if preprocessor is None:
                dp = pp.defaultpreprocessor()
                df = dp.reorder_columns(df)
            else:
                df = preprocessor.reorder_columns(df)
                df, _, _ = preprocessor.calculate(df)
            return df, filenames, fheaders
