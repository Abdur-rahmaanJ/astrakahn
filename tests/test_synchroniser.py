#!/usr/bin/env python3

# SLOPPY HACK
import sys
import os
sys.path.insert(0, os.path.dirname(__file__) + '/..')

import components as comp
import communication as comm
import time
from multiprocessing import Process
import random
import copy
import network as net

def gen(inp):

    continuation = copy.copy(inp)
    continuation['start'] += 1

    if inp['n'] == 0:
        return (None, None)

    continuation['n'] -= 1

    return ({0: inp['start']}, continuation)

def rprint(cid, msg):
    print(str(cid) + ":", msg)


init = [comm.DataMessage({'start': 1, 'n': 4}),
        comm.SegmentationMark(0),
        ]

P = net.Network("test_reductor")

P.add_vertex("2P", "G", ['init'], ['seq'],  gen, {'initial_messages': init})
P.add_vertex("1S2", "S", ['a', 'b'], ['zipped'])
P.add_vertex("C2", "P", ['p'], [], rprint)

P.wire(('G', 'v'), ('R', 'v'))
P.wire(('R', 'a'), ('P', 'pa'))
P.wire(('S', 'zipped'), ('P', 'p'))

P.start()
P.join()

P.debug_status()
