#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 29 17:30:44 2018

@author: khs3z
"""

import os
import pandas as pd
import glob
import re
import argparse

def parseArguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", nargs='+', help="import set of files or directories")
    parser.add_argument("-e", "--exclude", nargs='+', default=[], help="exclude file from importing")
    parser.add_argument("-o", "--output", default=None, help="save imported dataset to file")
    return parser.parse_args()
    
    
def defaultHeaderParser(fname, strip=["Results"], delimiters=['_','-','\.']):
    name = os.path.basename(fname)
    # remove substrings defined in strip list
    for s in strip:
        name = name.replace(s,'')
    # split by delimiter
    rawcols = re.split("|".join(delimiters), name)
    # remove empty elements
    rawcols = [col for col in rawcols if col != '']
    # create headers
    group = re.findall(r'\d+', rawcols[0])[0]
    fov = re.findall('[^\W\d]', rawcols[0])[0]
    headers = {'Directory':os.path.dirname(fname), 'File':os.path.basename(fname), 'Treatment':group, 'Cell':rawcols[-2], 'FOV':fov}
    return headers


def importRawData(input, extension="*.txt", delimiter=",", hparser=defaultHeaderParser, exclude=[]):
    dflist = []  
    readfiles = 0
    skippedfiles = 0
    for f in input:
        if os.path.isdir(f):
            f = glob.glob(os.path.join(f,extension))
        for fname in f:    
            if os.path.basename(fname) in exclude:
                skippedfiles+=1
                continue
            df = pd.read_table(fname, delimiter=delimiter, engine='python')
            headers = hparser(fname)
            for key in headers:
                df[key] = headers[key]
            dflist.append(df)
            readfiles+=1
    return (pd.concat(dflist),readfiles,skippedfiles)    
           

def saveRawData(data, fname):
    data.to_csv(fname, index=False)

        
if __name__ == "__main__":
    args = parseArguments()
    print args
    input = [os.path.abspath(i) for i in args.input]
    data,readfiles,skippedfiles = importRawData(input, delimiter="\t", exclude=args.exclude)
    print "Read %d file(s)" % readfiles
    print "Skipped %d file(s)" % skippedfiles
    if args.output is not None:
        print "Saving imported data to", args.output
        saveRawData(data, args.output)
