"""The three requested packet80-baseline compositions, all at placement 1."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent / 'packet84-record-bundle'
ROOT = HERE.parents[3]
sys.path.insert(0, str(PACKET))
from bundle_selection import KEYS, name, selection
from build_engine import sha

BASE = dict(dense='production', hc='hc-wide', experts='wide64', host='ordered',
            route='production', norm='production', recurrence='production', draft_head='production')
VIEWS = {'control': BASE, 'candidate-a': dict(BASE, recurrence='rec-parallel'),
         'candidate-b': dict(BASE, recurrence='rec-parallel', route='fast')}
ORDER = ('control', 'candidate-a', 'candidate-b', 'control')

def values(label):
    return tuple(VIEWS[label][k] for k in KEYS)

def view(label):
    return PACKET / 'selections' / (name(*values(label)) + '--placement-1')

def output(index):
    return HERE.parent / 'screen/v4-lanes/evidence' / f'p84s-B-{index}-{ORDER[index]}'

def verify():
    from chain_seal import check_map
    from screen_seal_support import wrapper_seal
    wrapper_seal()
    pin = json.loads((HERE / 'composition-pin.json').read_text())
    check_map(ROOT, pin['sources'])
    assert pin['views'] == VIEWS
    assert pin['order'] == list(ORDER)
    for label in VIEWS:
        assert json.loads((view(label) / 'selection.json').read_text()) == selection(values(label))
        assert sha(view(label) / 'screen-seal.json') == pin['seals'][label]
        assert sha(view(label) / 'build/device/own-rt-iq3') == pin['binary_sha256']
    return pin
