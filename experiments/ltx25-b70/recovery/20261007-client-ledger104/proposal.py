#!/usr/bin/env python3
"""Offline source proposal only. Does not import a client or touch any endpoint."""
import ast
import hashlib
from pathlib import Path

SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-resolution-full-103/resolution/components/request_client.py')
SOURCE_SHA256 = '4cd6c8b18cfce78367ea35f01ea67dffa7bbf4bb88abad38c4ac5df4b7c15c1d'
OLD = '''    def checkpoint(self):
        self.check_fixed()
        now = self.free_probe(self.root)
        G.require(type(now) is int and now >= 0, 'Invalid filesystem reading')
        self.state['charged_write_bytes'] += max(0, self.state['last_available_bytes'] - now)
        self.state['last_available_bytes'] = now
        remaining = WRITE_ALLOWANCE - self.state['charged_write_bytes']
        G.require(remaining >= 0 and now >= MIN_FREE + remaining, 'Storage reserve/allowance exhausted')
        self.save_state()
'''
NEW = '''    def checkpoint(self):
        self.check_fixed()
        now = self.free_probe(self.root)
        G.require(type(now) is int and now >= 0, 'Invalid filesystem reading')
        previous_storage = (self.state['charged_write_bytes'], self.state['last_available_bytes'])
        self.state['charged_write_bytes'] += max(0, self.state['last_available_bytes'] - now)
        self.state['last_available_bytes'] = now
        remaining = WRITE_ALLOWANCE - self.state['charged_write_bytes']
        G.require(remaining >= 0 and now >= MIN_FREE + remaining, 'Storage reserve/allowance exhausted')
        # Every other state mutation has its own explicit durable save. If these
        # fields did not change, the ledger already contains this checkpoint state.
        if (self.state['charged_write_bytes'], self.state['last_available_bytes']) != previous_storage:
            self.save_state()
'''


def transform(raw):
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Proposal requires exact sealed103 source')
    text = raw.decode()
    if text.count(OLD) != 1:
        raise ValueError('Expected checkpoint source differs')
    result = text.replace(OLD, NEW).encode()
    before, after = ast.parse(raw), ast.parse(result)
    for tree in (before, after):
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Client')
        cls.body = [n for n in cls.body if not (isinstance(n, ast.FunctionDef) and n.name == 'checkpoint')]
    if ast.dump(before) != ast.dump(after):
        raise ValueError('Proposal changed code outside checkpoint')
    return result
