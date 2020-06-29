"""
Created on Fri May  4 02:42:45 2018

@author: khs3z
"""

from core.importer import dataimporter
from core.parser import defaultparser
from core.preprocessor import defaultpreprocessor
from core.analyzer import dataanalyzer
from gui.app import FlimAnalyzerApp

import pandas as pd
import argparse
import sys

class flimanalyzer():
    
    def __init__(self):
        self.importer = dataimporter()
        self.preprocessor = defaultpreprocessor()
        self.analyzer = dataanalyzer()
        self.data = pd.DataFrame()
#        self.outputgenerator = outputgenerator()
        

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
    

def noninteractive_test(fa, args):
    impo = fa.get_importer()
#    a,s = impo.add_files(["../data/large_dataset"], exclude=['Master.txt'])
    a,s = impo.add_files(args.input, exclude=args.exclude)
    print ("\nFound %d file(s), skipping %d file(s)" % (a,s))
       
    hparser = defaultparser()
#    pattern = hparser.get_regexpatterns()
#    pattern['Test'] = pattern.pop('FOV')
#    hparser.set_regexpatterns(pattern)
    print ("\n","Importing raw data from %d file(s)..." % len(impo.get_files()))
    data,_,fheaders = impo.import_data(delimiter="\t", hparser=hparser)
    if data is None:
        print ("No data")
        return
    print ("Raw data contains %d rows, %d columns" % (data.shape[0], data.shape[1]))
    
    pp = fa.get_preprocessor()
    pp.set_replacementheaders({'Exc1_-Ch1-_':'trp ', 'Exc1_-Ch2-_':'NAD(P)H ', 'Exc2_-Ch3-_':'FAD '})
    data,ch = pp.rename_headers(data)
    data, dc = pp.drop_columns(data, [' ', 'Exc1', 'Exc2'], func='startswith')
    print ("\nRenamed %d column header(s)" % len(ch))
    print (ch)    
    print ("\nDropped %d columns: data contains %d rows, %d columns" % (len(dc), data.shape[0], data.shape[1]))
    print (dc)    

    # reorder headers
    print ("\nColumn headers parsed from file name(s): %s" % fheaders)
    print ("Other headers: %s" % (set(data.columns.values)-fheaders))
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

    print ("\nCalculating values for added columns...")
    data,capplied,cskipped = analyzer.calculate(data)
    print ("Applied %d calculation functions, skipped %d: data contains %d rows, %d columns" % (len(capplied),len(cskipped), data.shape[0], data.shape[1]))
    for afunc in capplied:
        print ("\tcalculated %s" % afunc)
    for sfunc in cskipped:
        print ("\tskipped %s" % sfunc)

    print ("\nFiltering values...")
    data,fapplied,fskipped, droppedrows = analyzer.apply_filter(data)
    print ("Applied %d filters, skipped %d filters, dropped %d rows: data contains %d rows, %d columns" % (len(fapplied),len(fskipped), droppedrows, data.shape[0], data.shape[1]))
    for afunc in fapplied:
        print ("\tapplied: %s (%s), dropped %d rows" % (afunc[0],afunc[1],afunc[2],))
    for sfunc in fskipped:
        print ("\tskipped %s" % sfunc) 


#    fig,ax = stacked_histogram(data, 'trp tm', bins=100, normalize=100)
#    fig.show()
#    fig,ax = stacked_histogram(data, 'trp tm', groups=['Treatment'], bins=100, normalize=100)
#    fig.show()
#    fig,ax = stacked_histogram(data, 'FAD tm', bins=100, normalize=100)
#    fig.show()
#    fig,ax = stacked_histogram(data, 'FAD tm', groups=['Treatment'], bins=100, normalize=100)
#    fig.show()
#    fig,ax = stacked_histogram(data, 'NAD(P)H tm', bins=100, normalize=100)
#    fig.show()
#    fig,ax = stacked_histogram(data, 'NAD(P)H tm', groups=['Treatment'], bins=100, normalize=100)
#    fig.show()
#    print "\n",data.describe()
    

def interactive_main(fa):    
    app = FlimAnalyzerApp(fa)
    app.MainLoop()


if __name__ == "__main__":
    fa = flimanalyzer()
    noninteractive_test(fa,sys.args)
    