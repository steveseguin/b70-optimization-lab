#!/usr/bin/env python3
"""Packet 95: is there room for one more sampler worker's graphs before capturing it?

    worker-headroom-95.py <coverage receipt.json> <layout>

Needed per card = 2 GiB floor + 0.12 GiB per transformer block on that card (one
worker's graph static buffers and pool share, measured in 94f: xpu:0 grew by 2.1-2.7
GiB for 18-23 blocks when the second worker captured) + 0.1 GiB on xpu:0 (glue).
The capture pass runs BEFORE the decode probe, so the room still to be taken by the
xpu:1 VAE replica (1.8 GiB) and the VAEs' explicit load onto xpu:3 (1.9 GiB) is added
(pre_decode=True, the runner's case).
Exit 0: every card has it. Exit 10: prints the cards that do not (the combination is
skipped cleanly, before anything is captured). Reads files only.
"""
import json
import sys

GIB = 2**30
FLOOR = 2.0
PER_BLOCK = 0.12
LAYOUTS = {'two-way': {'xpu:0': 23, 'xpu:1': 25, 'xpu:2': 0, 'xpu:3': 0},
           'shard3-c': {'xpu:0': 20, 'xpu:1': 20, 'xpu:2': 8, 'xpu:3': 0},
           'shard4-a': {'xpu:0': 18, 'xpu:1': 18, 'xpu:2': 8, 'xpu:3': 4}}


PRE_DECODE = {'xpu:1': 1.8, 'xpu:3': 1.9}


def needed(layout, pre_decode=True):
    out = {}
    for card, blocks in LAYOUTS[layout].items():
        out[card] = (FLOOR + PER_BLOCK * blocks + (0.1 if card == 'xpu:0' else 0.0) +
                     (PRE_DECODE.get(card, 0.0) if pre_decode else 0.0))
    return out


def verdict(free_bytes, layout, pre_decode=True):
    short = {}
    for card, need in needed(layout, pre_decode).items():
        have = free_bytes.get(card)
        if have is None or have < need * GIB:
            short[card] = {'free_gib': None if have is None else round(have / GIB, 3), 'needed_gib': round(need, 3)}
    return not short, short


if __name__ == '__main__':
    receipt = json.load(open(sys.argv[1]))
    ok, short = verdict(receipt.get('free_bytes') or {}, sys.argv[2])
    print(json.dumps({'room_for_one_more_worker': ok, 'short': short, 'needed_gib': needed(sys.argv[2])}))
    sys.exit(0 if ok else 10)
