#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 23 18:21:33 2018

@author: khs3z
"""

import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas


class MatplotlibPanel(wx.Panel):
    def __init__(self, parent, figure, ax):
        wx.Panel.__init__(self, parent)
        self.figure = figure
        self.axes = ax  # self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.sizer)
        self.Fit()


class MatplotlibFrame(wx.Frame):
    def __init__(self, parent, title, fig, ax):
        wx.Frame.__init__(self, parent, title=title)
        panel = MatplotlibPanel(self, fig, ax)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel)
        self.SetSizer(sizer)
        self.Fit()
