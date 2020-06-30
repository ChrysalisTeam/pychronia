# -*- coding: utf-8 -*-
"""
Created on Mon Jun 29 17:01:36 2020

@author: csfrlaay
"""

import shutil

size = 10

original = r'images\rouge.png'

for i in range(0, size):
    for j in range(0, size):
        shutil.copyfile(original, r'images\puzzle_cell_'+str(i)+'_'+str(j)+'.png')
