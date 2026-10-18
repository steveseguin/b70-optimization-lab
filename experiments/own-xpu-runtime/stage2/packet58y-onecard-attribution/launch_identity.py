"""Derive service identity from the coordinator's actual command builder."""
import importlib.util
from pathlib import Path

LANEQUEUE = Path(__file__).resolve().parents[2] / 'ops/lane-queue/lanequeue.py'
# Observe the real command builder without pinning mutable coordinator code.
import sys
sys.path.insert(0,str(LANEQUEUE.parent))
try:
    spec=importlib.util.spec_from_file_location('packet58y_lanequeue',LANEQUEUE)
    L=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)
finally:
    sys.path.pop(0)


def unit_name(job, library=''):
    command = L.command(job, '/tmp/packet58y-review.json', '/tmp/packet58y-exit.json', library)
    return next(arg.split('=', 1)[1] for arg in command if arg.startswith('--unit=')) + '.service'


def lane_unit_prefix():
    # No duplicated screen- literal: a naming change in lanequeue reaches this gate.
    return unit_name(dict(name='packet58y-', lane='A', argv=[])).removesuffix('.service')
