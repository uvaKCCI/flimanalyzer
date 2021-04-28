"""
Created on Fri May  4 02:42:45 2018

@author: khs3z
"""

import logging
from flim.core.importer import dataimporter
from flim.core.parser import defaultparser
from flim.core.preprocessor import defaultpreprocessor
from flim.core.analyzer import dataanalyzer
#from flim.gui.app import FlimAnalyzerApp

import pandas as pd
import argparse
import sys

class FLIMAnalyzer():
    
    def __init__(self, importer=dataimporter(), preprocessor=defaultpreprocessor(), danalyzer=dataanalyzer()):
        self.importer = importer
        self.preprocessor = preprocessor
        self.analyzer = danalyzer
        self.data = pd.DataFrame()
#        self.outputgenerator = outputgenerator()
        logging.debug(f"Initialized {__name__}.FlimAnalyzer with {importer}, {preprocessor}, {danalyzer}")
        

    def get_data(self):
        return self.data
    

    def get_importer(self):
        return self.importer
    
    
    def set_importer(self, imp):
        if imp is not None:
            self.importer = imp
            
    def get_preprocessor(self):
        return self.preprocessor
    
    
    def set_preprocessor(self, pp):
        if pp is not None:
            self.preprocessor = pp
            
    def get_analyzer(self):
        return self.analyzer
    
    
    def set_analyzer(self, anl):
        if anl is not None:
            self.analyzer = anl
            
    def set_outputgenerator(self, og):
        if og is not None:
            self.outputgenerator = og


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", nargs='+', help="import set of files or directories")
    parser.add_argument("-e", "--exclude", nargs='+', default=[], help="exclude file from importing")
    parser.add_argument("-o", "--output", default=None, help="save imported dataset to file")
    return parser.parse_args()
    

def noninteractive_test(fa, logger, args):
    impo = fa.get_importer()
#    a,s = impo.add_files(["../data/large_dataset"], exclude=['Master.txt'])
    a,s = impo.add_files(args.input, exclude=args.exclude)
    logger.debug ("\nFound %d file(s), skipping %d file(s)" % (a,s))
       
    hparser = defaultparser()
#    pattern = hparser.get_regexpatterns()
#    pattern['Test'] = pattern.pop('FOV')
#    hparser.set_regexpatterns(pattern)
    logging.info ("\n","Importing raw data from %d file(s)..." % len(impo.get_files()))
    data,_,fheaders = impo.import_data(delimiter="\t", hparser=hparser)
    if data is None:
        logging.info ("No data")
        return
    logging.info ("Raw data contains %d rows, %d columns" % (data.shape[0], data.shape[1]))
    
    pp = fa.get_preprocessor()
    pp.set_replacementheaders({'Exc1_-Ch1-_':'trp ', 'Exc1_-Ch2-_':'NAD(P)H ', 'Exc2_-Ch3-_':'FAD '})
    data,ch = pp.rename_headers(data)
    data, dc = pp.drop_columns(data, [' ', 'Exc1', 'Exc2'], func='startswith')
    logging.debug ("\nRenamed %d column header(s)" % len(ch))
    logging.debug (ch)    
    logging.debug ("\nDropped %d columns: data contains %d rows, %d columns" % (len(dc), data.shape[0], data.shape[1]))
    logging.debug (dc)    

    # reorder headers
    logging.info ("\nColumn headers parsed from file name(s): %s" % fheaders)
    logging.info ("Other headers: %s" % (set(data.columns.values)-fheaders))
    nh = list(fheaders)
    nh.extend(sorted(set(data.columns.values)-fheaders))
    if len(nh) == len(data.columns):
        data = data.reindex(nh, axis=1)
    
    analyzer = fa.get_analyzer()
    analyzer.add_columns([
            'NAD(P)H tm', 'NAD(P)H a2[%]/a1[%]', 
            'NAD(P)H %', 'NADH %', 'NAD(P)H/NADH', 
            'trp tm', 'trp E%1', 'trp E%2', 'trp E%3', 'trp a1[%]/a2[%]', 
            'FAD tm', 'FAD a1[%]/a2[%]', 'FAD photons/NAD(P)H photons',
            'NAD(P)H tm/FAD tm',
            'FLIRR {NAD(P)H a2[%]/FAD a1[%])',
            ])
    analyzer.add_rangefilters({
            'NAD(P)H tm': [0,5000],
            'NAD(P)H chi': [0,7],
            'FAD tm': [0,5000],
            'FAD chi': [0,7],
            'trp tm': [0,5000],
            'trp chi': [0,7],
            'trp E%1': [0,100],
            'trp E%2': [0,100],
            'trp E%3': [0,100],
            })

    logging.info ("\nCalculating values for added columns...")
    data,capplied,cskipped = analyzer.calculate(data)
    logging.info ("Applied %d calculation functions, skipped %d: data contains %d rows, %d columns" % (len(capplied),len(cskipped), data.shape[0], data.shape[1]))
    for afunc in capplied:
        logging.debug ("\tcalculated %s" % afunc)
    for sfunc in cskipped:
        logging.debug ("\tskipped %s" % sfunc)

    logging.info ("\nFiltering values...")
    data,fapplied,fskipped, droppedrows = analyzer.apply_filter(data)
    logging.info ("Applied %d filters, skipped %d filters, dropped %d rows: data contains %d rows, %d columns" % (len(fapplied),len(fskipped), droppedrows, data.shape[0], data.shape[1]))
    for afunc in fapplied:
        logging.debug ("\tapplied: %s (%s), dropped %d rows" % (afunc[0],afunc[1],afunc[2],))
    for sfunc in fskipped:
        logging.debug ("\tskipped %s" % sfunc) 


    
