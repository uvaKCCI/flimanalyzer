#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 10/27/20 2:08 PM
# @Author: Jiaxin_Zhang


import os


def mkdir(path):
    path = path.strip()
    path = path.rstrip("/")
    isexists = os.path.exists(path)

    if not isexists:
        os.makedirs(path)
        return True
    else:
        return False
