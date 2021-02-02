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
from gui.app import FlimAnalyzerApp
import core.parser as cp
import analysis
from analysis.absanalyzer import AbstractAnalyzer
from core.tools import FLIMAnalyzer
from core.configuration import Config, CONFIG_PARSERCLASS

#from MLfeatureanalyzer.autoencoder2 import SAE

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", nargs='+', help="import set of files or directories")
    parser.add_argument("-e", "--exclude", nargs='+', default=[], help="exclude file from importing")
    parser.add_argument("-o", "--output", default=None, help="save imported dataset to file")
    parser.add_argument("-p", "--parser", default='core.parser.defaultparser', help="use this class to parse filename")
    parser.add_argument("-c", "--config", default=None, help="configuration file, superseeds -p option")
    parser.add_argument("-l", "--log", choices=['info', 'debug', 'warning', 'error', 'critical'], default='info', help="logging level")
    return parser.parse_args()
    


def noninteractive_run(fa, args):
    impo = fa.get_importer()
    a,s = impo.add_files(args.input, exclude=args.exclude)
    logging.debug ("\nFound %d file(s), skipping %d file(s)." % (a,s))
    if len(impo.get_files())==0:
        return
    if args.config:
        if not os.path.isfile(args.config):
            logging.debug ("Configuration file %s does not exist." % args.config)
        else:
            config = Config()
            config.read_from_json(args.config)
    else:
        config = Config()
        config.create_default()
        config.update({CONFIG_PARSERCLASS:args.parser})        
    hparser = cp.instantiate_parser(config.get(CONFIG_PARSERCLASS))
    if hparser is None:
        logging.debug ("Error instantiating filename parser %s" % args.parser)
        return

    logging.debug ("\n","Importing raw data from %d file(s)..." % len(impo.get_files()))
    data,_,fheaders = impo.import_data(delimiter="\t", hparser=hparser)
    if data is None:
        logging.debug ("No data")
        return
    logging.debug ("Raw data contains %d rows, %d columns" % (data.shape[0], data.shape[1]))  
    
    pp = fa.get_preprocessor()
    pp.set_replacementheaders({'Exc1_-Ch1-_':'trp ', 'Exc1_-Ch2-_':'NAD(P)H ', 'Exc2_-Ch3-_':'FAD '})
    data,ch = pp.rename_headers(data)
    data, dc = pp.drop_columns(data, [' ', 'Exc1', 'Exc2'], func='startswith')
    logging.debug ("\nRenamed %d column header(s)" % len(ch))
    logging.debug (ch)    
    logging.debug ("\nDropped %d columns: data contains %d rows, %d columns" % (len(dc), data.shape[0], data.shape[1])) 
    logging.debug (dc)    

    # reorder headers
    logging.debug ("\nColumn headers parsed from file name(s): %s" % fheaders)
    logging.debug ("Other headers: %s" % (set(data.columns.values)-fheaders))
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
    logging.debug ("Applied %d calculation functions, skipped %d: data contains %d rows, %d columns" % (len(capplied),len(cskipped), data.shape[0], data.shape[1]))
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


def interactive_run(fa):    
    app = FlimAnalyzerApp(fa)
    app.MainLoop()

def init_logger(loglevel):
    numeric_level = getattr(logging, loglevel, None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log)
    logging.basicConfig(level=numeric_level,filename='flimanalyzer.log', filemode='w', format='%(levelname)s \t %(asctime)-15s - %(module)s.%(funcName)s: %(message)s')
    logging.info(f"Log level: {numeric_level}")

def init_analyzers(fa):
    tools = analysis.available_tools
    analyzers = [analysis.absanalyzer.create_instance(tools[aname], None, None, None) for aname in tools]
    return analyzers

def init_default_config(analyzers):
    config = {}
    for a in analyzers:
        config.update(a.get_default_parameters())
    return config

if __name__ == "__main__":
    with open(os.path.join("..","VERSION"), "r") as vf:
        __version__ = vf.read().strip()
    args = parse_arguments()
    init_logger(args.log.upper())
    logging.info(f"FlimAnalyzer version {__version__}")
            
    logging.debug(args)
    fa = FLIMAnalyzer()
    analyzers = init_analyzers(fa)
    config = init_default_config(analyzers)
    if args.input is None or args.output is None or args.config is None:
        interactive_run(fa)
    else:
        noninteractive_run(fa,args)
