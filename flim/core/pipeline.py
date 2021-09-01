#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Aug  7 09:25:32 2020

@author: khs3z
"""

import dask
from prefect import task, Task, Flow, Parameter
from prefect.agent.local import LocalAgent
import random


class WorkflowExecutor:

    def __init__(self, client):
        self.client = client
        self.pipeline = {}
    
    def _task_function(self, analyzername, data, **params): 
        if isinstance(data,dict):
            data = list(data.items())[0][1] 
        analysis_class = flim.analysis.absanalyzer.get_analyzer_classes()[analyzername]
        tool = flim.analysis.absanalyzer.create_instance(analysis_class, data) #, data_choices=data_choices)
        tool.configure(**params)
        #print (tool.get_parameters())
        return tool.execute()
    
    def start_agent(self):
        LocalAgent().start()
    
    def register_workflow(self):
        
    def load_pipeline(self, fname):
        pass
        
    def save_pipeline(self, fname):
        pass
        
    def add_task(self, analyzername, data, **params):
        taskname = (analyzername,0)
        i = 1
        while taskname in self.pipeline:
            taskname = (taskname[0],i)
            i+=1
        print (f'task={taskname}, input type={type(data)}')
        self.pipeline[taskname] = (apply, self._task_function, [analyzername, data], params)
        return (taskname, data)
        
    def get_pipeline(self):
        return self.pipeline.copy()
        
    def optimize(self):
        pass
    
    def create_pipeline(self):
        pass
            
    def run(self):
        return get(pipeline, list(pipeline.keys()))
    
def task_function(data, analyzername, **params): 
    if isinstance(data,dict):
        data = list(data.items())[0][1] 
    analysis_class = flim.analysis.absanalyzer.get_analyzer_classes()[analyzername]
    tool = flim.analysis.absanalyzer.create_instance(analysis_class, data) #, data_choices=data_choices)
    tool.configure(**params)
    #print (tool.get_parameters())
    return tool.execute()
    
    
@task(log_stdout=True)
def say_hello(name):
    #print (f'Hello {name}')
    return f'Hello {name}'

@task(log_stdout=True)
def number_task():
    return 42

@task(log_stdout=True)
def add_task(x, y):
    return x+y

@task
def random_number():
    return random.randint(0, 100)

@task
def plus_one(x):
    return x + 1

class DfSplit(Task):
    def run(self, data, rows=10):
        return data.iloc[:rows,:],data.iloc[rows:,:]

class DfHead(Task):
    def run(self, data):
        return data.head()

class DfMerge(Task):
    def run(self, input):
        return pd.concat(input)

class Root(Task):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Input"
        
    def run(self, data):
        return data


import pandas as pd
import numpy as np
import flim.analysis
import dask
from dask import delayed
from dask.multiprocessing import get
#from dask.distributed import Client
from dask.utils import apply


n=1000
df = pd.DataFrame(np.random.rand(3*n, 4), columns = ['FOV', 'Treatment', 'FAD a1%', 'FLIRR'])
df['FOV'] = n*['a'] + n*['b'] + n*['c']
df['Treatment'] = n*['Ctrl', 'dox15', 'dox30']
#print (df)

params = {'grouping':[],'features':['FLIRR', 'FAD a1%'],'aggs':['mean','median','count']}
params2 = {'grouping':['Treatment'], 'features':['FLIRR', 'FAD a1%'], 'keeporig':True}
params3 = {'grouping':['Treatment'], 'features':['Principal component 1', 'Principal component 2'], 'aggs':['max']}
params4 = {'grouping':['Treatment'], 'features':['FLIRR\nmean'], 'aggs':['median']}

dsk = {'summary': (apply, task_function, ['Summary Table', df], params),
	'pca': (apply, task_function, ['Principal Component Analysis', df], params2),
	'summary 2': (apply, task_function, ['Summary Table', 'pca'], params3),
	'summary 3': (apply, task_function, ['Summary Table', 'summary'], params4),}

#client = Client(asynchronous=False)  # start distributed scheduler locally.  Launch dashboard
#print (client)
""""
p = PipelineExecutor(None)
sumtask,_ = p.add_task('Summary Table', df, **{'grouping':['FOV','Treatment'],'features':['FLIRR', 'FAD a1%'],'aggs':['mean','count']})
pcatask,_ = p.add_task('Principal Component Analysis', df, **params2)
randomtask,_ = p.add_task('Random Forest', df, classifier='Treatment', **params)
p.add_task('Summary Table', pcatask, **params3)
p.add_task('Summary Table', sumtask, **params4)
pipeline = p.get_pipeline()
graphimg = dask.visualize(pipeline,filename='pipeline.svg')
result = p.run()
for r in result:
	print (r)
"""
from flim.analysis.summarystats import SummaryStats
from flim.analysis.pca import PCAnalysis

inputtask = Root()
stask = SummaryStats(log_stdout=True)
pcatask = PCAnalysis(log_stdout=True)
with Flow('FLIM Flow') as flow:
	input = inputtask(data=df)
	sresult = stask(data=input, grouping=['FOV'],features=['FLIRR', 'FAD a1%'],aggs=['max','mean','median','count'])
	pcaresult = pcatask(data=input, features=['FLIRR', 'FAD a1%'], keeporig=True)
	sresult2 = stask(data=sresult, input_select=[0], grouping=['FOV'], features=['FLIRR\nmean'], aggs=['max'])
	sresult3 = stask(data=pcaresult, input_select=['PCA'], grouping=[], features=['Principal component 1'], aggs=['max'])
	sresult4 = stask(data=pcaresult, input_select=['PCA explained'], grouping=['PCA component'], features=['explained var ratio'], aggs=['max'])

g = flow.visualize()
print (g)
#flow.run()