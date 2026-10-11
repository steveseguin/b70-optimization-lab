#!/usr/bin/env python3
"""Bounded CPU preparation only; never imports a device runtime."""
from common import prepare
if __name__ == '__main__':
    m = prepare()
    print('PASS CPU preparation:', len(m['fixtures']), 'fixtures;', m['fixture_cases'])
