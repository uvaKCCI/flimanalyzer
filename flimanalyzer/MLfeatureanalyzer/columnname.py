#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 10/27/20 2:29 PM
# @Author: Jiaxin_Zhang

import string


def getColumnName(columnIndex):
    ret = ''
    ci = columnIndex - 1
    index = ci // 26
    if index > 0:
        ret += getColumnName(index)
    ret += string.ascii_uppercase[ci % 26]

    return ret
