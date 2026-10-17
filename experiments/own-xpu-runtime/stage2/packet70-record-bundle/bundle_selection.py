"""Packet64's sealed topology and optional kernels; no environment overrides."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
PLACEMENTS = {'1': (1, 0, 24)}
EXPERTS = ('production', 'wide64', 'wg64', 'wg128', 'prefetch64')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def selected():
    row = json.loads((P / 'bundle-selection.json').read_text())
    rank, split, boundary = PLACEMENTS[row['placement']]
    if (row['draft_rank'], row['target_split'], row['layer_boundary']) != (rank, split, boundary):
        raise ValueError('sealed topology differs')
    if row['draft'] not in ('production', 'draft-hc') or row['miss'] not in ('control', 'batch'):
        raise ValueError('unregistered packet64 selection')
    if row['selection_sha256'] != sha(P / 'selection.json'):
        raise ValueError('kernel selection differs from bundle')
    if row.get('experts') not in EXPERTS or row['name'] != '1-draft-hc-batch-' + row['experts']:
        raise ValueError('unregistered expert choice')
    if row['draft'] != 'draft-hc' or row['miss'] != 'batch':
        raise ValueError('packet70 preset differs')
    view = P / 'selections' / row['name']
    for leaf in ('selection.json', 'memory-plan.json', 'dispatch-speed6.json'):
        if sha(view / leaf) != sha(P / leaf):
            raise ValueError('active configuration differs from sealed view: ' + leaf)
    if row['screen_seal_sha256'] != sha(view / 'screen-seal.json'):
        raise ValueError('selected screen seal changed')
    return row
