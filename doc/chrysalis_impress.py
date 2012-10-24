# -*- coding: utf-8 -*-
import math

def spiralz(slide, slides, r=2000):
    """:doc:`spiral`"""
    i = float(slide.index)
    if i > 0:
        slide.x = int(math.cos(i * math.pi / 4.5) * r)
        slide.y = int(math.sin(i * math.pi / 4.5) * r)
        slide.z = 100000 - int(i * r * 1)
        slide.rotate_x = 90 + int(10 * math.cos(i * math.pi / 2.8))
        slide.rotate_y += int(r / 180. * math.pi)
        slide.rotate_z += int(r / 180. * math.pi)
        print "Slide", i, "has", slide.x, slide.y, slide.z, "-", slide.rotate_x, slide.rotate_y, slide.rotate_z
    else:
        slide.x = slide.y = 0
        slide.z = 100000
        slide.rotate_x = slide.rotate_y = slide.rotate_z = 0