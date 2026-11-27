#!/usr/bin/env python3
"""Stores for the generated new shapes: up_stores (f18_stores driven by the PT), with the F-18-specific intake-lip
probe made optional (generated jets have no stock intake faces).  Usage: stores.py in.SH in.PT out.SH [static]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import up_stores
U = up_stores.U
_lip = U.intake_lip
def safe_lip(d):
    try: return _lip(d)
    except AssertionError: return 10 ** 4          # no intake lip: leave the PT launch point as it is
U.intake_lip = safe_lip

if __name__ == '__main__':
    up_stores.run(sys.argv[1], sys.argv[2], sys.argv[3], static=len(sys.argv) > 4)
