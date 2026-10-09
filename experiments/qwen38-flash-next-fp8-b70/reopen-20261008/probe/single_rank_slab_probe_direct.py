#!/usr/bin/env python3
"""Separately admitted direct-host-pointer variant; never chained to indirect."""
import sys
from single_rank_slab_probe import main

if __name__ == '__main__':
    raise SystemExit(main(['--direct-host-pointer', *sys.argv[1:]]))
