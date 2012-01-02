# -*- coding: utf-8 -*-
import random
LIST = ["A", "4", "3", "E", "D", "A", "F", "8", "B", "C", "D", "6", "5"]

def genarate_color():
    color = "#"
    for i in range(6):
        color += random.choice(LIST)
    return color