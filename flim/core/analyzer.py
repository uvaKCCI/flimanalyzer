#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  4 19:37:11 2018

@author: khs3z
"""

import flim.analysis.absanalyzer
import logging
import numpy as np
import pandas as pd
import flim.core.preprocessor
import numbers
from flim.gui.events import DataWindowEvent, EVT_DATA_TYPE

class dataanalyzer():
    
    def __init__(self):
        #self.additional_columns = []
        #self.functions = {
        #        'NADPH %': [nadph_perc.__name__,['NAD(P)H t2']],
        #        'NAD(P)H tm': [tm.__name__,['NAD(P)H a1[%]','NAD(P)H t1','NAD(P)H a2[%]','NAD(P)H t2']],
        #        'NAD(P)H a2[%]/a1[%]': [ratio.__name__, ['NAD(P)H a2[%]', 'NAD(P)H a1[%]']],
        #       'NADH %': [nadh_perc.__name__,['NADPH %']],
        #        'NADPH/NADH': [ratio.__name__, ['NADPH %', 'NADH %']],
        #        'trp tm': [tm.__name__,['trp a1[%]','trp t1','trp a2[%]','trp t2']],
        #        'trp E%1': [trp_Eperc_1.__name__,['trp tm']],
        #        'trp E%2': [trp_Eperc_2.__name__,['trp t1','trp t2']],
        #        'trp E%3': [trp_Eperc_3.__name__,['trp t1']],
        #        'trp r1': [trp_r.__name__,['trp E%1']],
        #        'trp r2': [trp_r.__name__,['trp E%2']],
        #        'trp r3': [trp_r.__name__,['trp E%3']],
        #        'trp a1[%]/a2[%]': [ratio.__name__, ['trp a1[%]', 'trp a2[%]']],
        #        'FAD tm': [tm.__name__,['FAD a1[%]','FAD t1','FAD a2[%]','FAD t2']],
        #        'FAD a1[%]/a2[%]': [ratio.__name__, ['FAD a1[%]', 'FAD a2[%]']],
        #        'FAD photons/NAD(P)H photons': [ratio.__name__, ['FAD photons', 'NAD(P)H photons']],
        #        'NAD(P)H tm/FAD tm': [ratio.__name__,['NAD(P)H tm','FAD tm']],
        #        'FLIRR': [ratio.__name__, ['NAD(P)H a2[%]', 'FAD a1[%]']],
        #        'NADPH a2/FAD a1': [ratio.__name__, ['NAD(P)H a2', 'FAD a1']],
        #        }
        self.rangefilters = {}
        self.filters = {}
        
    def get_config(self):
        return dict(self.functions)
                
    #def add_functions(self, newfuncs):
    #    if newfuncs is not None:
    #        self.functions.update(newfuncs)


    def add_filters(self, newfilters):
        if newfilters is not None:
            if type(newfilters) is list:
                newfilters = {f.get_name():f for f in newfilters}
            self.filters.update(newfilters)


    def get_filters(self):
        return self.filters

    
    def add_rangefilters(self, newfilters):
        if newfilters is not None:
            self.rangefilters.update(newfilters)

        
    def set_rangefilters(self, newfilters):
        if newfilters is not None:
            self.rangefilters = newfilters

    
    def set_seriesfilter(self, newseriesfilter):
        if newseriesfilter is not None:
            self.seriesfilter = newseriesfilter
            
    def get_rangefilters(self):
        return self.rangefilters
    
    
    #def add_columns(self, ncols):
    #    if ncols is not None:
    #        self.additional_columns.extend(ncols)
    
    
    #def get_additional_columns(self):
    #    return self.additional_columns
    
    
    def columns_available(self, data, args):
        for arg in args:
            if not isinstance(arg, numbers.Number) and data.get(arg) is None:
                return False
        return True

    
    def apply_filter(self, data, dropna=True, onlyselected=True, inplace=True, dropsonly=False):
        # store current col order
        currentcols = data.columns.tolist()
        usedfilters = []
        skippedfilters = []
        alldroppedrows = []
        if data is None:
            return None, usedfilters, [[k,self.rangefilters[k]] for k in self.rangefilters], len(alldroppedrows)
        logging.debug ("dataanalyzer.apply_filter: filtering %d rows, %d filters, onlyselected=%s" % (data.shape[0], len(self.rangefilters), str(onlyselected)))
        #if dropna:
        #    droppedrows = np.flatnonzero(data.isna().any(axis=0))
        #    usedfilters.append(['drop NaN', 'any', droppedrows])
        #    print "    dropped NaN", len(droppedrows)
        #    alldroppedrows.extend(droppedrows)
        for acol in sorted(self.rangefilters):
            rfilter = self.rangefilters[acol]
            if (onlyselected and not rfilter.is_selected()) or not self.columns_available(data, [acol]):
                skippedfilters.append([acol,rfilter])
            else:
                #low,high = rfilter.get_range()
                #logging.debug (f"{rfilter.is_selected()}, filtering {acol}: {low}, {high}")
                #if dropna:
                #    droppedrows = np.flatnonzero((data[acol] != data[acol]) | (data[acol] > high) | (data[acol] < low))
                #else:    
                #    droppedrows = np.flatnonzero((data[acol] > high) | (data[acol] < low))
                #data = data[(data[acol] >= low) & (data[acol] <= high)]
                droppedrows = rfilter.get_dropped(data)
                usedfilters.append([acol, rfilter, droppedrows])
                alldroppedrows.extend(droppedrows)
        
#        alldroppedrows = sorted(np.unique(alldroppedrows), reverse=True)
        logging.debug(f"usedfilters: {usedfilters}")
        alldroppedrows = np.unique(alldroppedrows)
        filtereddata = data
        if not dropsonly:
            filtereddata = data.drop(alldroppedrows, inplace=inplace)
        #print filtereddata

        # series filters        
        cats = list(filtereddata.select_dtypes(['category']).columns.values)
        noncats = filtereddata.select_dtypes(['number']).columns.values
        # create shortlist of cols (all categories plus 1 data col)

        
        cols = list(cats)
        if len(noncats) > 0:
            cols.append(noncats[0])
        #print self.seriesfilter
        combineddroppedidx = None
        for seriesname in self.seriesfilter:
            logging.debug (f'Required series: {seriesname}, {self.seriesfilter[seriesname]}')
            logging.debug (f'category columns: {cats}')
            logging.debug (f'Column subset: {cols}')
            # create smaller df with cats, seriesname, and single datacolumn, restrict to data rows that match series rrequirment defined by filter
            sdata = filtereddata[cols]
            logging.debug (sdata)

            # pivot data to find incomplete series            
            indexgroups = [c for c in cats if c != seriesname]
            pdata = sdata.pivot_table(index=indexgroups,columns=[seriesname],aggfunc='count')
            # restrict to seriesfilter columns of interest
            pdata = pdata.loc[:,pdata.columns.get_level_values(1).isin(self.seriesfilter[seriesname])]
            logging.debug (pdata)
            droppedseriesrows = pdata[pdata.isna().any(axis=1)]
            logging.debug (droppedseriesrows.index.tolist())
            
            # set index on filtered data and remove intersection with droppedseiresrows.index
            filtereddata.set_index(indexgroups, inplace=True, drop=False)
            droppedindex = droppedseriesrows.index.intersection(filtereddata.index)
            if combineddroppedidx is None:
                combineddroppedidx = droppedindex
            else:
                combineddroppedidx = droppedindex.union(combineddroppedidx)
            #print filtereddata.index
            #print droppedindex
            if not droppedindex.empty:
                filtereddata = filtereddata.set_index(droppedindex.names, drop=False).drop(droppedindex)
            filtereddata.reset_index(inplace=True, drop=True)
        # restore column order
        filtereddata = filtereddata[currentcols]
        #print filtereddata
        #print combineddroppedidx
        return filtereddata, usedfilters, skippedfilters, len(alldroppedrows), combineddroppedidx    


    def get_analysis_options(self):
        #return [k for k in self.analysis_functions]
        return [toolname for toolname in  analysis.absanalyzer.get_analyzer_classes()]
    
    
    def get_analysis_function(self, analysis_name):
        #return self.analysis_functions.get(analysis_name)
        return analysis.absanalyzer.get_analyzer_classes()[analysis_name]
    
    


   
        
    def categorize_data(self, data, col, bins=[-1, 1], labels='1', normalizeto={}, grouping=[], dropna=True, use_minvalue=False, joinmaster=True, add_ascategory=True, category_colheader='Category'):
        if not grouping or len(grouping) == 0:
            return
        ref_cols = [c for c in grouping if c in normalizeto]
        non_ref_cols = [c for c in grouping if c not in ref_cols]
        ref_values = tuple([normalizeto[c] for c in ref_cols])
        unstack_levels = [grouping.index(c) for c in ref_cols]
        logging.debug (f"COLS TO UNSTACK, ref_cols={str(ref_cols)}, non_ref_cols={str(non_ref_cols)}, unstack_levels={str(unstack_levels)}, ref_values={str(ref_values)}")
#        med = data.groupby(grouping)[col].median().unstack(level=0)#.rename(columns=str).reset_index()
        logging.debug (data.groupby(grouping)[col].median())
        med = data.groupby(grouping)[col].median().unstack(unstack_levels)#.rename(columns=str).reset_index()
        # keep only columns where topindex matches the outermost ref_value for unstacking
        logging.debug (f"unstacked med\t{med}")
        
        # TEST
#        xs_ref = med.xs(ref_values,level=ref_cols, axis=1, drop_level=True)
#        xs_meds = med.xs(ref_values[0],level=ref_cols[0], axis=1, drop_level=False)
#        print "crossection ref:\n", xs_ref
#        print "crossection others:\n", xs_meds
#        xs_norms = xs_meds.apply(lambda df:(df-xs_ref)/xs_ref * 100)
#        print "crossection norms:\n", xs_norms
        
        
        med = med.loc[:,ref_values[0]]
        if dropna:
            med.dropna(axis=0, inplace=True)
        logging.debug (f'med\t{med}')
        logging.debug (f'med.index\t {med.index}')
        
#        reorderedcols = [c for c in ref_cols] # [normalizeto]
#        reorderedcols.extend([c for c in med.columns.values if c != ref_cols])
#        med = med[reorderedcols]
#        med = med.xs(level=reorderedcols,axis=1)
#        print 'med[reorderedcols]',med.head()    

        # pick single multi-indexed column
        ref_median = med.loc[:,ref_values[1:]].iloc[:,0]
#        ref_median = med.xs(ref_values[1:], level=ref_cols[1:], axis=1)
        logging.debug (f'ref_median\t{ref_median}') 
        logging.debug (f'ref_median.index\t{ref_median.index}')

#        rel = med.iloc[:,1:].apply(lambda df:(df-med[ref_cols])/med[ref_cols]*100)
#        rel = med.apply(lambda df:(df-ref_median)/ref_median * 100, axis=0, raw=True)
        rel = med.apply(lambda df:(df-ref_median)/ref_median * 100)
        logging.debug (f'rel.columns.values\t{rel.columns.values}')
        logging.debug (f'rel.index\t{rel.index}')
        logging.debug (f'ref_values[1:]\t{ref_values[1:]}')
        if len(ref_values) == 2:
            rel.drop(ref_values[1], axis=1, inplace=True)
        else:    
            rel.drop(ref_values[1:], level=0, axis=1, inplace=True)
        logging.debug (f'rel\t{rel}')
        logging.debug (f'rel.index\t{rel.index}')
        rel.columns = [c+' rel %' for c in rel.columns.values]
        rel['min rel %'] = rel.min(axis=1)
        rel['max rel %'] = rel.max(axis=1)
        logging.debug (f'rel after addition of min %/max %\t{rel}')
        logging.debug (f'rel.index after addition of min %/max %\t{rel.index}')
        # create category for each column
        for c in rel.columns.values:
            rel['Cat %s' %c] = pd.cut(rel[c], bins=bins, labels=labels)#.rename('cat %s' % col)
#        med = pd.merge(med,rel, on=non_ref_cols)
        if use_minvalue:
            rel[category_colheader] = rel['Cat min rel %']    
        else:    
            rel[category_colheader] = rel['Cat max rel %']    
        logging.debug (f'med after rel merge {med}')
        med = pd.merge(med.rename(columns=str).reset_index(),rel.rename(columns=str).reset_index(), on=non_ref_cols)
        if joinmaster:
            if category_colheader in data.columns.values:
                data = data.drop([category_colheader], axis=1)
            logging.debug (f"DATA.INDEX={data.index}")
            logging.debug (f"REL[COL].INDEX={rel[category_colheader].index}")
            joineddata = data.join(rel[category_colheader], on=non_ref_cols).rename(index=str, columns={category_colheader: category_colheader})
            logging.debug (joineddata.dtypes)
            if add_ascategory:
                joineddata[category_colheader].astype('category')
                unassigned = 'unassigned'
                joineddata[category_colheader] = joineddata[category_colheader].cat.add_categories([unassigned])
                logging.debug (f"CATEGORIES={joineddata[category_colheader].cat.categories}")
                joineddata = joineddata.fillna(value={category_colheader:unassigned})
            logging.debug (joineddata.columns.values)
            return med, core.preprocessor.reorder_columns(joineddata)
        else:
            return med, data

        




