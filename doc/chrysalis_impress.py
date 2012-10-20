# -*- coding: utf-8 -*-
import math

def spiralz(slide, slides, r=1200):
    """:doc:`spiral`"""
    i = slide.index
    if i > 0:
        slide.x = math.cos(i) * r
        slide.y = math.sin(i) * r
        slide.z =  - math.log(i) * r * 3
        slide.rotate_x += (r / 180. * math.pi)
        slide.rotate_y += (r / 180. * math.pi)
        slide.rotate_y += (r / 180. * math.pi)