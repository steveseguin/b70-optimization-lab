"""Derive service identity from the coordinator's actual command builder."""
import importlib.util
from pathlib import Path

LANEQUEUE = Path(__file__).resolve().parents[3] / 'ops/lane-queue/lanequeue.py'
spec = importlib.util.spec_from_file_location('p58ag_packet58ab_lanequeue', Path(__file__).with_name('coordinator_snapshot.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


def unit_name(job, library=''):
    command = L.command(job, '/tmp/packet58x-review.json', '/tmp/packet58x-exit.json', library)
    return next(arg.split('=', 1)[1] for arg in command if arg.startswith('--unit=')) + '.service'


def lane_unit_prefix():
    # No duplicated screen- literal: a naming change in lanequeue reaches this gate.
    return unit_name(dict(name='packet176-', lane='A', argv=[])).removesuffix('.service')
