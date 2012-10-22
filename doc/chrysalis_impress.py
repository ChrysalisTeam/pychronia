# -*- coding: utf-8 -*-
import math

def spiralz(slide, slides, r=800):
    """:doc:`spiral`"""
    i = float(slide.index)
    if i > 0:
        slide.x = math.cos(i) * r
        slide.y = math.sin(i) * r
        slide.z =  - math.log(i) * r * 7
        slide.rotate_x += (r / 180. * math.pi)
        slide.rotate_y += (r / 180. * math.pi)
        slide.rotate_y += (r / 180. * math.pi)