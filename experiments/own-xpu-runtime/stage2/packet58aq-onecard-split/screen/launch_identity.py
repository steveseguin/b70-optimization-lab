"""Derive service identity from the coordinator's actual command builder."""
import importlib.util
from pathlib import Path

LANEQUEUE = Path(__file__).resolve().parents[3] / 'ops/lane-queue/lanequeue.py'
spec = importlib.util.spec_from_file_location('p58aq_lanequeue', Path(__file__).with_name('coordinator_snapshot.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


def unit_name(job, library=''):
    command = L.command(job, '/tmp/packet58x-review.json', '/tmp/packet58x-exit.json', library)
    return next(arg.split('=', 1)[1] for arg in command if arg.startswith('--unit=')) + '.service'


def lane_unit_names():
    import json
    names=[]
    for tag in ('split','smoke'):
        path=Path(__file__).parent/'proposals'/('proposed-p58aq-'+tag+'-A.txt')
        job=json.loads(next(x for x in path.read_text().splitlines() if x.startswith('{')))
        L.validate(job,'A')
        names.append(unit_name(job))
    return tuple(names)
