#!/usr/bin/env python3

import sys
import os

# SLOPPY HACK
sys.path.insert(0, os.path.dirname(__file__) + '/..')

import boxes

#transductor = boxes.PrimeTransductor()
#transductor.test()

#inductor = boxes.PrimeInductor()
#inductor.test()

reductor = boxes.SomeReductor()
reductor.test(verbose=True)

reductor = boxes.MonadicReductor()
reductor.test(verbose=True)

#reductor = boxes.Merger()
#reductor.test(view=True, verbose=True)

#sync = boxes.Sync_zip2()
#sync.test(view=True, verbose=True)