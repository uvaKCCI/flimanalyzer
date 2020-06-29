#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  7 14:38:04 2018

@author: khs3z
"""

import os
import logging
import argparse
import sys
import core.parser as cp
from gui.app import FlimAnalyzerApp
from core.flimanalyzer import flimanalyzer
from core.configuration import Config, CONFIG_PARSERCLASS



def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", nargs='+', help="import set of files or directories")
    parser.add_argument("-e", "--exclude", nargs='+', default=[], help="exclude file from importing")
    parser.add_argument("-o", "--output", default=None, help="save imported dataset to file")
    parser.add_argument("-p", "--parser", default='core.parser.defaultparser', help="use this class to parse filename")
    parser.add_argument("-c", "--config", default=None, help="configuration file, superseeds -p option")
    parser.add_argument("-l", "--log", choices=['info', 'debug', 'warning'', error', 'critical'], default='info', help="logging level")
    return parser.parse_args()
    


def noninteractive_run(fa, args):
    impo = fa.get_importer()
    a,s = impo.add_files(args.input, exclude=args.exclude)
    print ("\nFound %d file(s), skipping %d file(s)." % (a,s))
    if len(impo.get_files())==0:
        return
    if args.config:
        if not os.path.isfile(args.config):
            print ("Configuration file %s does not exist." % args.config)
        else:
            config = Config()
            config.read_from_json(args.config)
    else:
        config = Config()
        config.create_default()
        config.update({CONFIG_PARSERCLASS:args.parser})        
    hparser = cp.instantiate_parser(config.get(CONFIG_PARSERCLASS))
    if hparser is None:
        print ("Error instantiating filename parser %s" % args.parser)
        return

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
    

def interactive_run(fa):    
    app = FlimAnalyzerApp(fa)
    app.MainLoop()


if __name__ == "__main__":
    args = parse_arguments()
    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log)
    logging.basicConfig(level=numeric_level,filename='flimanalyzer.log', format='%(levelname)s:%(message)s')
    logging.info("FlimAnalyzer version %s" % __version__)
    fa = flimanalyzer()
    if len(sys.argv) > 1:
        print (args)
        noninteractive_run(fa,args)
    else:
        interactive_run(fa)
