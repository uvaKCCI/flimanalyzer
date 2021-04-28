#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 5 07:53:29 2021

@author: khs3z
"""

import wx
from matplotlib.backends.backend_wx import NavigationToolbar2Wx

class MyCustomToolbar(NavigationToolbar2Wx): 

    _NTB_PLAY = wx.NewId()
	
    def __init__(self, plotCanvas):
        # create the default toolbar
        NavigationToolbar2Wx.__init__(self, plotCanvas)
        # remove the unwanted button
        # POSITION_OF_CONFIGURE_SUBPLOTS_BTN = 6
        # self.DeleteToolByPos(POSITION_OF_CONFIGURE_SUBPLOTS_BTN)
        self.AddSimpleTool(_NTB_PLAY, _load_bitmap('forward.xpm'),
                        'Play', 'Start playing')
                    
